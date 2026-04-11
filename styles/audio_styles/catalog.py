from __future__ import annotations

from .categories import STT_STYLES, TTAUDIO_STYLES, TTS_STYLES
from .types import AudioStyleBundle, AudioStylePreset

AUDIO_STYLE_PRESETS: list[AudioStylePreset] = [
    *TTS_STYLES,
    *STT_STYLES,
    *TTAUDIO_STYLES,
]

AUDIO_STYLE_PRESETS_BY_TASK: dict[str, list[AudioStylePreset]] = {
    "tts": TTS_STYLES,
    "stt": STT_STYLES,
    "ttaudio": TTAUDIO_STYLES,
}

AUDIO_STYLE_BUNDLES: dict[str, AudioStyleBundle] = {
    "Off": {
        "tts": "Off",
        "stt": "Off",
        "ttaudio": "Off",
        "description": "No audio style bundle applied.",
    },
    "Clarity Bundle": {
        "tts": "Natural Narration",
        "stt": "Readable Transcript",
        "ttaudio": "Ambient Focus",
        "description": "Balanced clarity for speech synthesis, transcription, and background audio.",
    },
    "Creator Bundle": {
        "tts": "Podcast Host",
        "stt": "Interview Highlights",
        "ttaudio": "Lo-Fi Chill",
        "description": "Creator-oriented voice and post-production style defaults.",
    },
    "Cinematic Bundle": {
        "tts": "Dramatic Performance",
        "stt": "Verbatim Accuracy",
        "ttaudio": "Cinematic Atmosphere",
        "description": "Film-style dramatic delivery and cinematic scoring guidance.",
    },
    "Broadcast Bundle": {
        "tts": "Broadcast News",
        "stt": "Legal Deposition",
        "ttaudio": "Synthwave Drive",
        "description": "Formal speech and precision transcript defaults.",
    },
}
