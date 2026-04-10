# ============================================================================
# pollinations/text_enhancer.py
# GZ_TextEnhancer - Vision-capable text enhancement with dynamic model selection
# ============================================================================
"""
GZ_TextEnhancer: Pollinations Chat/Vision Node
===============================================
Uses gen.pollinations.ai/v1/chat/completions compatible payloads via SuiteConfig.

Features:
- Dynamic model fetching with capability tags
- Grouped mode-family controls (text/image/video/tts)
- Optional IMAGE input for vision-capable models
- Batch image support (video frames)
"""

import importlib
import logging
import os
import time
from typing import Any, Optional, Tuple

requests = importlib.import_module("requests")

from ..exceptions import OvertliAPIError, OvertliInputError, OvertliTimeoutError, OvertliVisionError
from ..image_utils import comfy_image_to_base64, load_image_from_path
from ..instruction_modes import (
    IMAGE_MODE_NAMES,
    TEXT_MODE_NAMES,
    TTS_MODE_NAMES,
    VIDEO_MODE_NAMES,
    resolve_mode_family_preset,
    resolve_mode_preset,
)
from ..settings_store import resolve_config_value, save_persistent_settings
from ..prompt_styles import (
    STYLE_OFF_LABEL,
    append_style_layers_to_prompt,
    get_style_options,
    infer_mode_category,
    normalize_style_presets,
)
from ..shared_utils import (
    build_user_facing_error,
    normalize_string_input,
    select_image_batch_indices,
    validate_single_image_source,
)
from ..suite_config import get_config
from .compat_retry import execute_with_compat_retry
from .model_catalog import extract_display_model_name, fetch_pollinations_text_models, get_pollinations_model_entry

logger = logging.getLogger(__name__)

_DEFAULT_TEXT_MAX_TOKENS = 750


def _extract_model_name(model_display: str) -> str:
    """Extract raw model name from tagged display value."""
    if not model_display:
        return "openai"
    return extract_display_model_name(model_display) or "openai"


def _ensure_data_url(image_b64_or_data_url: str) -> str:
    """Normalize image representation to a data URL."""
    if image_b64_or_data_url.startswith("data:image/"):
        return image_b64_or_data_url
    return f"data:image/png;base64,{image_b64_or_data_url}"


# ============================================================================
# Dynamic Model Fetching
# ============================================================================


def fetch_text_models() -> list[str]:
    """
    Fetch Pollinations chat models.
    Vision-capable models remain tagged, but text-only models are allowed when no image input is used.
    """
    fallback_models = [
        "openai [text] [vision] [free]",
        "openai-fast [text] [vision] [free]",
        "openai-large [text] [vision] [free]",
    ]

    result = fetch_pollinations_text_models(require_vision=False, fallback_models=fallback_models)
    logger.info("Pollinations text models refreshed: %s eligible chat model(s)", len(result))
    return result


_CACHED_MODELS: Optional[list[str]] = None


def get_cached_models() -> list[str]:
    global _CACHED_MODELS
    if _CACHED_MODELS is None:
        _CACHED_MODELS = fetch_text_models()
    return _CACHED_MODELS


def refresh_models() -> list[str]:
    """Force refresh cached models."""
    global _CACHED_MODELS
    _CACHED_MODELS = None
    return get_cached_models()


# ============================================================================
# GZ_TextEnhancer Node
# ============================================================================


class GZ_TextEnhancer:
    """
    Pollinations Text/Vision Enhancement Node.

    Uses the 3-Layer Instruction Stack:
    1. Mode Preset
    2. Custom Instructions (overrides mode)
    3. Raw Prompt (always appended)
    """

    CATEGORY = "OVERTLI STUDIO/LLM"
    FUNCTION = "execute"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("enhanced_text",)

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
                        "placeholder": "Enter your raw prompt or idea here...",
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
                    {"default": model_options[0] if model_options else "openai [free]"},
                ),
            },
            "optional": {
                "image": ("IMAGE",),
                "file_path": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "placeholder": "Optional local image path...",
                    },
                ),
                "custom_instructions": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "forceInput": True,
                        "placeholder": "Custom instructions (overrides Mode Preset)...",
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
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.1}),
                "max_tokens": ("INT", {"default": _DEFAULT_TEXT_MAX_TOKENS, "min": 64, "max": 16384, "step": 64}),
                "seed": ("INT", {"default": -1, "min": -1, "max": 2147483647}),
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
                    {"default": 0, "min": 0, "max": 512, "step": 1},
                ),
                "api_key": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "placeholder": "Optional Pollinations API key (sk_/pk_)...",
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
        temperature: float = 0.7,
        max_tokens: int = _DEFAULT_TEXT_MAX_TOKENS,
        seed: int = -1,
        vision_enabled: bool = True,
        batch_image_mode: str = "all_frames",
        max_batch_frames: int = 0,
        api_key: str = "",
        persist_api_key: bool = False,
    ) -> Tuple[str]:
        """Execute text enhancement via Pollinations API."""
        model_name = _extract_model_name(model)
        model_entry = get_pollinations_model_entry(model_name) or {}
        model_supports_vision = bool(model_entry) and (
            bool(model_entry.get("vision")) or "image" in str(model_entry.get("input_modalities", ""))
        )
        if not model_entry:
            model_supports_vision = "[vision]" in (model or "")

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

        final_prompt = normalize_string_input(prompt)

        messages: list[dict[str, Any]] = []
        if instructions:
            messages.append({"role": "system", "content": instructions})

        source_type, source_value = validate_single_image_source(
            image_tensor=image,
            file_path=file_path,
        )

        image_tensor: Optional[Any] = None
        if source_type == "file":
            image_tensor = load_image_from_path(str(source_value))
        elif source_type == "tensor":
            image_tensor = image

        if image_tensor is not None and not final_prompt.strip():
            final_prompt = "Analyze these image frame(s) and provide a detailed response."
        elif image_tensor is None and not final_prompt.strip():
            raise OvertliInputError(
                "Prompt cannot be empty for text enhancement unless image context is provided.",
                input_name="prompt",
            )

        final_prompt = append_style_layers_to_prompt(
            raw_prompt=final_prompt,
            style_labels=style_labels,
            mode_category=mode_category,
            additional_styles=additional_styles,
        )

        try:
            if image_tensor is not None and hasattr(image_tensor, "shape"):
                if not vision_enabled:
                    logger.info("Vision disabled; ignoring image input for model '%s'.", model_name)
                    messages.append({"role": "user", "content": final_prompt})
                elif not model_supports_vision:
                    raise OvertliVisionError(
                        (
                            f"Selected model '{model_name}' is not tagged as vision-capable.\n"
                            "What happened: you supplied image input to a text-only model.\n"
                            "What we tried: we checked the live Pollinations catalog for image support.\n"
                            "What to do next: choose a [vision] Pollinations text model or disable the image input."
                        ),
                        image_source="image",
                    )
                elif len(image_tensor.shape) == 4 and image_tensor.shape[0] > 1:
                    # Batch image input (video-like): support full frame sequence.
                    frame_indices = select_image_batch_indices(
                        batch_size=image_tensor.shape[0],
                        batch_image_mode=batch_image_mode,
                        max_batch_frames=max_batch_frames,
                    )
                    content: list[dict[str, Any]] = [{"type": "text", "text": final_prompt}]

                    for index in frame_indices:
                        frame_data_url = _ensure_data_url(
                            comfy_image_to_base64(image_tensor, batch_index=index)
                        )
                        content.append({"type": "image_url", "image_url": {"url": frame_data_url}})

                    messages.append({"role": "user", "content": content})
                else:
                    single_img = _ensure_data_url(comfy_image_to_base64(image_tensor))
                    messages.append(
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": final_prompt},
                                {"type": "image_url", "image_url": {"url": single_img}},
                            ],
                        }
                    )
            else:
                messages.append({"role": "user", "content": final_prompt})
        except Exception as exc:  # noqa: BLE001
            raise OvertliVisionError(f"Failed to prepare image payload: {exc}", image_source="tensor") from exc

        config = get_config()

        runtime_api_key = normalize_string_input(api_key)
        if runtime_api_key and persist_api_key:
            save_persistent_settings(
                {"pollinations_api_key": runtime_api_key},
                source="GZ_TextEnhancer",
            )

        effective_api_key = resolve_config_value(
            "pollinations_api_key",
            runtime_api_key,
            default=(config.pollinations.api_key or ""),
        )

        headers = {"Content-Type": "application/json"}
        if effective_api_key:
            headers["Authorization"] = f"Bearer {effective_api_key}"
            headers["x-api-key"] = effective_api_key

        payload: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if seed >= 0:
            payload["seed"] = seed

        timeout_seconds = max(5, int(getattr(config.pollinations, "chat_timeout", 120) or 120))

        try:
            logger.info(
                "Pollinations chat request started (model=%s, endpoint=%s, timeout=%ss, images=%s).",
                model_name,
                config.pollinations.chat_endpoint,
                timeout_seconds,
                len(image_tensor) if hasattr(image_tensor, "__len__") and image_tensor is not None else (1 if image_tensor is not None else 0),
            )
            started_at = time.monotonic()
            response = execute_with_compat_retry(
                send_request=lambda _req_params, req_payload: requests.post(
                    config.pollinations.chat_endpoint,
                    json=req_payload,
                    headers=headers,
                    timeout=timeout_seconds,
                ),
                endpoint=config.pollinations.chat_endpoint,
                model_name=model_name,
                logger=logger,
                payload=payload,
                optional_payload_keys={"seed", "temperature", "max_tokens"},
                max_attempts=3,
            )

            with response:
                data = response.json()

                if "choices" in data and isinstance(data["choices"], list) and data["choices"]:
                    result = data["choices"][0].get("message", {}).get("content", "")
                else:
                    result = data.get("content", str(data))

                if isinstance(result, list):
                    normalized_parts = []
                    for item in result:
                        if isinstance(item, str):
                            normalized_parts.append(item)
                        elif isinstance(item, dict) and isinstance(item.get("text"), str):
                            normalized_parts.append(item["text"])
                    result = "\n".join(part for part in normalized_parts if part)
                elif isinstance(result, dict):
                    if isinstance(result.get("text"), str):
                        result = result["text"]
                    elif isinstance(result.get("content"), str):
                        result = result["content"]
                    else:
                        result = str(result)

                result = (result or "").strip()
                if not result:
                    raise OvertliAPIError(
                        "Pollinations returned an empty text response.",
                        endpoint=config.pollinations.chat_endpoint,
                    )

                elapsed = time.monotonic() - started_at
                logger.info(
                    "Pollinations chat request completed in %.2fs (model=%s, chars=%s).",
                    elapsed,
                    model_name,
                    len(result),
                )

                logger.info("GZ_TextEnhancer generated %s chars with model '%s'.", len(result), model_name)
                return (result,)

        except requests.exceptions.Timeout as exc:
            timeout_message = build_user_facing_error(
                "Pollinations request timed out.",
                what_happened=f"No response was received within {timeout_seconds} seconds.",
                what_we_tried=(
                    f"Called {config.pollinations.chat_endpoint} with model '{model_name}' and compatibility fallback retries."
                ),
                next_steps=(
                    "Retry with a simpler prompt, switch to a lighter model, increase timeout via "
                    "GZ_POLLINATIONS_CHAT_TIMEOUT, or check Pollinations service health."
                ),
            )
            logger.error(timeout_message)
            raise OvertliTimeoutError(
                timeout_message,
                timeout_seconds=timeout_seconds,
                operation="pollinations chat completion",
            ) from exc
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            body = exc.response.text[:200] if exc.response is not None else str(exc)
            http_message = build_user_facing_error(
                "Pollinations API request failed.",
                what_happened=f"Provider returned HTTP {status}.",
                what_we_tried=(
                    f"Submitted chat payload to {config.pollinations.chat_endpoint} with model '{model_name}'."
                ),
                next_steps="Check model availability, API key validity/rate limits, and request payload size.",
                details=f"Response excerpt: {body}",
            )
            logger.error(http_message)
            raise OvertliAPIError(
                http_message,
                endpoint=config.pollinations.chat_endpoint,
                status_code=status,
            ) from exc
        except OvertliAPIError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Pollinations text request failed")
            fallback_message = build_user_facing_error(
                "Pollinations request failed.",
                what_happened=f"Unexpected error: {exc}",
                what_we_tried="Executed Pollinations chat request with compatibility fallback strategy.",
                next_steps="Review terminal logs for stack details and verify network/provider availability.",
            )
            raise OvertliAPIError(
                fallback_message,
                endpoint=config.pollinations.chat_endpoint,
            ) from exc
