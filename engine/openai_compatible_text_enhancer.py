"""
Dedicated OpenAI-compatible all-engines node.

This node exposes engine selection for text, image, video, text-to-speech,
speech-to-text, and text-to-music generation via OpenAI-compatible APIs.

Core execution is delegated to the shared internal engine implementation used
by the Advanced router so behavior stays consistent across both nodes.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Tuple

from .openai_compatible import _OpenAICompatibleEngine
from ..exceptions import OvertliInputError
from ..instruction_modes import (
    IMAGE_MODE_NAMES,
    SPEECH_TO_TEXT_MODE_NAMES,
    TEXT_MODE_NAMES,
    TEXT_TO_AUDIO_MODE_NAMES,
    TTS_MODE_NAMES,
    VIDEO_MODE_NAMES,
)
from ..styles import STYLE_OFF_LABEL, get_style_options
from ..suite_config import get_config

logger = logging.getLogger(__name__)

_ENGINE_OPTIONS = [
    "text",
    "image_gen",
    "video_gen",
    "text_to_speech_gen",
    "speech_to_text_gen",
    "text_to_music_gen",
]

_ENGINE_OPTION_TO_VALUE = {
    "text": "text",
    "image_gen": "image",
    "video_gen": "video",
    "text_to_speech_gen": "text_to_speech",
    "speech_to_text_gen": "speech_to_text",
    "text_to_music_gen": "text_to_music",
}

_MODE_OPTIONS_BY_FAMILY = {
    "text": set(TEXT_MODE_NAMES),
    "image": set(IMAGE_MODE_NAMES),
    "video": set(VIDEO_MODE_NAMES),
    "tts": set(TTS_MODE_NAMES),
    "stt": set(SPEECH_TO_TEXT_MODE_NAMES),
    "ttaudio": set(TEXT_TO_AUDIO_MODE_NAMES),
}


def _normalize_openai_engine(active_engine: str) -> str:
    """Normalize engine aliases to canonical internal engine values."""
    normalized = (active_engine or "text").strip().lower().replace("-", "_")
    if normalized in _ENGINE_OPTION_TO_VALUE:
        return _ENGINE_OPTION_TO_VALUE[normalized]

    alias_map = {
        "text": "text",
        "image": "image",
        "video": "video",
        "text_to_speech": "text_to_speech",
        "speech_to_text": "speech_to_text",
        "text_to_music": "text_to_music",
        "tts": "text_to_speech",
        "stt": "speech_to_text",
    }
    if normalized in alias_map:
        return alias_map[normalized]

    raise OvertliInputError(
        (
            f"Unsupported active_engine '{active_engine}'. Supported values: "
            f"{', '.join(_ENGINE_OPTIONS)}."
        ),
        input_name="active_engine",
    )


class GZ_OpenAICompatibleTextEnhancer(_OpenAICompatibleEngine):
    """OpenAI-compatible node with explicit engine selection across all modalities."""

    CATEGORY = "OVERTLI STUDIO/LLM"
    FUNCTION = "execute"
    RETURN_TYPES = ("STRING", "IMAGE", "VIDEO", "AUDIO")
    RETURN_NAMES = ("text", "image", "video", "audio")

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        cfg = get_config().openai_compatible
        return {
            "required": {
                "active_engine": (_ENGINE_OPTIONS, {"default": "text"}),
                "prompt": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "placeholder": "Prompt text. For speech_to_text_gen, AUDIO input may be used with optional prompt.",
                    },
                ),
                "model": (
                    "STRING",
                    {
                        "default": cfg.default_model,
                        "multiline": False,
                        "placeholder": "Model id (for example gpt-4.1-mini or provider-specific compatible id)",
                    },
                ),
            },
            "optional": {
                "text_mode": (list(TEXT_MODE_NAMES), {"default": "Off"}),
                "image_mode": (list(IMAGE_MODE_NAMES), {"default": "Off"}),
                "video_mode": (list(VIDEO_MODE_NAMES), {"default": "Off"}),
                "tts_mode": (list(TTS_MODE_NAMES), {"default": "Off"}),
                "stt_mode": (list(SPEECH_TO_TEXT_MODE_NAMES), {"default": "Off"}),
                "ttaudio_mode": (list(TEXT_TO_AUDIO_MODE_NAMES), {"default": "Off"}),
                "image": ("IMAGE",),
                "file_path": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "placeholder": "Optional local image path",
                    },
                ),
                "audio": ("AUDIO",),
                "custom_instructions": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "placeholder": "Optional system/custom instructions",
                    },
                ),
                "style_preset_1": (get_style_options(), {"default": STYLE_OFF_LABEL}),
                "style_preset_2": (get_style_options(), {"default": STYLE_OFF_LABEL}),
                "style_preset_3": (get_style_options(), {"default": STYLE_OFF_LABEL}),
                "additional_styles": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "placeholder": "Optional style stack text",
                    },
                ),
                "api_base_url": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "placeholder": "Optional OpenAI-compatible base URL override (blank = configured default)",
                    },
                ),
                "api_key": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "placeholder": "Optional API key",
                    },
                ),
                "persist_api_settings": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "label_on": "Persist Settings",
                        "label_off": "Session Only",
                    },
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
                        "default": 750,
                        "min": 64,
                        "max": 32768,
                        "step": 64,
                    },
                ),
                "timeout_seconds": (
                    "INT",
                    {
                        "default": cfg.timeout,
                        "min": 5,
                        "max": 1200,
                        "step": 5,
                    },
                ),
                "require_api_key": (
                    "BOOLEAN",
                    {
                        "default": cfg.require_api_key,
                        "label_on": "Require API Key",
                        "label_off": "Allow Anonymous",
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
                "media_width": ("INT", {"default": 1024, "min": 128, "max": 4096, "step": 32}),
                "media_height": ("INT", {"default": 1024, "min": 128, "max": 4096, "step": 32}),
                "audio_voice": (
                    "STRING",
                    {
                        "default": "nova",
                        "multiline": False,
                        "placeholder": "Voice id for text_to_speech_gen",
                    },
                ),
                "audio_speed": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": 0.25,
                        "max": 4.0,
                        "step": 0.05,
                    },
                ),
                "audio_response_format": (["mp3", "wav", "opus", "aac", "flac", "pcm"], {"default": "mp3"}),
                "stt_response_format": (["json", "text", "srt", "verbose_json", "vtt"], {"default": "text"}),
                "stt_language": (
                    ["auto", "en", "es", "pt", "fr", "de", "it", "nl", "ru", "ja", "ko", "zh", "ar", "hi"],
                    {"default": "auto"},
                ),
            },
        }

    def execute(
        self,
        active_engine: str,
        prompt: str,
        model: str,
        text_mode: str = "Off",
        image_mode: str = "Off",
        video_mode: str = "Off",
        tts_mode: str = "Off",
        stt_mode: str = "Off",
        ttaudio_mode: str = "Off",
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
        max_tokens: int = 750,
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
        selected_engine = _normalize_openai_engine(active_engine)
        engine_to_family = {
            "text": "text",
            "image": "image",
            "video": "video",
            "text_to_speech": "tts",
            "speech_to_text": "stt",
            "text_to_music": "ttaudio",
        }
        family = engine_to_family[selected_engine]

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
            if candidate_mode.lower() == "off":
                candidate_mode = "Off"
            else:
                raise OvertliInputError(
                    f"Invalid {family} mode selection: '{candidate_mode}'",
                    input_name=f"{family}_mode",
                )

        logger.info(
            "OpenAI-compatible node dispatch engine='%s' model='%s' vision=%s",
            selected_engine,
            (model or "").strip() or "<default>",
            vision_enabled,
        )

        return super().execute(
            active_engine=selected_engine,
            mode_preset=candidate_mode,
            prompt=prompt,
            model=model,
            image=image,
            file_path=file_path,
            audio=audio,
            custom_instructions=custom_instructions,
            style_preset_1=style_preset_1,
            style_preset_2=style_preset_2,
            style_preset_3=style_preset_3,
            additional_styles=additional_styles,
            api_base_url=api_base_url,
            api_key=api_key,
            persist_api_settings=persist_api_settings,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
            require_api_key=require_api_key,
            max_image_dimension=max_image_dimension,
            vision_enabled=vision_enabled,
            batch_image_mode=batch_image_mode,
            max_batch_frames=max_batch_frames,
            media_width=media_width,
            media_height=media_height,
            audio_voice=audio_voice,
            audio_speed=audio_speed,
            audio_response_format=audio_response_format,
            stt_response_format=stt_response_format,
            stt_language=stt_language,
        )


__all__ = ["GZ_OpenAICompatibleTextEnhancer"]

