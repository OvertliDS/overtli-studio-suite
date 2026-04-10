"""Audio style preset helpers for TTS, STT, and text-to-audio nodes."""

from __future__ import annotations

from typing import Dict

AUDIO_STYLE_OFF = "Off"


_AUDIO_STYLE_PRESETS: dict[str, dict[str, dict[str, str]]] = {
    "tts": {
        AUDIO_STYLE_OFF: {"instruction": "", "hint": ""},
        "Natural Narration": {
            "instruction": (
                "Prioritize calm, natural pacing with clear sentence boundaries, "
                "balanced emphasis, and easy-to-follow phrasing."
            ),
            "hint": "",
        },
        "Podcast Host": {
            "instruction": (
                "Shape the text for upbeat spoken delivery with conversational flow, "
                "energetic transitions, and short punchy lines where useful."
            ),
            "hint": "",
        },
        "Dramatic Performance": {
            "instruction": (
                "Emphasize theatrical rhythm with purposeful pauses, stronger contrast, "
                "and emotionally weighted sentence endings."
            ),
            "hint": "",
        },
    },
    "stt": {
        AUDIO_STYLE_OFF: {"instruction": "", "hint": ""},
        "Verbatim Accuracy": {
            "instruction": (
                "Keep transcript wording as close as possible to source speech while "
                "restoring basic punctuation and casing only."
            ),
            "hint": "",
        },
        "Readable Transcript": {
            "instruction": (
                "Improve readability with clean punctuation, paragraphing, and light filler "
                "reduction while preserving factual meaning."
            ),
            "hint": "",
        },
        "Meeting Notes": {
            "instruction": (
                "Format into concise notes with key decisions, action items, and important "
                "names while preserving factual content."
            ),
            "hint": "",
        },
    },
    "ttaudio": {
        AUDIO_STYLE_OFF: {"instruction": "", "hint": ""},
        "Cinematic Atmosphere": {
            "instruction": (
                "Focus on cinematic ambience with layered depth, evolving motion, and a clear "
                "foreground-to-background soundstage."
            ),
            "hint": "cinematic atmospheric",
        },
        "Lo-Fi Chill": {
            "instruction": (
                "Target mellow, warm, lo-fi character with soft dynamics and steady "
                "unobtrusive rhythmic texture."
            ),
            "hint": "lo-fi chill",
        },
        "Epic Trailer": {
            "instruction": (
                "Build high-impact trailer energy with dramatic rises, bold low-end emphasis, "
                "and strong climactic transitions."
            ),
            "hint": "epic trailer",
        },
    },
}


_ADVANCED_AUDIO_STYLE_BUNDLES: dict[str, dict[str, str]] = {
    AUDIO_STYLE_OFF: {
        "tts": AUDIO_STYLE_OFF,
        "stt": AUDIO_STYLE_OFF,
        "ttaudio": AUDIO_STYLE_OFF,
    },
    "Clarity Bundle": {
        "tts": "Natural Narration",
        "stt": "Readable Transcript",
        "ttaudio": "Cinematic Atmosphere",
    },
    "Creator Bundle": {
        "tts": "Podcast Host",
        "stt": "Meeting Notes",
        "ttaudio": "Lo-Fi Chill",
    },
    "Cinematic Bundle": {
        "tts": "Dramatic Performance",
        "stt": "Verbatim Accuracy",
        "ttaudio": "Epic Trailer",
    },
}


def _normalize_task(task: str) -> str:
    normalized = (task or "").strip().lower()
    if normalized in {"text_to_audio", "text-to-audio", "audio"}:
        return "ttaudio"
    if normalized in {"speech_to_text", "speech-to-text", "transcription"}:
        return "stt"
    return normalized


def get_audio_style_options(task: str) -> list[str]:
    presets = _AUDIO_STYLE_PRESETS.get(_normalize_task(task), {})
    if not presets:
        return [AUDIO_STYLE_OFF]
    return list(presets.keys())


def resolve_audio_style_instruction(task: str, preset: str) -> str:
    presets = _AUDIO_STYLE_PRESETS.get(_normalize_task(task), {})
    selected = presets.get((preset or "").strip()) or presets.get(AUDIO_STYLE_OFF, {})
    return selected.get("instruction", "")


def resolve_audio_style_hint(task: str, preset: str) -> str:
    presets = _AUDIO_STYLE_PRESETS.get(_normalize_task(task), {})
    selected = presets.get((preset or "").strip()) or presets.get(AUDIO_STYLE_OFF, {})
    return selected.get("hint", "")


def get_advanced_audio_style_bundle_options() -> list[str]:
    return list(_ADVANCED_AUDIO_STYLE_BUNDLES.keys())


def resolve_advanced_audio_style_bundle(bundle_name: str) -> Dict[str, str]:
    selected = _ADVANCED_AUDIO_STYLE_BUNDLES.get((bundle_name or "").strip())
    if selected:
        return dict(selected)
    return dict(_ADVANCED_AUDIO_STYLE_BUNDLES[AUDIO_STYLE_OFF])


__all__ = [
    "AUDIO_STYLE_OFF",
    "get_audio_style_options",
    "resolve_audio_style_instruction",
    "resolve_audio_style_hint",
    "get_advanced_audio_style_bundle_options",
    "resolve_advanced_audio_style_bundle",
]
