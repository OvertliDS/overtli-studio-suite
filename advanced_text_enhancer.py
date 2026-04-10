# ============================================================================
# advanced_text_enhancer.py
# GZ_AdvancedTextEnhancer - Unified provider router
# ============================================================================
"""Unified provider router with modality-aware Pollinations dispatch."""

from __future__ import annotations

import base64
import io
import logging
import importlib
import os
import tempfile
from typing import Any, Optional, Tuple

from .base_node import GZBaseNode
from .audio_style_presets import (
    AUDIO_STYLE_OFF,
    get_advanced_audio_style_bundle_options,
    get_audio_style_options,
    resolve_advanced_audio_style_bundle,
)
from .exceptions import OvertliAPIError, OvertliConfigError, OvertliInputError, OvertliTimeoutError, OvertliVisionError
from .image_utils import binary_to_comfy_image, comfy_image_to_pil, validate_comfy_image
from .instruction_modes import (
    IMAGE_MODE_NAMES,
    SPEECH_TO_TEXT_MODE_NAMES,
    TEXT_MODE_NAMES,
    TEXT_TO_AUDIO_MODE_NAMES,
    TTS_MODE_NAMES,
    VIDEO_MODE_NAMES,
    resolve_mode_family_preset,
)
from .pollinations.model_catalog import (
    extract_display_model_name,
    fetch_pollinations_advanced_models,
    supports_pollinations_family,
)
from .prompt_styles import (
    STYLE_OFF_LABEL,
    append_style_layers_to_prompt,
    get_style_options,
    infer_mode_category,
    normalize_style_presets,
)
from .settings_store import resolve_config_value, save_persistent_settings
from .shared_utils import (
    build_user_facing_error,
    normalize_string_input,
    select_image_batch_indices,
    validate_single_image_source,
)
from .suite_config import get_config

logger = logging.getLogger(__name__)
requests = importlib.import_module("requests")

_PROVIDER_OPTIONS = [
    "pollinations",
    "lm_studio",
    "copilot",
    "openai_compatible",
]

_ACTIVE_ENGINE_OPTIONS = [
    "text",
    "image",
    "video",
    "text_to_speech",
    "speech_to_text",
    "text_to_music",
]

_TEXT_MODE_OPTIONS = list(TEXT_MODE_NAMES)
_IMAGE_MODE_OPTIONS = list(IMAGE_MODE_NAMES)
_VIDEO_MODE_OPTIONS = list(VIDEO_MODE_NAMES)
_TTS_MODE_OPTIONS = list(TTS_MODE_NAMES)
_STT_MODE_OPTIONS = list(SPEECH_TO_TEXT_MODE_NAMES)
_TTAUDIO_MODE_OPTIONS = list(TEXT_TO_AUDIO_MODE_NAMES)

_MODE_OPTIONS_BY_FAMILY = {
    "text": set(_TEXT_MODE_OPTIONS),
    "image": set(_IMAGE_MODE_OPTIONS),
    "video": set(_VIDEO_MODE_OPTIONS),
    "tts": set(_TTS_MODE_OPTIONS),
    "stt": set(_STT_MODE_OPTIONS),
    "ttaudio": set(_TTAUDIO_MODE_OPTIONS),
}

_ADVANCED_POLLINATIONS_DEFAULTS = {
    "text": "openai [text] [vision] [free]",
    "image": "flux [image-gen] [free]",
    "video": "wan [video-gen] [free]",
    "stt": "whisper [stt] [free]",
    "tts": "openai-audio [tts] [free]",
    "ttaudio": "openai-audio [ttaudio] [tts] [free]",
}

_DEFAULT_TEXT_MAX_TOKENS = 750


def _empty_image() -> Any:
    """Return a tiny blank ComfyUI IMAGE tensor for non-image execution paths."""
    try:
        torch = importlib.import_module("torch")

        return torch.zeros((1, 1, 1, 3), dtype=torch.float32)
    except Exception:
        # Fallback keeps routing stable even if torch is unavailable in editor-only contexts.
        return [[[[0.0, 0.0, 0.0]]]]


class GZ_AdvancedTextEnhancer:
    """Unified provider-aware router with explicit text/image/video/audio outputs."""

    CATEGORY = "OVERTLI STUDIO/LLM"
    FUNCTION = "execute"
    RETURN_TYPES = ("STRING", "IMAGE", "VIDEO", "AUDIO")
    RETURN_NAMES = ("text", "image", "video", "audio")

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        cfg = get_config()
        pollinations_models = fetch_pollinations_advanced_models()
        try:
            from .lm_studio_vision import get_cached_models

            lm_studio_models = get_cached_models()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to preload LM Studio models for advanced router: %s", exc)
            lm_studio_models = ["auto [local]"]

        return {
            "required": {
                "provider": (_PROVIDER_OPTIONS, {"default": "pollinations"}),
                "active_engine": (_ACTIVE_ENGINE_OPTIONS, {"default": "text"}),
                "prompt": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "placeholder": "Text prompt for text/image/video/tts/ttaudio. Leave blank only for STT if audio is supplied.",
                    },
                ),
            },
            "optional": {
                "text_mode": (_TEXT_MODE_OPTIONS, {"default": "Off"}),
                "image_mode": (_IMAGE_MODE_OPTIONS, {"default": "Off"}),
                "video_mode": (_VIDEO_MODE_OPTIONS, {"default": "Off"}),
                "tts_mode": (_TTS_MODE_OPTIONS, {"default": "Off"}),
                "stt_mode": (_STT_MODE_OPTIONS, {"default": "Off"}),
                "ttaudio_mode": (_TTAUDIO_MODE_OPTIONS, {"default": "Off"}),
                "pollinations_model": (
                    pollinations_models,
                    {"default": pollinations_models[0] if pollinations_models else "auto"},
                ),
                "lm_studio_model": (
                    lm_studio_models,
                    {"default": lm_studio_models[0] if lm_studio_models else "auto [local]"},
                ),
                "openai_model_override": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "placeholder": "Optional OpenAI-compatible model override",
                    },
                ),
                "image": ("IMAGE",),
                "audio": ("AUDIO",),
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
                "custom_instructions": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "forceInput": True,
                        "placeholder": "Optional custom instructions input",
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
                "tts_style_preset": (
                    get_audio_style_options("tts"),
                    {"default": AUDIO_STYLE_OFF},
                ),
                "stt_style_preset": (
                    get_audio_style_options("stt"),
                    {"default": AUDIO_STYLE_OFF},
                ),
                "ttaudio_style_preset": (
                    get_audio_style_options("ttaudio"),
                    {"default": AUDIO_STYLE_OFF},
                ),
                "advanced_audio_style_bundle": (
                    get_advanced_audio_style_bundle_options(),
                    {"default": AUDIO_STYLE_OFF},
                ),
                "temperature": (
                    "FLOAT",
                    {
                        "default": 0.7,
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
                "timeout_seconds": (
                    "INT",
                    {
                        "default": 120,
                        "min": 5,
                        "max": 1200,
                        "step": 5,
                    },
                ),
                "seed": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 0xffffffffffffffff,
                        "control_after_generate": True,
                    },
                ),
                "output_format": (["text", "json"], {"default": "text"}),
                "media_width": ("INT", {"default": 512, "min": 128, "max": 4096, "step": 32}),
                "media_height": ("INT", {"default": 512, "min": 128, "max": 4096, "step": 32}),
                "safe_mode": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "Safe Mode ON",
                        "label_off": "Safe Mode OFF",
                    },
                ),
                "no_logo": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "label_on": "No Logo ON",
                        "label_off": "No Logo OFF",
                    },
                ),
                "enhance_media_prompt": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "Enhance Prompt",
                        "label_off": "Raw Prompt",
                    },
                ),
                "stt_response_format": (["json", "text", "srt", "verbose_json", "vtt"], {"default": "text"}),
                "stt_language": (
                    ["auto", "en", "es", "pt", "fr", "de", "it", "nl", "ru", "ja", "ko", "zh", "ar", "hi"],
                    {"default": "auto"},
                ),
                "audio_response_format": (["mp3", "wav", "opus", "aac", "flac", "pcm"], {"default": "mp3"}),
                "audio_voice": (
                    [
                        "alloy",
                        "echo",
                        "fable",
                        "onyx",
                        "nova",
                        "shimmer",
                        "coral",
                        "verse",
                        "ballad",
                        "ash",
                        "sage",
                        "amuch",
                        "dan",
                    ],
                    {"default": "nova"},
                ),
                "audio_speed": ("FLOAT", {"default": 1.0, "min": 0.25, "max": 4.0, "step": 0.05}),
                "audio_duration": ("INT", {"default": 10, "min": 0, "max": 600, "step": 1}),
                "audio_instrumental": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "Instrumental ON",
                        "label_off": "Instrumental OFF",
                    },
                ),
                "api_key": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "placeholder": "Optional provider API key",
                    },
                ),
                "api_base_url": (
                    "STRING",
                    {
                        "default": cfg.openai_compatible.base_url,
                        "multiline": False,
                        "placeholder": "OpenAI-compatible base URL",
                    },
                ),
                "copilot_executable": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "placeholder": "Optional Copilot executable override",
                    },
                ),
                "persist_provider_settings": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "label_on": "Persist Settings",
                        "label_off": "Session Only",
                    },
                ),
            },
        }

    @staticmethod
    def _selected_pollinations_model(family: str, pollinations_model: str) -> str:
        if (pollinations_model or "").strip() and pollinations_model != "auto":
            return pollinations_model.strip()
        return _ADVANCED_POLLINATIONS_DEFAULTS[family]

    @staticmethod
    def _validate_pollinations_model_family(selected_model: str, family: str) -> None:
        support_state = supports_pollinations_family(selected_model, family)
        if support_state is None:
            logger.warning(
                "AdvancedTextEnhancer could not verify Pollinations model '%s' for family '%s'; allowing request.",
                selected_model,
                family,
            )
            return

        if support_state:
            return

        normalized_model = extract_display_model_name(selected_model) or selected_model
        raise OvertliInputError(
            (
                f"Pollinations model '{normalized_model}' is not compatible with '{family}' mode.\n"
                f"What happened: the selected model does not advertise {family} support in the live catalog.\n"
                "What we tried: we validated the selected model against the requested family before dispatch.\n"
                "What to do next: pick a model tagged for that family, or set pollinations_model to auto to use the recommended default."
            ),
            input_name="pollinations_model",
        )

    @staticmethod
    def _unsupported_provider_error(provider_name: str, family: str) -> None:
        raise OvertliInputError(
            (
                f"Provider '{provider_name}' does not currently expose '{family}' generation in AdvancedTextEnhancer.\n"
                f"What happened: {provider_name} only routes through text/vision text nodes here.\n"
                "What we tried: we checked the selected family before dispatching the request.\n"
                "What to do next: switch provider to 'pollinations' for image/video/stt/tts/ttaudio, or use the provider-specific node directly."
            ),
            input_name="provider",
        )

    def execute(
        self,
        provider: str,
        active_engine: str,
        prompt: str,
        text_mode: str = "Off",
        image_mode: str = "Off",
        video_mode: str = "Off",
        tts_mode: str = "Off",
        stt_mode: str = "Off",
        ttaudio_mode: str = "Off",
        pollinations_model: str = "auto",
        lm_studio_model: str = "auto [local]",
        openai_model_override: str = "",
        image: Optional[Any] = None,
        audio: Optional[Any] = None,
        vision_enabled: bool = True,
        batch_image_mode: str = "all_frames",
        max_batch_frames: int = 0,
        custom_instructions: Optional[str] = None,
        style_preset_1: str = STYLE_OFF_LABEL,
        style_preset_2: str = STYLE_OFF_LABEL,
        style_preset_3: str = STYLE_OFF_LABEL,
        additional_styles: str = "",
        tts_style_preset: str = AUDIO_STYLE_OFF,
        stt_style_preset: str = AUDIO_STYLE_OFF,
        ttaudio_style_preset: str = AUDIO_STYLE_OFF,
        advanced_audio_style_bundle: str = AUDIO_STYLE_OFF,
        temperature: float = 0.7,
        max_tokens: int = _DEFAULT_TEXT_MAX_TOKENS,
        timeout_seconds: int = 120,
        seed: int = -1,
        output_format: str = "text",
        media_width: int = 512,
        media_height: int = 512,
        safe_mode: bool = False,
        no_logo: bool = True,
        enhance_media_prompt: bool = False,
        stt_response_format: str = "text",
        stt_language: str = "auto",
        audio_response_format: str = "mp3",
        audio_voice: str = "nova",
        audio_speed: float = 1.0,
        audio_duration: int = 10,
        audio_instrumental: bool = False,
        api_key: str = "",
        api_base_url: str = "",
        copilot_executable: str = "",
        persist_provider_settings: bool = True,
    ) -> Tuple[str, Any, Any, Any]:
        provider_name = (provider or "pollinations").strip().lower()
        custom_instructions = (custom_instructions or "").strip()
        selected_engine = (active_engine or "text").strip().lower()
        engine_to_family = {
            "text": "text",
            "image": "image",
            "video": "video",
            "text_to_speech": "tts",
            "speech_to_text": "stt",
            "text_to_music": "ttaudio",
        }
        family = engine_to_family.get(selected_engine, "")
        if not family:
            raise OvertliInputError(
                f"Unsupported active_engine '{active_engine}'.",
                input_name="active_engine",
            )

        family_mode_map = {
            "text": text_mode,
            "image": image_mode,
            "video": video_mode,
            "tts": tts_mode,
            "stt": stt_mode,
            "ttaudio": ttaudio_mode,
        }
        candidate_mode = (family_mode_map.get(family) or "Off").strip()
        if candidate_mode not in _MODE_OPTIONS_BY_FAMILY[family]:
            raise OvertliInputError(
                f"Invalid {family} mode selection: '{candidate_mode}'",
                input_name=f"{family}_mode",
            )
        resolved_mode = candidate_mode

        effective_text_max_tokens = max(64, int(max_tokens or _DEFAULT_TEXT_MAX_TOKENS))
        blank_image = _empty_image()
        bundle_styles = resolve_advanced_audio_style_bundle(advanced_audio_style_bundle)
        resolved_tts_style = tts_style_preset if tts_style_preset != AUDIO_STYLE_OFF else bundle_styles.get("tts", AUDIO_STYLE_OFF)
        resolved_stt_style = stt_style_preset if stt_style_preset != AUDIO_STYLE_OFF else bundle_styles.get("stt", AUDIO_STYLE_OFF)
        resolved_ttaudio_style = (
            ttaudio_style_preset
            if ttaudio_style_preset != AUDIO_STYLE_OFF
            else bundle_styles.get("ttaudio", AUDIO_STYLE_OFF)
        )
        logger.info(
            "AdvancedTextEnhancer dispatching provider='%s' family='%s' override='%s'.",
            provider_name,
            family,
            (openai_model_override or "").strip(),
        )

        if provider_name == "pollinations":
            selected_model = self._selected_pollinations_model(family, pollinations_model)
            self._validate_pollinations_model_family(selected_model, family)

            if family == "text":
                from .pollinations.text_enhancer import GZ_TextEnhancer

                response = GZ_TextEnhancer().execute(
                    prompt=prompt,
                    text_mode_enabled=True,
                    text_mode=resolved_mode if resolved_mode != "Off" else "Off",
                    image_mode_enabled=False,
                    image_mode="Off",
                    video_mode_enabled=False,
                    video_mode="Off",
                    tts_mode_enabled=False,
                    tts_mode="Off",
                    model=selected_model,
                    vision_enabled=vision_enabled,
                    batch_image_mode=batch_image_mode,
                    max_batch_frames=max_batch_frames,
                    custom_instructions=custom_instructions,
                    style_preset_1=style_preset_1,
                    style_preset_2=style_preset_2,
                    style_preset_3=style_preset_3,
                    additional_styles=additional_styles,
                    temperature=temperature,
                    max_tokens=effective_text_max_tokens,
                    seed=seed,
                    api_key=api_key,
                    persist_api_key=persist_provider_settings,
                )[0]
                return (response, blank_image, None, None)

            if family == "image":
                from .pollinations.image_gen import GZ_ImageGen

                image_output = GZ_ImageGen().execute(
                    prompt=prompt,
                    mode_preset=resolved_mode,
                    model=selected_model,
                    width=media_width,
                    height=media_height,
                    image=image,
                    custom_instructions=custom_instructions,
                    style_preset_1=style_preset_1,
                    style_preset_2=style_preset_2,
                    style_preset_3=style_preset_3,
                    additional_styles=additional_styles,
                    enhance_prompt=enhance_media_prompt,
                    seed=seed,
                    safe_mode=safe_mode,
                    no_logo=no_logo,
                    api_key=api_key,
                    persist_api_key=persist_provider_settings,
                )[0]
                return ("Image generated successfully.", image_output, None, None)

            if family == "video":
                from .pollinations.video_gen import GZ_VideoGen

                video_output = GZ_VideoGen().execute(
                    prompt=prompt,
                    mode_preset=resolved_mode,
                    model=selected_model,
                    image=image,
                    custom_instructions=custom_instructions,
                    style_preset_1=style_preset_1,
                    style_preset_2=style_preset_2,
                    style_preset_3=style_preset_3,
                    additional_styles=additional_styles,
                    enhance_prompt=enhance_media_prompt,
                    width=media_width,
                    height=media_height,
                    seed=seed,
                    timeout_seconds=timeout_seconds,
                    api_key=api_key,
                    persist_api_key=persist_provider_settings,
                )[0]
                return ("Video generated successfully.", blank_image, video_output, None)

            if family == "stt":
                from .pollinations.speech_to_text import GZ_SpeechToText

                transcript = GZ_SpeechToText().execute(
                    model=selected_model,
                    mode_preset=resolved_mode,
                    response_format=stt_response_format,
                    audio=audio,
                    input_language=stt_language,
                    prompt=prompt,
                    stt_style_preset=resolved_stt_style,
                    temperature=0.5,
                    api_key=api_key,
                    persist_api_key=persist_provider_settings,
                )[0]
                return (transcript, blank_image, None, None)

            if family == "tts":
                from .pollinations.text_to_speech import GZ_TextToSpeech

                audio_output = GZ_TextToSpeech().execute(
                    text=prompt,
                    mode_preset=resolved_mode,
                    model=selected_model,
                    voice=audio_voice,
                    custom_instructions=custom_instructions,
                    tts_style_preset=resolved_tts_style,
                    format_script=enhance_media_prompt,
                    api_key=api_key,
                    persist_api_key=persist_provider_settings,
                )[0]
                return ("TTS audio generated.", blank_image, None, audio_output)

            if family == "ttaudio":
                from .pollinations.text_to_audio import GZ_TextToAudio

                audio_output = GZ_TextToAudio().execute(
                    text=prompt,
                    mode_preset=resolved_mode,
                    model=selected_model,
                    response_format=audio_response_format,
                    music_style_preset=resolved_ttaudio_style,
                    speed=audio_speed,
                    duration=audio_duration,
                    instrumental=audio_instrumental,
                    custom_instructions=custom_instructions,
                    api_key=api_key,
                    persist_api_key=persist_provider_settings,
                )[0]
                return ("Music generated.", blank_image, None, audio_output)

        if family != "text" and provider_name in {"lm_studio", "copilot"}:
            self._unsupported_provider_error(provider_name, family)

        if provider_name == "lm_studio":
            from .lm_studio_vision import GZ_LMStudioTextEnhancer

            selected_model = (lm_studio_model or "auto [local]").strip()
            response = GZ_LMStudioTextEnhancer().execute(
                prompt=prompt,
                text_mode_enabled=True,
                text_mode=resolved_mode if resolved_mode != "Off" else "Off",
                image_mode_enabled=False,
                image_mode="Off",
                video_mode_enabled=False,
                video_mode="Off",
                tts_mode_enabled=False,
                tts_mode="Off",
                model=selected_model,
                image=image,
                vision_enabled=vision_enabled,
                batch_image_mode=batch_image_mode,
                max_batch_frames=max_batch_frames,
                custom_instructions=custom_instructions,
                style_preset_1=style_preset_1,
                style_preset_2=style_preset_2,
                style_preset_3=style_preset_3,
                additional_styles=additional_styles,
                temperature=temperature,
                max_tokens=effective_text_max_tokens,
                timeout_seconds=timeout_seconds,
                api_key=api_key,
                persist_api_key=persist_provider_settings,
            )[0]
            return (response, blank_image, None, None)

        if provider_name == "copilot":
            from .copilot_agent import GZ_CopilotAgent

            selected_model = get_config().copilot.default_model.strip()
            response = GZ_CopilotAgent().execute(
                prompt=prompt,
                text_mode_enabled=True,
                text_mode=resolved_mode if resolved_mode != "Off" else "Off",
                image_mode_enabled=False,
                image_mode="Off",
                video_mode_enabled=False,
                video_mode="Off",
                tts_mode_enabled=False,
                tts_mode="Off",
                model=selected_model,
                image=image,
                copilot_executable=copilot_executable,
                persist_copilot_executable=persist_provider_settings,
                custom_instructions=custom_instructions,
                style_preset_1=style_preset_1,
                style_preset_2=style_preset_2,
                style_preset_3=style_preset_3,
                additional_styles=additional_styles,
                vision_enabled=vision_enabled,
                batch_image_mode=batch_image_mode,
                max_batch_frames=max_batch_frames,
                max_output_tokens=effective_text_max_tokens,
                output_format=output_format,
                timeout_seconds=timeout_seconds,
            )[0]
            return (response, blank_image, None, None)

        if provider_name == "openai_compatible":
            selected_model = (openai_model_override or get_config().openai_compatible.default_model).strip()
            family_to_engine = {
                "text": "text",
                "image": "image",
                "video": "video",
                "tts": "text_to_speech",
                "stt": "speech_to_text",
                "ttaudio": "text_to_music",
            }
            engine = family_to_engine.get(family, "text")
            response_text, response_image, response_video, response_audio = _OpenAICompatibleEngine().execute(
                active_engine=engine,
                mode_preset=resolved_mode,
                prompt=prompt,
                model=selected_model,
                image=image,
                audio=audio,
                vision_enabled=vision_enabled,
                batch_image_mode=batch_image_mode,
                max_batch_frames=max_batch_frames,
                custom_instructions=custom_instructions,
                style_preset_1=style_preset_1,
                style_preset_2=style_preset_2,
                style_preset_3=style_preset_3,
                additional_styles=additional_styles,
                api_base_url=api_base_url,
                api_key=api_key,
                persist_api_settings=persist_provider_settings,
                temperature=temperature,
                max_tokens=effective_text_max_tokens,
                timeout_seconds=timeout_seconds,
                media_width=media_width,
                media_height=media_height,
                audio_voice=audio_voice,
                audio_speed=audio_speed,
                audio_response_format=audio_response_format,
                stt_response_format=stt_response_format,
                stt_language=stt_language,
            )
            return (response_text, response_image, response_video, response_audio)

        raise ValueError(f"Unsupported provider '{provider_name}'. Expected one of: {', '.join(_PROVIDER_OPTIONS)}")


def _get_pil_image_module():
    return importlib.import_module("PIL.Image")


def _extract_text_content(value: Any) -> str:
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


def _prepare_image_data_url(image_tensor: Any, max_dimension: int) -> str:
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


class _OpenAICompatibleEngine(GZBaseNode):
    """Internal OpenAI-compatible multimodal engine used by GZ_AdvancedTextEnhancer."""

    @staticmethod
    def _write_stream_to_temp_audio(response: Any, requested_format: str) -> str:
        suffix = f".{requested_format}" if requested_format in {"mp3", "wav", "opus", "aac", "flac", "pcm"} else ".mp3"
        with tempfile.NamedTemporaryFile(prefix="overtli_openai_audio_", suffix=suffix, delete=False) as temp_file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    temp_file.write(chunk)
            return temp_file.name

    def execute(
        self,
        active_engine: str,
        mode_preset: str,
        prompt: str,
        model: str,
        image: Optional[Any] = None,
        file_path: str = "",
        audio: Optional[Any] = None,
        custom_instructions: str = "",
        style_preset_1: str = STYLE_OFF_LABEL,
        style_preset_2: str = STYLE_OFF_LABEL,
        style_preset_3: str = STYLE_OFF_LABEL,
        additional_styles: str = "",
        api_base_url: str = "",
        api_key: str = "",
        persist_api_settings: bool = True,
        temperature: float = 0.7,
        max_tokens: int = _DEFAULT_TEXT_MAX_TOKENS,
        timeout_seconds: int = 120,
        require_api_key: bool = True,
        max_image_dimension: int = 1280,
        vision_enabled: bool = True,
        batch_image_mode: str = "all_frames",
        max_batch_frames: int = 0,
        media_width: int = 1024,
        media_height: int = 1024,
        audio_voice: str = "nova",
        audio_speed: float = 1.0,
        audio_response_format: str = "mp3",
        stt_response_format: str = "text",
        stt_language: str = "auto",
    ) -> Tuple[str, Any, Any, Any]:
        cfg = get_config().openai_compatible

        runtime_base_url = normalize_string_input(api_base_url)
        runtime_api_key = normalize_string_input(api_key)
        runtime_model = normalize_string_input(model)
        selected_engine = (active_engine or "text").strip().lower()

        if persist_api_settings:
            updates: dict[str, str] = {}
            if runtime_base_url:
                updates["openai_compatible_base_url"] = runtime_base_url
            if runtime_api_key:
                updates["openai_compatible_api_key"] = runtime_api_key
            if runtime_model:
                updates["openai_compatible_model"] = runtime_model
            if updates:
                save_persistent_settings(updates, source="GZ_AdvancedTextEnhancer")

        resolved_base_url = resolve_config_value(
            "openai_compatible_base_url",
            runtime_base_url,
            default=cfg.base_url,
        ).rstrip("/")

        resolved_api_key = resolve_config_value(
            "openai_compatible_api_key",
            runtime_api_key,
            default=cfg.api_key or "",
        )

        resolved_model = normalize_string_input(
            resolve_config_value(
                "openai_compatible_model",
                runtime_model,
                default=cfg.default_model,
            )
        )

        if not resolved_model:
            raise OvertliConfigError(
                "OpenAI-compatible model is required for this node.",
                config_key="OPENAI_COMPAT_MODEL",
            )

        if require_api_key and not resolved_api_key:
            raise OvertliConfigError(
                "OpenAI-compatible API key is required but not provided",
                config_key="OPENAI_COMPAT_API_KEY",
            )

        timeout_seconds = self.clamp_timeout(timeout_seconds)
        headers = {"Content-Type": "application/json"}
        if resolved_api_key:
            headers["Authorization"] = f"Bearer {resolved_api_key}"

        source_type, source_value = validate_single_image_source(image_tensor=image, file_path=file_path)
        image_data_urls: list[str] = []
        if source_type != "none" and not vision_enabled:
            logger.info("Vision disabled; ignoring image context for OpenAI-compatible request.")
        elif source_type == "file":
            resolved_path = os.path.abspath(str(source_value))
            if not os.path.exists(resolved_path):
                raise OvertliInputError(
                    f"Provided file_path does not exist: {resolved_path}",
                    input_name="file_path",
                )
            image_data_urls = [
                _prepare_image_data_url_from_path(
                    resolved_path,
                    max_dimension=max_image_dimension,
                )
            ]
        elif source_type == "tensor":
            image_data_urls = _prepare_image_data_urls(
                image_tensor=image,
                max_dimension=max_image_dimension,
                batch_image_mode=batch_image_mode,
                max_batch_frames=max_batch_frames,
            )

        mode_category_map = {
            "text": "text",
            "image": "image",
            "video": "video",
            "text_to_speech": "tts",
            "speech_to_text": "speech_to_text",
            "text_to_music": "text_to_audio",
        }
        mode_category = mode_category_map.get(selected_engine, "text")

        # Keep grouped mode-family resolution path active for parity with other providers.
        _ = resolve_mode_family_preset(
            text_mode_enabled=mode_category == "text",
            text_mode=mode_preset,
            image_mode_enabled=mode_category == "image",
            image_mode=mode_preset,
            video_mode_enabled=mode_category == "video",
            video_mode=mode_preset,
            tts_mode_enabled=mode_category == "tts",
            tts_mode=mode_preset,
        )

        style_labels = normalize_style_presets(
            style_preset_1=style_preset_1,
            style_preset_2=style_preset_2,
            style_preset_3=style_preset_3,
        )

        user_prompt = normalize_string_input(prompt)
        if selected_engine == "text" and not user_prompt and image_data_urls:
            user_prompt = "Describe and analyze this image in detail."

        if selected_engine in {"text", "image", "text_to_speech", "text_to_music"}:
            user_prompt = self.require_prompt(user_prompt, input_name="prompt")

        mode_hint = infer_mode_category(mode_preset=mode_preset, fallback=mode_category)
        styled_prompt = append_style_layers_to_prompt(
            raw_prompt=user_prompt,
            style_labels=style_labels,
            mode_category=mode_hint,
            additional_styles=additional_styles,
        )

        blank_image = _empty_image()

        try:
            if selected_engine == "text":
                messages: list[dict[str, Any]] = []
                if custom_instructions.strip():
                    messages.append({"role": "system", "content": custom_instructions.strip()})

                if image_data_urls:
                    content: list[dict[str, Any]] = [{"type": "text", "text": styled_prompt}]
                    for image_data_url in image_data_urls:
                        content.append({"type": "image_url", "image_url": {"url": image_data_url}})
                    messages.append({"role": "user", "content": content})
                else:
                    messages.append({"role": "user", "content": styled_prompt})

                payload: dict[str, Any] = {
                    "model": resolved_model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                endpoint = f"{resolved_base_url}/chat/completions"
                response = requests.post(endpoint, json=payload, headers=headers, timeout=timeout_seconds)
                response.raise_for_status()
                data = response.json()
                if "choices" in data and isinstance(data["choices"], list) and data["choices"]:
                    content = data["choices"][0].get("message", {}).get("content", "")
                    result = _extract_text_content(content)
                else:
                    result = _extract_text_content(data.get("content", ""))
                result = (result or "").strip()
                if not result:
                    raise OvertliAPIError("OpenAI-compatible provider returned an empty response", endpoint=endpoint)
                return (result, blank_image, None, None)

            if selected_engine == "image":
                payload = {
                    "model": resolved_model,
                    "prompt": styled_prompt,
                    "size": f"{int(media_width)}x{int(media_height)}",
                }
                endpoint = f"{resolved_base_url}/images/generations"
                response = requests.post(endpoint, json=payload, headers=headers, timeout=timeout_seconds)
                response.raise_for_status()
                data = response.json()
                image_bytes: Optional[bytes] = None
                if isinstance(data, dict) and isinstance(data.get("data"), list) and data["data"]:
                    first = data["data"][0]
                    if isinstance(first, dict):
                        b64_payload = first.get("b64_json") or first.get("base64")
                        if isinstance(b64_payload, str) and b64_payload.strip():
                            image_bytes = base64.b64decode(b64_payload)
                        elif isinstance(first.get("url"), str) and first.get("url"):
                            image_fetch = requests.get(first["url"], timeout=timeout_seconds)
                            image_fetch.raise_for_status()
                            image_bytes = image_fetch.content

                if not image_bytes:
                    raise OvertliAPIError(
                        "OpenAI-compatible image endpoint did not return image data.",
                        endpoint=endpoint,
                    )
                return ("Image generated successfully.", binary_to_comfy_image(image_bytes), None, None)

            if selected_engine == "video":
                raise OvertliAPIError(
                    (
                        "Active engine 'video' is not available for generic OpenAI-compatible routing yet. "
                        "Use a provider-specific video node or switch active_engine."
                    ),
                    endpoint=f"{resolved_base_url}/videos",
                )

            if selected_engine in {"text_to_speech", "text_to_music"}:
                endpoint = f"{resolved_base_url}/audio/speech"
                payload = {
                    "model": resolved_model,
                    "input": styled_prompt,
                    "response_format": audio_response_format,
                    "speed": max(0.25, min(float(audio_speed), 4.0)),
                }
                if selected_engine == "text_to_speech":
                    payload["voice"] = (audio_voice or "nova").strip() or "nova"
                else:
                    payload["instrumental"] = True

                with requests.post(
                    endpoint,
                    json=payload,
                    headers=headers,
                    timeout=timeout_seconds,
                    stream=True,
                ) as response:
                    response.raise_for_status()
                    temp_audio = self._write_stream_to_temp_audio(response, audio_response_format)

                try:
                    from .pollinations.text_to_speech import _audio_path_to_output

                    audio_output = _audio_path_to_output(temp_audio)
                finally:
                    if os.path.exists(temp_audio):
                        os.remove(temp_audio)

                success_text = (
                    "Speech generated successfully."
                    if selected_engine == "text_to_speech"
                    else "Music generated successfully."
                )
                return (success_text, blank_image, None, audio_output)

            if selected_engine == "speech_to_text":
                if audio is None:
                    raise OvertliInputError(
                        "AUDIO input is required for speech_to_text engine.",
                        input_name="audio",
                    )

                from .pollinations.speech_to_text import _write_audio_input_to_temp_wav

                temp_audio = _write_audio_input_to_temp_wav(audio)
                endpoint = f"{resolved_base_url}/audio/transcriptions"
                data_payload: dict[str, Any] = {
                    "model": resolved_model,
                    "response_format": stt_response_format,
                    "temperature": max(0.0, min(float(temperature), 2.0)),
                }
                lang = (stt_language or "auto").strip().lower()
                if lang and lang != "auto":
                    data_payload["language"] = lang
                if styled_prompt.strip():
                    data_payload["prompt"] = styled_prompt.strip()

                try:
                    with open(temp_audio, "rb") as handle:
                        files = {
                            "file": (
                                os.path.basename(temp_audio),
                                handle,
                                "audio/wav",
                            )
                        }
                        response = requests.post(
                            endpoint,
                            files=files,
                            data=data_payload,
                            headers={"Authorization": headers["Authorization"]} if "Authorization" in headers else None,
                            timeout=timeout_seconds,
                        )
                    response.raise_for_status()
                finally:
                    if os.path.exists(temp_audio):
                        os.remove(temp_audio)

                content_type = (response.headers.get("content-type") or "").lower()
                if "json" in content_type:
                    payload = response.json()
                    transcript = payload.get("text") if isinstance(payload, dict) else ""
                    if not transcript:
                        transcript = str(payload)
                else:
                    transcript = (response.text or "").strip()

                transcript = transcript.strip()
                if not transcript:
                    raise OvertliAPIError(
                        "OpenAI-compatible STT returned an empty transcript.",
                        endpoint=endpoint,
                    )
                return (transcript, blank_image, None, None)

            raise OvertliInputError(
                f"Unsupported active_engine value: {selected_engine}",
                input_name="active_engine",
            )

        except requests.exceptions.Timeout as exc:
            timeout_message = build_user_facing_error(
                "OpenAI-compatible request timed out.",
                what_happened=f"No response was received within {timeout_seconds} seconds.",
                what_we_tried=(
                    f"Sent '{selected_engine}' request to {resolved_base_url} with model '{resolved_model}'."
                ),
                next_steps=(
                    "Increase timeout_seconds, reduce payload size, verify provider status, "
                    "or test the same endpoint with curl/Postman."
                ),
            )
            logger.error(timeout_message)
            raise OvertliTimeoutError(
                timeout_message,
                timeout_seconds=timeout_seconds,
                operation=f"openai-compatible {selected_engine}",
            ) from exc
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            body = exc.response.text[:300] if exc.response is not None else str(exc)
            api_error_message = build_user_facing_error(
                "OpenAI-compatible API request failed.",
                what_happened=f"Provider returned HTTP {status}.",
                what_we_tried=(
                    f"Called OpenAI-compatible endpoint for engine '{selected_engine}' with model '{resolved_model}'."
                ),
                next_steps=(
                    "Check API key permissions, model availability, rate limits, and request body format."
                ),
                details=f"Response excerpt: {body}",
            )
            logger.error(api_error_message)
            raise OvertliAPIError(
                api_error_message,
                endpoint=resolved_base_url,
                status_code=status,
            ) from exc
        except OvertliInputError:
            raise
        except OvertliVisionError:
            raise
        except OvertliConfigError:
            raise
        except OvertliAPIError:
            raise
        except Exception as exc:  # noqa: BLE001
            fallback_message = build_user_facing_error(
                "OpenAI-compatible request failed.",
                what_happened=f"Unexpected error: {exc}",
                what_we_tried=f"Provider call attempted via base URL {resolved_base_url}.",
                next_steps="Review terminal logs and verify endpoint compatibility.",
            )
            logger.exception("OpenAI-compatible unexpected error")
            raise OvertliAPIError(fallback_message, endpoint=resolved_base_url) from exc
