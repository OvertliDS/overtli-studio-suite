# ============================================================================
# lm_studio_vision.py
# GZ_LMStudioTextEnhancer - Local multimodal inference via LM Studio
# ============================================================================
"""
GZ_LMStudioTextEnhancer: LM Studio Node
=======================================
Runs local text/vision inference through LM Studio OpenAI-compatible APIs.

Features:
- Multimodal support with IMAGE tensor and FILE_PATH inputs
- Connection health monitoring before inference
- Optional model unload and VRAM cleanup after execution
- Grouped mode-family controls (text/image/video/tts)
"""

from __future__ import annotations

import base64
import gc
import importlib
import io
import logging
import os
from typing import Any, Optional, Tuple

requests = importlib.import_module("requests")

from .base_node import GZBaseNode
from .exceptions import OvertliAPIError, OvertliInputError, OvertliModelError, OvertliTimeoutError, OvertliVisionError
from .image_utils import comfy_image_to_pil, validate_comfy_image
from .instruction_modes import (
    IMAGE_MODE_NAMES,
    TEXT_MODE_NAMES,
    TTS_MODE_NAMES,
    VIDEO_MODE_NAMES,
    resolve_mode_family_preset,
    resolve_mode_preset,
)
from .prompt_styles import (
    STYLE_OFF_LABEL,
    append_style_layers_to_prompt,
    get_style_options,
    infer_mode_category,
    normalize_style_presets,
)
from .settings_store import resolve_config_value, save_persistent_settings
from .shared_utils import normalize_string_input, select_image_batch_indices, validate_single_image_source
from .suite_config import get_config

logger = logging.getLogger(__name__)

_DEFAULT_TEXT_MAX_TOKENS = 750
_CHARS_PER_TOKEN_ESTIMATE = 4


def _get_pil_image_module():
    return importlib.import_module("PIL.Image")


def _get_torch_module():
    return importlib.import_module("torch")


def _is_probably_vision_model(model_name: str) -> bool:
    """Best-effort classifier for local model names that usually support images."""
    normalized = (model_name or "").lower()
    vision_tokens = (
        "vision",
        "vl",
        "llava",
        "multimodal",
        "gemma-3",
        "qwen-vl",
        "qwen2.5-vl",
        "minicpm-v",
        "moondream",
        "phi-4-mm",
    )
    return any(token in normalized for token in vision_tokens)


def _extract_model_name(model_display: str) -> str:
    """Extract model id from tagged display value."""
    if not model_display:
        return ""
    name = model_display.split(" [", 1)[0].strip()
    return "" if name.lower() == "auto" else name


def _format_model_display(model_name: str) -> str:
    """Attach lightweight tags for model picker display."""
    tag = "[vision]" if _is_probably_vision_model(model_name) else "[text]"
    return f"{model_name} {tag} [local]"


def _build_auth_headers(api_key: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        headers["x-api-key"] = api_key
    return headers


def _check_lmstudio_connection(
    timeout_seconds: int = 5,
    headers: Optional[dict[str, str]] = None,
) -> Tuple[bool, str]:
    """Probe LM Studio model endpoint for health status."""
    cfg = get_config().lm_studio
    try:
        response = requests.get(cfg.models_endpoint, headers=headers or None, timeout=timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        models = payload.get("data", payload) if isinstance(payload, dict) else payload
        if isinstance(models, list):
            return True, f"Connected ({len(models)} model(s) visible)"
        return True, "Connected"
    except Exception as exc:  # noqa: BLE001
        return False, f"Connection failed: {exc}"


def fetch_lmstudio_models() -> list[str]:
    """Fetch local model list from LM Studio and decorate entries."""
    cfg = get_config().lm_studio
    base = ["auto [local]"]

    try:
        resolved_api_key = resolve_config_value(
            "lmstudio_api_key",
            default=(cfg.api_key or ""),
        )
        auth_headers = _build_auth_headers(resolved_api_key)

        response = requests.get(cfg.models_endpoint, headers=auth_headers or None, timeout=8)
        response.raise_for_status()
        payload = response.json()
        models = payload.get("data", payload) if isinstance(payload, dict) else payload

        if not isinstance(models, list):
            return base

        names: list[str] = []
        for model_data in models:
            if isinstance(model_data, dict):
                model_name = (
                    model_data.get("id")
                    or model_data.get("model")
                    or model_data.get("name")
                    or ""
                )
            else:
                model_name = str(model_data)

            model_name = normalize_string_input(model_name)
            if model_name:
                names.append(_format_model_display(model_name))

        return base + sorted(set(names)) if names else base
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to fetch LM Studio models: %s", exc)
        return base


_CACHED_MODELS: Optional[list[str]] = None


def get_cached_models() -> list[str]:
    """Get cached LM Studio model options."""
    global _CACHED_MODELS
    if _CACHED_MODELS is None:
        _CACHED_MODELS = fetch_lmstudio_models()
    return _CACHED_MODELS


def refresh_models() -> list[str]:
    """Force refresh cached LM Studio models."""
    global _CACHED_MODELS
    _CACHED_MODELS = None
    return get_cached_models()


def _prepare_image_data_url(image_tensor: Any, max_dimension: int) -> str:
    """Convert ComfyUI IMAGE tensor to a bounded-size JPEG data URL."""
    if not hasattr(image_tensor, "shape"):
        raise OvertliVisionError("Invalid IMAGE tensor input", image_source="tensor")

    validate_comfy_image(image_tensor, name="image")

    pil_image = comfy_image_to_pil(image_tensor)
    width, height = pil_image.size
    pil_image_module = _get_pil_image_module()

    if max(width, height) > max_dimension:
        ratio = max_dimension / float(max(width, height))
        resized = (
            max(1, int(width * ratio)),
            max(1, int(height * ratio)),
        )
        pil_image = pil_image.resize(resized, pil_image_module.Resampling.LANCZOS)

    buffer = io.BytesIO()
    pil_image.save(buffer, format="JPEG", quality=90, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{encoded}"


def _prepare_image_data_urls(
    image_tensor: Any,
    max_dimension: int,
    batch_image_mode: str,
    max_batch_frames: int,
) -> list[str]:
    validate_comfy_image(image_tensor, name="image")

    if len(image_tensor.shape) == 4 and image_tensor.shape[0] > 1:
        indices = select_image_batch_indices(
            batch_size=image_tensor.shape[0],
            batch_image_mode=batch_image_mode,
            max_batch_frames=max_batch_frames,
        )
        return [_prepare_image_data_url(image_tensor[index : index + 1], max_dimension=max_dimension) for index in indices]

    return [_prepare_image_data_url(image_tensor, max_dimension=max_dimension)]


def _prepare_image_data_url_from_path(file_path: str, max_dimension: int) -> str:
    """Convert image file directly to bounded-size JPEG data URL without tensor conversion."""
    try:
        pil_image_module = _get_pil_image_module()

        with pil_image_module.open(file_path) as source:
            pil_image = source.convert("RGB")

        width, height = pil_image.size
        if max(width, height) > max_dimension:
            ratio = max_dimension / float(max(width, height))
            resized = (
                max(1, int(width * ratio)),
                max(1, int(height * ratio)),
            )
            pil_image = pil_image.resize(resized, pil_image_module.Resampling.LANCZOS)

        buffer = io.BytesIO()
        pil_image.save(buffer, format="JPEG", quality=90, optimize=True)
        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{encoded}"
    except FileNotFoundError as exc:
        raise OvertliVisionError(f"Image file not found: {file_path}", image_source="file_path") from exc
    except Exception as exc:  # noqa: BLE001
        raise OvertliVisionError(f"Failed to process image file: {exc}", image_source="file_path") from exc


def _extract_text_content(value: Any) -> str:
    """Normalize LM Studio/OpenAI-compatible content payloads into plain text."""
    if isinstance(value, str):
        return value

    if isinstance(value, list):
        parts = [_extract_text_content(item) for item in value]
        return "\n".join(part for part in parts if part).strip()

    if isinstance(value, dict):
        if "text" in value and isinstance(value["text"], str):
            return value["text"]
        if "content" in value:
            return _extract_text_content(value["content"])

    return ""


def _unload_model(model_name: str, headers: Optional[dict[str, str]] = None) -> None:
    """Attempt to unload the active model without failing the main response flow."""
    cfg = get_config().lm_studio
    if not model_name:
        return

    payload_variants = [
        {"model": model_name},
        {"model_name": model_name},
        {"id": model_name},
    ]

    for payload in payload_variants:
        try:
            response = requests.post(cfg.unload_endpoint, json=payload, headers=headers or None, timeout=10)
            if response.ok:
                logger.info("LM Studio model unload succeeded for '%s'.", model_name)
                return
        except Exception:  # noqa: BLE001
            continue

    logger.warning("LM Studio model unload request did not succeed for '%s'.", model_name)


def _cleanup_runtime_memory() -> None:
    """Run defensive memory cleanup after local inference."""
    gc.collect()

    try:
        torch_module = _get_torch_module()
    except Exception:
        return

    if torch_module.cuda.is_available():
        try:
            torch_module.cuda.empty_cache()
        except Exception:  # noqa: BLE001
            pass
        try:
            torch_module.cuda.ipc_collect()
        except Exception:  # noqa: BLE001
            pass


class GZ_LMStudioTextEnhancer(GZBaseNode):
    """Local LM Studio text enhancer with optional multimodal context."""

    CATEGORY = "OVERTLI STUDIO/LLM"
    FUNCTION = "execute"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("response",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        model_options = refresh_models()
        return {
            "required": {
                "prompt": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "placeholder": "Ask your local model to analyze, reason, or describe...",
                    },
                ),
                "text_mode_enabled": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "Text Mode ON",
                        "label_off": "Text Mode OFF",
                    },
                ),
                "text_mode": (TEXT_MODE_NAMES, {"default": "Off"}),
                "image_mode_enabled": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "Image Mode ON",
                        "label_off": "Image Mode OFF",
                    },
                ),
                "image_mode": (IMAGE_MODE_NAMES, {"default": "Off"}),
                "video_mode_enabled": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "Video Mode ON",
                        "label_off": "Video Mode OFF",
                    },
                ),
                "video_mode": (VIDEO_MODE_NAMES, {"default": "Off"}),
                "tts_mode_enabled": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "TTS Mode ON",
                        "label_off": "TTS Mode OFF",
                    },
                ),
                "tts_mode": (TTS_MODE_NAMES, {"default": "Off"}),
                "model": (
                    model_options,
                    {
                        "default": model_options[0] if model_options else "auto [local]",
                    },
                ),
            },
            "optional": {
                "image": ("IMAGE",),
                "custom_instructions": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "forceInput": True,
                        "placeholder": "Custom instructions (overrides mode)...",
                    },
                ),
                "style_preset_1": (
                    get_style_options(),
                    {"default": STYLE_OFF_LABEL},
                ),
                "style_preset_2": (
                    get_style_options(),
                    {"default": STYLE_OFF_LABEL},
                ),
                "style_preset_3": (
                    get_style_options(),
                    {"default": STYLE_OFF_LABEL},
                ),
                "additional_styles": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "forceInput": True,
                        "placeholder": "Connect OVERTLI Style Stack output (STRING)...",
                    },
                ),
                "temperature": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": 0.0,
                        "max": 2.0,
                        "step": 0.1,
                    },
                ),
                "max_tokens": (
                    "INT",
                    {
                        "default": _DEFAULT_TEXT_MAX_TOKENS,
                        "min": 64,
                        "max": 32768,
                        "step": 64,
                    },
                ),
                "vision_enabled": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "label_on": "Vision ON",
                        "label_off": "Vision OFF",
                    },
                ),
                "batch_image_mode": (
                    ["all_frames", "first_middle_last", "first_frame"],
                    {"default": "all_frames"},
                ),
                "max_batch_frames": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 512,
                        "step": 1,
                    },
                ),
                "timeout_seconds": (
                    "INT",
                    {
                        "default": 60,
                        "min": 5,
                        "max": 1200,
                        "step": 5,
                    },
                ),
                "max_image_dimension": (
                    "INT",
                    {
                        "default": 1280,
                        "min": 256,
                        "max": 4096,
                        "step": 64,
                    },
                ),
                "api_key": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "placeholder": "Optional LM Studio API key...",
                    },
                ),
                "persist_api_key": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "Persist API Key",
                        "label_off": "Session Only",
                    },
                ),
                "unload_after_generation": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "Unload Model",
                        "label_off": "Keep Model Loaded",
                    },
                ),
                "cleanup_vram": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "label_on": "VRAM Cleanup ON",
                        "label_off": "VRAM Cleanup OFF",
                    },
                ),
            },
        }

    def execute(
        self,
        prompt: str,
        text_mode_enabled: bool,
        text_mode: str,
        image_mode_enabled: bool,
        image_mode: str,
        video_mode_enabled: bool,
        video_mode: str,
        tts_mode_enabled: bool,
        tts_mode: str,
        model: str,
        image: Optional[Any] = None,
        file_path: str = "",
        custom_instructions: str = "",
        style_preset_1: str = STYLE_OFF_LABEL,
        style_preset_2: str = STYLE_OFF_LABEL,
        style_preset_3: str = STYLE_OFF_LABEL,
        additional_styles: str = "",
        temperature: float = 1.0,
        max_tokens: int = _DEFAULT_TEXT_MAX_TOKENS,
        vision_enabled: bool = True,
        batch_image_mode: str = "all_frames",
        max_batch_frames: int = 0,
        timeout_seconds: int = 60,
        max_image_dimension: int = 1280,
        max_encoded_image_bytes: int = 8000000,
        max_response_chars: int = 0,
        check_connection: bool = True,
        require_healthy_connection: bool = True,
        strict_vision_model: bool = False,
        api_key: str = "",
        persist_api_key: bool = False,
        unload_after_generation: bool = False,
        cleanup_vram: bool = True,
    ) -> Tuple[str]:
        """Run inference against LM Studio local API."""
        cfg = get_config().lm_studio

        runtime_api_key = normalize_string_input(api_key)
        if runtime_api_key and persist_api_key:
            save_persistent_settings(
                {"lmstudio_api_key": runtime_api_key},
                source="GZ_LMStudioTextEnhancer",
            )

        resolved_api_key = resolve_config_value(
            "lmstudio_api_key",
            runtime_api_key,
            default=(cfg.api_key or ""),
        )
        auth_headers = _build_auth_headers(resolved_api_key)

        connection_ok = True
        timeout_seconds = self.clamp_timeout(timeout_seconds)

        if check_connection:
            connection_ok, status_message = _check_lmstudio_connection(timeout_seconds=5, headers=auth_headers)
            logger.info("LM Studio health: %s", status_message)
            if require_healthy_connection and not connection_ok:
                raise OvertliAPIError(status_message, endpoint=cfg.models_endpoint)

        source_type, source_value = validate_single_image_source(
            image_tensor=image,
            file_path=file_path,
        )

        image_tensor = None
        image_path = ""
        image_data_urls: list[str] = []

        if source_type == "file":
            resolved_path = os.path.abspath(str(source_value))
            if not os.path.exists(resolved_path):
                raise OvertliInputError(
                    f"Provided file_path does not exist: {resolved_path}",
                    input_name="file_path",
                )
            image_path = resolved_path
        elif source_type == "tensor":
            image_tensor = image

        model_name = _extract_model_name(model)
        has_image_input = bool(image_path) or image_tensor is not None
        has_vision_payload = has_image_input and vision_enabled

        if strict_vision_model and has_vision_payload and model_name and not _is_probably_vision_model(model_name):
            raise OvertliModelError(
                f"Selected model '{model_name}' is not tagged as vision-capable.",
                model_name=model_name,
            )

        try:
            if not vision_enabled and has_image_input:
                logger.info("Vision disabled; ignoring image input for LM Studio request.")
            elif image_path:
                image_data_urls = [
                    _prepare_image_data_url_from_path(
                        image_path,
                        max_dimension=max_image_dimension,
                    )
                ]
            elif image_tensor is not None:
                image_data_urls = _prepare_image_data_urls(
                    image_tensor=image_tensor,
                    max_dimension=max_image_dimension,
                    batch_image_mode=batch_image_mode,
                    max_batch_frames=max_batch_frames,
                )

            for image_data_url in image_data_urls:
                encoded_size = len(image_data_url.encode("utf-8"))
                if encoded_size > max_encoded_image_bytes:
                    raise OvertliVisionError(
                        f"Encoded image payload too large ({encoded_size} bytes); "
                        f"limit is {max_encoded_image_bytes} bytes.",
                        image_source="payload",
                    )

            resolved_mode = resolve_mode_family_preset(
                text_mode_enabled=text_mode_enabled,
                text_mode=text_mode,
                image_mode_enabled=image_mode_enabled,
                image_mode=image_mode,
                video_mode_enabled=video_mode_enabled,
                video_mode=video_mode,
                tts_mode_enabled=tts_mode_enabled,
                tts_mode=tts_mode,
            )

            instructions = resolve_mode_preset(
                mode_preset=resolved_mode,
                custom_instructions=custom_instructions,
            )
            fallback_category = "text"
            if image_mode_enabled:
                fallback_category = "image"
            elif video_mode_enabled:
                fallback_category = "video"
            elif tts_mode_enabled:
                fallback_category = "tts"

            mode_category = infer_mode_category(resolved_mode, fallback=fallback_category)
            style_labels = normalize_style_presets(
                style_preset_1=style_preset_1,
                style_preset_2=style_preset_2,
                style_preset_3=style_preset_3,
            )

            user_prompt = normalize_string_input(prompt)
            if not user_prompt and image_data_urls:
                user_prompt = "Describe these image frame(s) in detail."

            user_prompt = self.require_prompt(user_prompt, input_name="prompt")
            user_prompt = append_style_layers_to_prompt(
                raw_prompt=user_prompt,
                style_labels=style_labels,
                mode_category=mode_category,
                additional_styles=additional_styles,
            )

            messages: list[dict[str, Any]] = []
            if instructions:
                messages.append({"role": "system", "content": instructions})

            if image_data_urls:
                content: list[dict[str, Any]] = [{"type": "text", "text": user_prompt}]
                for image_data_url in image_data_urls:
                    content.append({"type": "image_url", "image_url": {"url": image_data_url}})

                messages.append(
                    {
                        "role": "user",
                        "content": content,
                    }
                )
            else:
                messages.append({"role": "user", "content": user_prompt})

            payload: dict[str, Any] = {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if model_name:
                payload["model"] = model_name

            request_headers = {"Content-Type": "application/json"}
            request_headers.update(auth_headers)

            response = requests.post(
                cfg.chat_endpoint,
                json=payload,
                headers=request_headers,
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()

            if "choices" in data and isinstance(data["choices"], list) and data["choices"]:
                content = data["choices"][0].get("message", {}).get("content", "")
                result = _extract_text_content(content)
            else:
                result = _extract_text_content(data.get("content", ""))

            result = (result or "").strip()
            if not result:
                raise OvertliAPIError("LM Studio returned an empty response", endpoint=cfg.chat_endpoint)

            effective_max_response_chars = max_response_chars
            if effective_max_response_chars <= 0:
                safe_tokens = max(64, min(int(max_tokens or _DEFAULT_TEXT_MAX_TOKENS), 32768))
                effective_max_response_chars = safe_tokens * _CHARS_PER_TOKEN_ESTIMATE

            effective_max_response_chars = max(1024, min(int(effective_max_response_chars), 2_000_000))
            if len(result) > effective_max_response_chars:
                raise OvertliAPIError(
                    (
                        "LM Studio response exceeded safety limit "
                        f"({len(result)} > {effective_max_response_chars} characters)"
                    ),
                    endpoint=cfg.chat_endpoint,
                )

            should_unload = unload_after_generation or cfg.auto_unload
            if should_unload and model_name:
                _unload_model(model_name, headers=auth_headers)

            logger.info("GZ_LMStudioTextEnhancer completed with model '%s'.", model_name or "auto")
            return (result,)

        except requests.exceptions.Timeout as exc:
            raise OvertliTimeoutError(
                f"LM Studio request timed out after {timeout_seconds} seconds",
                timeout_seconds=timeout_seconds,
                operation="lmstudio_inference",
            ) from exc
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            body = exc.response.text[:300] if exc.response is not None else str(exc)
            raise OvertliAPIError(
                f"LM Studio API error: {status} - {body}",
                endpoint=cfg.chat_endpoint,
                status_code=status,
            ) from exc
        except OvertliInputError:
            raise
        except OvertliVisionError:
            raise
        except OvertliModelError:
            raise
        except OvertliAPIError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise OvertliAPIError(f"LM Studio request failed: {exc}", endpoint=cfg.chat_endpoint) from exc
        finally:
            if cleanup_vram:
                _cleanup_runtime_memory()


