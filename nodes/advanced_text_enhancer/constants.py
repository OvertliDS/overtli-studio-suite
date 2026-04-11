from __future__ import annotations

from ...instruction_modes import (
    IMAGE_MODE_NAMES,
    SPEECH_TO_TEXT_MODE_NAMES,
    TEXT_MODE_NAMES,
    TEXT_TO_AUDIO_MODE_NAMES,
    TTS_MODE_NAMES,
    VIDEO_MODE_NAMES,
)

_PROVIDER_OPTIONS = [
    "pollinations",
    "lm_studio",
    "copilot",
    "openai_compatible",
]

_ENGINE_OPTION_LABEL_TO_VALUE = {
    "text (pollinations, lm_studio, copilot, openai_compatible)": "text",
    "image (pollinations, openai_compatible)": "image",
    "video (pollinations, openai_compatible)": "video",
    "text_to_speech (pollinations, openai_compatible)": "text_to_speech",
    "speech_to_text (pollinations, openai_compatible)": "speech_to_text",
    "text_to_music (pollinations, openai_compatible)": "text_to_music",
}
_ACTIVE_ENGINE_OPTIONS = list(_ENGINE_OPTION_LABEL_TO_VALUE.keys())
_ENGINE_VALUE_TO_LABEL = {value: label for label, value in _ENGINE_OPTION_LABEL_TO_VALUE.items()}
_PROVIDER_SUPPORTED_ENGINES = {
    "pollinations": {"text", "image", "video", "text_to_speech", "speech_to_text", "text_to_music"},
    "lm_studio": {"text"},
    "copilot": {"text"},
    "openai_compatible": {"text", "image", "video", "text_to_speech", "speech_to_text", "text_to_music"},
}

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
