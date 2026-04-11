# ============================================================================
# advanced_text_enhancer.py
# GZ_AdvancedTextEnhancer - Unified provider router
# ============================================================================
"""Unified provider router with modality-aware Pollinations dispatch."""

from __future__ import annotations

import logging
from typing import Any, Optional, Tuple

from ...styles.audio_styles import (
    AUDIO_STYLE_OFF,
    get_advanced_audio_style_bundle_options,
    get_audio_style_options,
    resolve_advanced_audio_style_bundle,
)
from ...exceptions import OvertliInputError
from ...instruction_modes import resolve_mode_family_preset
from ...engine.pollinations.model_catalog import (
    extract_display_model_name,
    fetch_pollinations_advanced_models,
    supports_pollinations_family,
)
from ...styles import STYLE_OFF_LABEL, get_style_options
from ...settings_store import resolve_config_value
from ...suite_config import get_config
from ...engine.openai_compatible import _OpenAICompatibleEngine
from ...engine.copilot_agent import _build_model_options as _build_copilot_model_options
from .constants import (
    _ACTIVE_ENGINE_OPTIONS,
    _ADVANCED_POLLINATIONS_DEFAULTS,
    _DEFAULT_TEXT_MAX_TOKENS,
    _IMAGE_MODE_OPTIONS,
    _MODE_OPTIONS_BY_FAMILY,
    _PROVIDER_OPTIONS,
    _STT_MODE_OPTIONS,
    _TEXT_MODE_OPTIONS,
    _TTAUDIO_MODE_OPTIONS,
    _TTS_MODE_OPTIONS,
    _VIDEO_MODE_OPTIONS,
)
from .dispatch import dispatch_provider_route
from .routing import _normalize_active_engine_name, _normalize_provider_name, _validate_provider_engine

logger = logging.getLogger(__name__)

# UI label anchors kept local for test and tooling discoverability:
# text (pollinations, lm_studio, copilot, openai_compatible)
# image (pollinations, openai_compatible)
# video (pollinations, openai_compatible)
# Supported engines for provider
# GZ_OpenAICompatibleTextEnhancer dispatches from dispatch_provider_route.


class GZ_AdvancedTextEnhancer:
    """Unified provider-aware router with explicit text/image/video/audio outputs."""

    CATEGORY = "OVERTLI STUDIO/LLM"
    FUNCTION = "execute"
    RETURN_TYPES = ("STRING", "IMAGE", "VIDEO", "AUDIO")
    RETURN_NAMES = ("text", "image", "video", "audio")

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        pollinations_models = fetch_pollinations_advanced_models()
        copilot_models = _build_copilot_model_options()
        lm_studio_models: list[str]
        try:
            from ..llm_text_enhancer import node as _lm_studio_vision

            get_cached_models_fn = getattr(_lm_studio_vision, "get_cached_models", None)
            if not callable(get_cached_models_fn):
                raise AttributeError("get_cached_models is unavailable")
            models_value = get_cached_models_fn()
            if not isinstance(models_value, list):
                raise TypeError("get_cached_models returned non-list value")
            lm_studio_models = [str(item) for item in models_value if str(item).strip()]
            if not lm_studio_models:
                lm_studio_models = ["auto [local]"]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to preload LM Studio models for advanced router: %s", exc)
            lm_studio_models = ["auto [local]"]

        return {
            "required": {
                "provider": (_PROVIDER_OPTIONS, {"default": "pollinations"}),
                "active_engine": (_ACTIVE_ENGINE_OPTIONS, {"default": _ACTIVE_ENGINE_OPTIONS[0]}),
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
                "text_mode_enabled": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "Text Mode ON",
                        "label_off": "Text Mode OFF",
                    },
                ),
                "text_mode": (_TEXT_MODE_OPTIONS, {"default": "Off"}),
                "image_mode_enabled": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "Image Mode ON",
                        "label_off": "Image Mode OFF",
                    },
                ),
                "image_mode": (_IMAGE_MODE_OPTIONS, {"default": "Off"}),
                "video_mode_enabled": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "Video Mode ON",
                        "label_off": "Video Mode OFF",
                    },
                ),
                "video_mode": (_VIDEO_MODE_OPTIONS, {"default": "Off"}),
                "tts_mode_enabled": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "TTS Mode ON",
                        "label_off": "TTS Mode OFF",
                    },
                ),
                "tts_mode": (_TTS_MODE_OPTIONS, {"default": "Off"}),
                "stt_mode_enabled": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "STT Mode ON",
                        "label_off": "STT Mode OFF",
                    },
                ),
                "stt_mode": (_STT_MODE_OPTIONS, {"default": "Off"}),
                "ttaudio_mode_enabled": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "Text-to-Audio Mode ON",
                        "label_off": "Text-to-Audio Mode OFF",
                    },
                ),
                "ttaudio_mode": (_TTAUDIO_MODE_OPTIONS, {"default": "Off"}),
                "pollinations_model": (
                    pollinations_models,
                    {"default": pollinations_models[0] if pollinations_models else "auto"},
                ),
                "lm_studio_model": (
                    lm_studio_models,
                    {"default": lm_studio_models[0] if lm_studio_models else "auto [local]"},
                ),
                "copilot_model": (
                    copilot_models,
                    {"default": copilot_models[0] if copilot_models else "gpt-4.1"},
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
                        "default": "",
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

    def execute(
        self,
        provider: str,
        active_engine: str,
        prompt: str,
        text_mode_enabled: bool = False,
        text_mode: str = "Off",
        image_mode_enabled: bool = False,
        image_mode: str = "Off",
        video_mode_enabled: bool = False,
        video_mode: str = "Off",
        tts_mode_enabled: bool = False,
        tts_mode: str = "Off",
        stt_mode_enabled: bool = False,
        stt_mode: str = "Off",
        ttaudio_mode_enabled: bool = False,
        ttaudio_mode: str = "Off",
        pollinations_model: str = "auto",
        lm_studio_model: str = "auto [local]",
        copilot_model: str = "",
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
        provider_name = _normalize_provider_name(provider)
        custom_instructions = (custom_instructions or "").strip()
        selected_engine = _normalize_active_engine_name(active_engine)
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

        _validate_provider_engine(provider_name, selected_engine)

        family_mode_map = {
            "text": text_mode,
            "image": image_mode,
            "video": video_mode,
            "tts": tts_mode,
            "stt": stt_mode,
            "ttaudio": ttaudio_mode,
        }
        family_enabled_map = {
            "text": bool(text_mode_enabled),
            "image": bool(image_mode_enabled),
            "video": bool(video_mode_enabled),
            "tts": bool(tts_mode_enabled),
            "stt": bool(stt_mode_enabled),
            "ttaudio": bool(ttaudio_mode_enabled),
        }
        candidate_mode = (family_mode_map.get(family) or "Off").strip()
        if candidate_mode.lower() == "off":
            candidate_mode = "Off"

        if not family_enabled_map.get(family, True):
            candidate_mode = "Off"

        if candidate_mode not in _MODE_OPTIONS_BY_FAMILY[family]:
            raise OvertliInputError(
                f"Invalid {family} mode selection: '{candidate_mode}'",
                input_name=f"{family}_mode",
            )
        resolved_mode = candidate_mode

        effective_text_max_tokens = max(64, int(max_tokens or _DEFAULT_TEXT_MAX_TOKENS))
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
        logger.info(
            "AdvancedTextEnhancer mode resolved family='%s' enabled=%s mode='%s'.",
            family,
            family_enabled_map.get(family, True),
            resolved_mode,
        )
        return dispatch_provider_route(
            provider_name=provider_name,
            family=family,
            prompt=prompt,
            resolved_mode=resolved_mode,
            text_mode=text_mode,
            image_mode=image_mode,
            video_mode=video_mode,
            tts_mode=tts_mode,
            stt_mode=stt_mode,
            ttaudio_mode=ttaudio_mode,
            pollinations_model=pollinations_model,
            lm_studio_model=lm_studio_model,
            copilot_model=copilot_model,
            openai_model_override=openai_model_override,
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
            resolved_tts_style=resolved_tts_style,
            resolved_stt_style=resolved_stt_style,
            resolved_ttaudio_style=resolved_ttaudio_style,
            temperature=temperature,
            effective_text_max_tokens=effective_text_max_tokens,
            timeout_seconds=timeout_seconds,
            seed=seed,
            output_format=output_format,
            media_width=media_width,
            media_height=media_height,
            safe_mode=safe_mode,
            no_logo=no_logo,
            enhance_media_prompt=enhance_media_prompt,
            stt_response_format=stt_response_format,
            stt_language=stt_language,
            audio_response_format=audio_response_format,
            audio_voice=audio_voice,
            audio_speed=audio_speed,
            audio_duration=audio_duration,
            audio_instrumental=audio_instrumental,
            api_key=api_key,
            api_base_url=api_base_url,
            copilot_executable=copilot_executable,
            persist_provider_settings=persist_provider_settings,
            selected_pollinations_model=self._selected_pollinations_model,
            validate_pollinations_model_family=self._validate_pollinations_model_family,
        )



