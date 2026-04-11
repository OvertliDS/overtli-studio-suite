from __future__ import annotations

from .catalog import AUDIO_STYLE_BUNDLES, AUDIO_STYLE_PRESETS_BY_TASK

AUDIO_STYLE_OFF = "Off"


def _normalize_task(task: str) -> str:
    normalized = (task or "").strip().lower()
    if normalized in {"text_to_audio", "text-to-audio", "audio"}:
        return "ttaudio"
    if normalized in {"speech_to_text", "speech-to-text", "transcription"}:
        return "stt"
    return normalized


def get_audio_style_options(task: str) -> list[str]:
    presets = AUDIO_STYLE_PRESETS_BY_TASK.get(_normalize_task(task), [])
    labels = [style["name"] for style in presets]
    return [AUDIO_STYLE_OFF, *labels]


def _lookup_style(task: str, preset: str) -> dict[str, str]:
    normalized_preset = (preset or "").strip()
    if not normalized_preset or normalized_preset == AUDIO_STYLE_OFF:
        return {"instruction": "", "hint": ""}

    for style in AUDIO_STYLE_PRESETS_BY_TASK.get(_normalize_task(task), []):
        if style["name"] == normalized_preset:
            return {"instruction": style.get("instruction", ""), "hint": style.get("hint", "")}
    return {"instruction": "", "hint": ""}


def resolve_audio_style_instruction(task: str, preset: str) -> str:
    return _lookup_style(task, preset).get("instruction", "")


def resolve_audio_style_hint(task: str, preset: str) -> str:
    return _lookup_style(task, preset).get("hint", "")


def get_advanced_audio_style_bundle_options() -> list[str]:
    return list(AUDIO_STYLE_BUNDLES.keys())


def resolve_advanced_audio_style_bundle(bundle_name: str) -> dict[str, str]:
    selected = AUDIO_STYLE_BUNDLES.get((bundle_name or "").strip())
    if selected:
        return {
            "tts": selected.get("tts", AUDIO_STYLE_OFF),
            "stt": selected.get("stt", AUDIO_STYLE_OFF),
            "ttaudio": selected.get("ttaudio", AUDIO_STYLE_OFF),
        }

    fallback = AUDIO_STYLE_BUNDLES[AUDIO_STYLE_OFF]
    return {
        "tts": fallback["tts"],
        "stt": fallback["stt"],
        "ttaudio": fallback["ttaudio"],
    }
