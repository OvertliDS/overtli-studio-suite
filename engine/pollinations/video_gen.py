# ============================================================================
# pollinations/video_gen.py
# GZ_VideoGen - Synchronous video generation via Pollinations.ai
# ============================================================================
"""
GZ_VideoGen: Pollinations Video Generation Node
================================================
Uses video models via gen.pollinations.ai/video endpoint.

⚠️ IMPORTANT: Video generation is SYNCHRONOUS and can take 60-180+ seconds.
This WILL block the ComfyUI UI during generation.

Features:
- Video-specific mode presets
- Optional init image for Image-to-Video
- Long timeout handling with progress indication
- Returns native ComfyUI VIDEO output
"""

import logging
import importlib
import os
import tempfile
import time
import urllib.parse
from typing import Any, Optional, Tuple

requests = importlib.import_module("requests")

from ...exceptions import OvertliAPIError, OvertliInputError, OvertliTimeoutError
from ...instruction_modes import get_video_gen_modes, resolve_mode_preset
from ...styles import (
    STYLE_OFF_LABEL,
    append_style_layers_to_prompt,
    get_style_options,
    normalize_style_presets,
)
from ...shared_utils import build_user_facing_error
from .compat_retry import execute_with_compat_retry
from .media_upload import resolve_reference_image_value
from .model_catalog import fetch_pollinations_modality_models
from ...settings_store import resolve_config_value, save_persistent_settings
from ...suite_config import get_config

logger = logging.getLogger(__name__)

_VIDEO_TEMP_PREFIX = "overtli_pollinations_video_"
_VIDEO_TEMP_MAX_AGE_SECONDS = 60 * 60 * 24


# ============================================================================
# Video Model List
# ============================================================================

DEFAULT_VIDEO_MODELS = [
    "wan [free]",
    "wan-fast [free]",
    "ltx-2 [free]",
    "veo [paid]",
    "seedance [free]",
    "grok-video-pro [paid]",
]


def _cleanup_stale_video_temp_files(temp_dir: str, *, max_age_seconds: int = _VIDEO_TEMP_MAX_AGE_SECONDS) -> int:
    """Delete stale Pollinations video temp files to avoid temp-directory bloat."""
    now = time.time()
    removed = 0

    try:
        for entry in os.scandir(temp_dir):
            if not entry.is_file():
                continue
            if not entry.name.startswith(_VIDEO_TEMP_PREFIX) or not entry.name.endswith(".mp4"):
                continue

            try:
                age_seconds = now - entry.stat().st_mtime
                if age_seconds < max_age_seconds:
                    continue
                os.remove(entry.path)
                removed += 1
            except FileNotFoundError:
                continue
            except Exception as exc:  # noqa: BLE001
                logger.warning("Unable to remove stale Pollinations video temp file '%s': %s", entry.path, exc)
    except FileNotFoundError:
        return 0
    except Exception as exc:  # noqa: BLE001
        logger.warning("Unable to scan temp directory '%s' for stale Pollinations video files: %s", temp_dir, exc)
        return 0

    if removed:
        logger.info("Removed %s stale Pollinations video temp file(s).", removed)
    return removed


# ============================================================================
# GZ_VideoGen Node
# ============================================================================


class GZ_VideoGen:
    """
    Pollinations Video Generation Node

    ⚠️ WARNING: Video generation is SYNCHRONOUS.
    Generation typically takes 60-180 seconds.
    ComfyUI UI WILL be unresponsive during this time.
    """

    CATEGORY = "OVERTLI STUDIO/Media"
    FUNCTION = "execute"
    RETURN_TYPES = ("VIDEO",)
    RETURN_NAMES = ("video",)
    OUTPUT_NODE = False

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        model_options = fetch_pollinations_modality_models("video", DEFAULT_VIDEO_MODELS)
        return {
            "required": {
                "prompt": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "placeholder": "Describe the video scene with motion and camera movement...",
                    },
                ),
                "mode_preset": (list(get_video_gen_modes().keys()), {"default": "Off"}),
                "model": (
                    model_options,
                    {"default": model_options[0] if model_options else "wan-fast [free]"},
                ),
            },
            "optional": {
                "image": ("IMAGE",),  # Optional image input for image-to-video
                "custom_instructions": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "forceInput": True,
                        "placeholder": "Custom video prompt instructions...",
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
                "enhance_prompt": (
                    "BOOLEAN",
                    {"default": False, "label_on": "Auto-Enhance ON", "label_off": "Raw Prompt"},
                ),
                "width": ("INT", {"default": 512, "min": 256, "max": 1280, "step": 64}),
                "height": ("INT", {"default": 512, "min": 256, "max": 1280, "step": 64}),
                "seed": ("INT", {"default": -1, "min": -1, "max": 2147483647}),
                "timeout_seconds": ("INT", {"default": 300, "min": 60, "max": 600, "step": 30}),
                "api_key": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "placeholder": "Optional Pollinations API key...",
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
        mode_preset: str,
        model: str,
        image: Optional[Any] = None,
        custom_instructions: str = "",
        style_preset_1: str = STYLE_OFF_LABEL,
        style_preset_2: str = STYLE_OFF_LABEL,
        style_preset_3: str = STYLE_OFF_LABEL,
        additional_styles: str = "",
        enhance_prompt: bool = False,
        width: int = 512,
        height: int = 512,
        seed: int = -1,
        timeout_seconds: int = 300,
        api_key: str = "",
        persist_api_key: bool = False,
    ) -> Tuple[Any]:
        """Execute video generation via Pollinations API."""

        # Extract raw model name from display text
        model_name = model.split(" [", 1)[0].strip() if model else "wan-fast"
        cfg = get_config().pollinations

        if api_key and persist_api_key:
            save_persistent_settings(
                {"pollinations_api_key": api_key},
                source="GZ_VideoGen",
            )

        effective_api_key = resolve_config_value(
            "pollinations_api_key",
            api_key,
            default=(cfg.api_key or ""),
        )

        headers: dict[str, str] = {}
        if effective_api_key:
            headers["Authorization"] = f"Bearer {effective_api_key}"
            headers["x-api-key"] = effective_api_key

        final_prompt = (prompt or "").strip()
        style_labels = normalize_style_presets(
            style_preset_1=style_preset_1,
            style_preset_2=style_preset_2,
            style_preset_3=style_preset_3,
        )

        if enhance_prompt:
            instructions = resolve_mode_preset(
                mode_preset=mode_preset,
                custom_instructions=custom_instructions,
                mode_category_hint="video",
            )
            if not instructions:
                instructions = (
                    "Transform this into a cinematic video prompt with smooth camera movements, "
                    "dynamic action, and atmospheric lighting. Describe motion explicitly."
                )

            enhance_payload = {
                "model": "openai-fast",
                "messages": [
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": prompt or ""},
                ],
                "temperature": 0.8,
            }

            try:
                resp = requests.post(
                    cfg.chat_endpoint,
                    json=enhance_payload,
                    headers=headers if headers else None,
                    timeout=30,
                )
                if resp.ok:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        final_prompt = (choices[0].get("message", {}).get("content", final_prompt) or "").strip()
                        logger.info("GZ_VideoGen: Enhanced prompt to %s chars", len(final_prompt))
            except Exception as exc:  # noqa: BLE001
                logger.warning("GZ_VideoGen: Prompt enhancement failed: %s", exc)

        if not final_prompt:
            raise OvertliInputError(
                "Prompt cannot be empty for video generation.",
                input_name="prompt",
            )

        final_prompt = append_style_layers_to_prompt(
            raw_prompt=final_prompt,
            style_labels=style_labels,
            mode_category="video",
            additional_styles=additional_styles,
        )

        # Build generation URL
        encoded_prompt = urllib.parse.quote((final_prompt or "")[:1500], safe="")
        url = f"{cfg.video_endpoint}/{encoded_prompt}"

        params: dict[str, Any] = {
            "model": model_name,
            "width": width,
            "height": height,
            "nologo": "true",
        }
        if seed >= 0:
            params["seed"] = seed

        # Optional init image forwarding for image-to-video capable backends.
        if image is not None:
            params["image"] = resolve_reference_image_value(
                image=image,
                api_key=effective_api_key,
                logger=logger,
                context_label="video-generation",
            )

        logger.info(
            "GZ_VideoGen: starting synchronous video generation (timeout=%ss).",
            timeout_seconds,
        )
        logger.info("GZ_VideoGen: ComfyUI may appear busy while the synchronous request is running.")

        try:
            started_at = time.monotonic()
            response = execute_with_compat_retry(
                send_request=lambda req_params, _req_payload: requests.get(
                    url,
                    params=req_params,
                    headers=headers if headers else None,
                    timeout=timeout_seconds,
                    stream=True,
                ),
                endpoint=url,
                model_name=model_name,
                logger=logger,
                params=params,
                optional_param_keys={"seed", "nologo"},
                max_attempts=3,
            )

            with response:
                content_type = response.headers.get("content-type", "")
                if "video" not in content_type and "application/octet-stream" not in content_type:
                    preview = response.text[:200] if hasattr(response, "text") else ""
                    raise OvertliAPIError(f"Expected video response, got '{content_type}'. {preview}")

                temp_dir = tempfile.gettempdir()
                os.makedirs(temp_dir, exist_ok=True)
                _cleanup_stale_video_temp_files(temp_dir)
                with tempfile.NamedTemporaryFile(
                    prefix=_VIDEO_TEMP_PREFIX,
                    suffix=".mp4",
                    delete=False,
                    dir=temp_dir,
                ) as tmp:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            tmp.write(chunk)
                    video_path = tmp.name

                elapsed = time.monotonic() - started_at
                logger.info(
                    "Pollinations video request completed in %.2fs (model=%s).",
                    elapsed,
                    model_name,
                )
                logger.info("GZ_VideoGen: Saved video to %s", video_path)
                video_types_module = importlib.import_module("comfy_api.latest._input_impl.video_types")
                video_type = getattr(video_types_module, "VideoFromFile")
                return (video_type(video_path),)

        except requests.exceptions.Timeout as exc:
            timeout_message = build_user_facing_error(
                "Pollinations video generation timed out.",
                what_happened=f"No video response was received within {timeout_seconds} seconds.",
                what_we_tried=(
                    f"Requested model '{model_name}' at {width}x{height} with synchronous streaming generation."
                ),
                next_steps=(
                    "Use a simpler prompt, shorter sequence, lower resolution, or increase timeout_seconds."
                ),
            )
            logger.error(timeout_message)
            raise OvertliTimeoutError(
                timeout_message,
                timeout_seconds=timeout_seconds,
                operation="video_generation",
            ) from exc
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            body = exc.response.text[:200] if exc.response is not None else str(exc)
            http_message = build_user_facing_error(
                "Pollinations video API request failed.",
                what_happened=f"Provider returned HTTP {status}.",
                what_we_tried=f"Called endpoint {url} with model '{model_name}'.",
                next_steps="Check API key limits, model availability, and prompt constraints.",
                details=f"Response excerpt: {body}",
            )
            logger.error(http_message)
            raise OvertliAPIError(http_message, endpoint=url, status_code=status) from exc
        except OvertliAPIError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Pollinations video generation failed")
            fallback_message = build_user_facing_error(
                "Pollinations video generation failed.",
                what_happened=f"Unexpected error: {exc}",
                what_we_tried="Executed video request with compatibility fallback logic.",
                next_steps="Review terminal logs and verify provider/network health.",
            )
            raise OvertliAPIError(fallback_message, endpoint=url) from exc


