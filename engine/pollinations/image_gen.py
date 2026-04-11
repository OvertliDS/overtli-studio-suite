# ============================================================================
# pollinations/image_gen.py
# GZ_ImageGen - Image generation via Pollinations.ai (returns binary)
# ============================================================================
"""
GZ_ImageGen: Pollinations Image Generation Node
================================================
Uses gen.pollinations.ai/image/{encoded_prompt} which returns BINARY image data.

Features:
- Curated image-specific mode dropdown (not inclusive)
- Built-in prompt enhancement option
- Supports img2img via reference image
- Returns ComfyUI IMAGE tensor
"""

import logging
import importlib
import os
import time
import urllib.parse
from typing import Any, Optional, Tuple

requests = importlib.import_module("requests")

from ...exceptions import OvertliAPIError, OvertliInputError, OvertliTimeoutError
from ...image_utils import binary_to_comfy_image
from ...styles import (
    STYLE_OFF_LABEL,
    append_style_layers_to_prompt,
    get_style_options,
    normalize_style_presets,
)
from .compat_retry import execute_with_compat_retry
from .media_upload import resolve_reference_image_value
from .model_catalog import fetch_pollinations_modality_models
from ...settings_store import resolve_config_value, save_persistent_settings
from ...shared_utils import build_prompt, build_user_facing_error
from ...suite_config import get_config

logger = logging.getLogger(__name__)


# ============================================================================
# Image Model List (Curated)
# ============================================================================

DEFAULT_IMAGE_MODELS = [
    "flux [free]",
    "flux-pro [paid]",
    "flux-realism [free]",
    "flux-anime [free]",
    "flux-3d [free]",
    "flux-cablyai [free]",
    "turbo [free]",
    "zimage [free]",
    "gptimage [paid] [img2img]",
    "nanobanana [free]",
    "kontext [free] [img2img]",
    "wan-image [free]",
]


# ============================================================================
# GZ_ImageGen Node
# ============================================================================


class GZ_ImageGen:
    """
    Pollinations Image Generation Node

    Key differences from TextEnhancer:
    - Uses IMAGE-SPECIFIC mode presets (not inclusive)
    - Has built-in "Visual Mode" for auto-enhancement
    - Returns IMAGE tensor (not STRING)
    - Handles binary response from gen.pollinations.ai/image
    """

    CATEGORY = "OVERTLI STUDIO/Media"
    FUNCTION = "execute"
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        from ...instruction_modes import get_image_gen_modes

        image_gen_modes = get_image_gen_modes()
        mode_names = list(image_gen_modes.keys())
        model_options = fetch_pollinations_modality_models("image", DEFAULT_IMAGE_MODELS)

        return {
            "required": {
                "prompt": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "placeholder": "Describe the image you want to generate...",
                    },
                ),
                "mode_preset": (mode_names, {"default": "Off"}),
                "model": (
                    model_options,
                    {"default": model_options[0] if model_options else "flux [free]"},
                ),
                "width": ("INT", {"default": 1024, "min": 256, "max": 2048, "step": 64}),
                "height": ("INT", {"default": 1024, "min": 256, "max": 2048, "step": 64}),
            },
            "optional": {
                "image": ("IMAGE",),  # Optional image input for img2img models
                "custom_instructions": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "forceInput": True,
                        "placeholder": "Custom instructions for prompt enhancement...",
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
                "seed": ("INT", {"default": -1, "min": -1, "max": 2147483647}),
                "safe_mode": ("BOOLEAN", {"default": False, "label_on": "Safe Mode ON", "label_off": "Safe Mode OFF"}),
                "no_logo": ("BOOLEAN", {"default": True, "label_on": "No Logo", "label_off": "With Logo"}),
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
        width: int,
        height: int,
        image: Optional[Any] = None,
        custom_instructions: str = "",
        style_preset_1: str = STYLE_OFF_LABEL,
        style_preset_2: str = STYLE_OFF_LABEL,
        style_preset_3: str = STYLE_OFF_LABEL,
        additional_styles: str = "",
        enhance_prompt: bool = False,
        seed: int = -1,
        safe_mode: bool = False,
        no_logo: bool = True,
        api_key: str = "",
        persist_api_key: bool = False,
    ) -> Tuple[Any]:
        """Execute image generation via Pollinations API."""

        # Extract model name
        model_name = model.split(" [", 1)[0].strip() if model else "flux"
        model_supports_img2img = "[img2img]" in (model or "")

        # Build final prompt using 3-Layer Stack with optional enhancement behavior
        style_labels = normalize_style_presets(
            style_preset_1=style_preset_1,
            style_preset_2=style_preset_2,
            style_preset_3=style_preset_3,
        )

        if enhance_prompt:
            final_prompt = build_prompt(
                mode_preset=mode_preset,
                custom_instructions=custom_instructions,
                raw_prompt=prompt,
                mode_category="image",
                style_preset_1=style_preset_1,
                style_preset_2=style_preset_2,
                style_preset_3=style_preset_3,
                additional_styles=additional_styles,
            )
            if not final_prompt.strip():
                final_prompt = prompt
        else:
            final_prompt = append_style_layers_to_prompt(
                raw_prompt=(prompt or "").strip(),
                style_labels=style_labels,
                mode_category="image",
                additional_styles=additional_styles,
            )

        final_prompt = (final_prompt or "").strip()
        if not final_prompt:
            raise OvertliInputError(
                "Prompt cannot be empty for image generation.",
                input_name="prompt",
            )

        # Validate reference image compatibility for img2img.
        if image is not None:
            if not model_supports_img2img:
                raise OvertliInputError(
                    (
                        f"Image input is not supported by the selected Pollinations image model '{model_name}'.\n"
                        "What happened: an image input was provided for a model that is not tagged [img2img].\n"
                        "What we tried: we checked the selected model tags before sending the request.\n"
                        "What to do next: choose a model tagged [img2img] such as gptimage or kontext, or remove the image input."
                    ),
                    input_name="image",
                )

        # Build image generation URL
        config = get_config()

        if api_key and persist_api_key:
            save_persistent_settings(
                {"pollinations_api_key": api_key},
                source="GZ_ImageGen",
            )

        effective_api_key = resolve_config_value(
            "pollinations_api_key",
            api_key,
            default=(config.pollinations.api_key or ""),
        )

        encoded_prompt = urllib.parse.quote((final_prompt or "")[:2000], safe="")
        url = f"{config.pollinations.image_endpoint}/{encoded_prompt}"

        params: dict[str, Any] = {
            "model": model_name,
            "width": width,
            "height": height,
            "nologo": str(no_logo).lower(),
            "safe": str(safe_mode).lower(),
        }

        if seed >= 0:
            params["seed"] = seed
        if enhance_prompt:
            params["enhance"] = "true"

        if image is not None:
            params["image"] = resolve_reference_image_value(
                image=image,
                api_key=effective_api_key,
                logger=logger,
                context_label="image-generation",
            )

        headers: dict[str, str] = {}
        if effective_api_key:
            headers["Authorization"] = f"Bearer {effective_api_key}"
            headers["x-api-key"] = effective_api_key

        # Make request - returns BINARY
        try:
            timeout_seconds = max(5, int(config.pollinations.image_timeout or 60))
            logger.info(
                "Pollinations image request started (model=%s, endpoint=%s, timeout=%ss, size=%sx%s).",
                model_name,
                url,
                timeout_seconds,
                width,
                height,
            )
            started_at = time.monotonic()
            response = execute_with_compat_retry(
                send_request=lambda req_params, _req_payload: requests.get(
                    url,
                    params=req_params,
                    headers=headers if headers else None,
                    timeout=timeout_seconds,
                ),
                endpoint=url,
                model_name=model_name,
                logger=logger,
                params=params,
                optional_param_keys={"seed", "enhance", "safe", "nologo"},
                max_attempts=3,
            )

            with response:
                # Verify we got an image
                content_type = response.headers.get("content-type", "")
                if "image" not in content_type:
                    raise OvertliAPIError(f"Expected image, got {content_type}: {response.text[:200]}")

                # Convert binary to ComfyUI tensor
                image_tensor = binary_to_comfy_image(response.content)
                elapsed = time.monotonic() - started_at
                logger.info(
                    "Pollinations image request completed in %.2fs (model=%s).",
                    elapsed,
                    model_name,
                )
                logger.info("GZ_ImageGen: Generated %s image with %s", tuple(image_tensor.shape), model_name)
                return (image_tensor,)

        except requests.exceptions.Timeout as exc:
            timeout_message = build_user_facing_error(
                "Pollinations image generation timed out.",
                what_happened=(
                    f"No image response was received within {max(5, int(config.pollinations.image_timeout or 60))} seconds."
                ),
                what_we_tried=f"Requested model '{model_name}' at resolution {width}x{height}.",
                next_steps="Try smaller dimensions, a lighter model, or increase GZ_POLLINATIONS_IMAGE_TIMEOUT.",
            )
            logger.error(timeout_message)
            raise OvertliTimeoutError(
                timeout_message,
                timeout_seconds=max(5, int(config.pollinations.image_timeout or 60)),
                operation="pollinations image generation",
            ) from exc
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            body = exc.response.text[:200] if exc.response is not None else str(exc)
            http_message = build_user_facing_error(
                "Pollinations image API request failed.",
                what_happened=f"Provider returned HTTP {status}.",
                what_we_tried=(
                    f"Called endpoint {url} with model '{model_name}' and compatibility fallback retries."
                ),
                next_steps="Check prompt complexity, API key limits, and model availability.",
                details=f"Response excerpt: {body}",
            )
            logger.error(http_message)
            raise OvertliAPIError(http_message, endpoint=url, status_code=status) from exc
        except OvertliAPIError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Pollinations image generation failed")
            fallback_message = build_user_facing_error(
                "Pollinations image generation failed.",
                what_happened=f"Unexpected error: {exc}",
                what_we_tried="Executed image request with compatibility fallback logic.",
                next_steps="Review terminal logs and verify network/provider status.",
            )
            raise OvertliAPIError(fallback_message, endpoint=url) from exc


