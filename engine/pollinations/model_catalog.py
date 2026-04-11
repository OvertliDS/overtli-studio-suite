"""Dynamic Pollinations model catalog helpers."""

from __future__ import annotations

import logging
import importlib
import os
import time
from typing import Any

requests = importlib.import_module("requests")

from ...settings_store import get_persistent_setting, resolve_setting
from ...suite_config import get_config

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 300
_CACHE_MODELS: list[dict[str, Any]] = []
_CACHE_TS = 0.0

_TEXT_MODEL_NAME_KEYWORDS = {
    "openai",
    "gpt",
    "qwen",
    "mistral",
    "llama",
    "gemini",
    "deepseek",
    "claude",
    "grok",
    "perplexity",
    "kimi",
    "nova",
    "glm",
    "minimax",
    "polly",
}

_VISION_MODEL_NAME_KEYWORDS = {
    "vision",
    "qwen-vision",
    "kimi",
}

_IMAGE_MODEL_NAME_KEYWORDS = {
    "flux",
    "image",
    "gptimage",
    "nanobanana",
    "kontext",
    "seedream",
    "qwen-image",
    "grok-imagine",
    "klein",
    "canvas",
}

_VIDEO_MODEL_NAME_KEYWORDS = {
    "video",
    "veo",
    "seedance",
    "wan",
    "ltx",
    "nova-reel",
}

_AUDIO_STT_KEYWORDS = {
    "whisper",
    "scribe",
    "transcrib",
    "stt",
}

_AUDIO_MUSIC_KEYWORDS = {
    "music",
    "acestep",
    "midi",
    "udio",
    "riff",
}

_AUDIO_SPEECH_KEYWORDS = {
    "openai-audio",
    "elevenlabs",
    "tts",
    "voice",
    "speech",
}


def _normalize_tokens(value: Any) -> set[str]:
    tokens: set[str] = set()
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered:
            tokens.add(lowered)
        return tokens

    if isinstance(value, dict):
        for key, nested in value.items():
            tokens.update(_normalize_tokens(key))
            tokens.update(_normalize_tokens(nested))
        return tokens

    if isinstance(value, (list, tuple, set)):
        for item in value:
            tokens.update(_normalize_tokens(item))
        return tokens

    return tokens


def _extract_model_name(entry: dict[str, Any]) -> str:
    for key in ("id", "name", "model", "slug"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def extract_display_model_name(model_display: str) -> str:
    """Extract the raw model id from a tagged dropdown/manual display string."""
    if not model_display:
        return ""
    return str(model_display).split(" [", 1)[0].strip()


def _normalize_model_entry(entry: Any) -> dict[str, Any]:
    if isinstance(entry, dict):
        return dict(entry)
    if isinstance(entry, str) and entry.strip():
        return {
            "id": entry.strip(),
            "name": entry.strip(),
        }
    return {}


def _has_any_keyword(name: str, keywords: set[str]) -> bool:
    lowered = (name or "").lower()
    return any(keyword in lowered for keyword in keywords)


def _merge_token_lists(first: Any, second: Any) -> list[str]:
    return sorted(_normalize_tokens(first).union(_normalize_tokens(second)))


def _merge_catalog_entries(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)

    for field in (
        "supported_endpoints",
        "input_modalities",
        "output_modalities",
        "capabilities",
        "features",
        "tags",
        "modalities",
    ):
        merged[field] = _merge_token_lists(base.get(field, []), incoming.get(field, []))

    for field in (
        "paid_only",
        "tools",
        "web",
        "vision",
        "reasoning",
        "community",
    ):
        if field in incoming:
            merged[field] = merged.get(field, incoming[field]) or incoming[field]

    if not merged.get("name"):
        merged["name"] = incoming.get("name") or incoming.get("id")
    if not merged.get("id"):
        merged["id"] = incoming.get("id") or incoming.get("name")

    return merged


def _is_text_chat_model(entry: dict[str, Any]) -> bool:
    name = _extract_model_name(entry)
    if not name:
        return False

    endpoints = _normalize_tokens(entry.get("supported_endpoints", []))
    input_modalities = _normalize_tokens(entry.get("input_modalities", []))
    output_modalities = _normalize_tokens(entry.get("output_modalities", []))

    has_chat_endpoint = "/v1/chat/completions" in endpoints
    has_text_output = "text" in output_modalities
    looks_like_text_model = _has_any_keyword(name, _TEXT_MODEL_NAME_KEYWORDS)

    if has_chat_endpoint and has_text_output:
        return True

    if has_text_output and looks_like_text_model:
        return True

    # Some payloads omit modalities while still being chat-capable.
    if has_chat_endpoint and ("text" in input_modalities or looks_like_text_model):
        return True

    return False


def _supports_vision_input(entry: dict[str, Any]) -> bool:
    name = _extract_model_name(entry)
    input_modalities = _normalize_tokens(entry.get("input_modalities", []))
    tags = _normalize_tokens(entry.get("tags", []))
    capabilities = _normalize_tokens(entry.get("capabilities", []))

    if "image" in input_modalities:
        return True
    if "vision" in tags or "vision" in capabilities:
        return True
    if bool(entry.get("vision")):
        return True
    return _has_any_keyword(name, _VISION_MODEL_NAME_KEYWORDS)


def _detect_audio_capabilities(entry: dict[str, Any]) -> set[str]:
    capabilities: set[str] = set()

    name = _extract_model_name(entry)
    endpoints = _normalize_tokens(entry.get("supported_endpoints", []))
    input_modalities = _normalize_tokens(entry.get("input_modalities", []))
    output_modalities = _normalize_tokens(entry.get("output_modalities", []))
    tokens = _normalize_tokens(entry.get("tags", []))
    tokens = tokens.union(_normalize_tokens(entry.get("capabilities", [])))

    supports_transcriptions_endpoint = any("/v1/audio/transcriptions" in endpoint for endpoint in endpoints)
    supports_audio_to_text = "audio" in input_modalities and "text" in output_modalities
    stt_by_name = _has_any_keyword(name, _AUDIO_STT_KEYWORDS)
    if supports_transcriptions_endpoint or supports_audio_to_text or stt_by_name:
        capabilities.add("transcription")

    supports_speech_endpoint = any(
        marker in endpoint for marker in ("/v1/audio/speech", "/audio/{text}") for endpoint in endpoints
    )
    supports_text_to_audio = "text" in input_modalities and "audio" in output_modalities
    speech_by_name = _has_any_keyword(name, _AUDIO_SPEECH_KEYWORDS)
    music_by_name = _has_any_keyword(name, _AUDIO_MUSIC_KEYWORDS)
    music_by_tokens = "music" in tokens

    if music_by_name or music_by_tokens:
        capabilities.add("music")

    if supports_speech_endpoint or supports_text_to_audio or speech_by_name:
        if "music" not in capabilities or speech_by_name:
            capabilities.add("speech")

    return capabilities


def _extract_modalities(entry: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for key in (
        "modalities",
        "input_modalities",
        "output_modalities",
        "capabilities",
        "features",
        "tags",
        "type",
        "category",
    ):
        if key in entry:
            tokens.update(_normalize_tokens(entry.get(key)))

    name = _extract_model_name(entry).lower()
    if "image" in name:
        tokens.add("image")
    if "video" in name:
        tokens.add("video")
    if any(token in name for token in ("audio", "speech", "voice", "tts", "eleven")):
        tokens.add("audio")
    if any(token in name for token in ("openai", "gpt", "qwen", "mistral", "llama", "gemini", "deepseek")):
        tokens.add("text")
    if "vision" in name:
        tokens.add("vision")

    endpoints = _normalize_tokens(entry.get("supported_endpoints", []))
    if any("/v1/chat/completions" in endpoint for endpoint in endpoints):
        tokens.add("text")
    if any("/v1/images/" in endpoint or "/image/" in endpoint for endpoint in endpoints):
        tokens.add("image")
    if any("video" in endpoint for endpoint in endpoints):
        tokens.add("video")
    if any("/audio/" in endpoint for endpoint in endpoints):
        tokens.add("audio")

    return tokens


def _supports_modality(entry: dict[str, Any], modality: str) -> bool:
    name = _extract_model_name(entry).lower()
    tokens = _extract_modalities(entry)
    endpoints = _normalize_tokens(entry.get("supported_endpoints", []))

    if modality == "text":
        return _is_text_chat_model(entry)

    if modality == "image":
        explicit_image_endpoint = any(
            marker in endpoint for marker in ("/image/", "/v1/images/generations", "/v1/images/edits")
            for endpoint in endpoints
        )
        image_by_name = _has_any_keyword(name, _IMAGE_MODEL_NAME_KEYWORDS)
        video_by_name = _has_any_keyword(name, _VIDEO_MODEL_NAME_KEYWORDS)
        return (
            "image" in tokens
            or explicit_image_endpoint
            or image_by_name
            or ("vision" in tokens and not video_by_name)
        ) and not ("video" in tokens and not image_by_name)

    if modality == "video":
        explicit_video_endpoint = any("video" in endpoint for endpoint in endpoints)
        return "video" in tokens or explicit_video_endpoint or _has_any_keyword(name, _VIDEO_MODEL_NAME_KEYWORDS)

    if modality == "audio":
        return bool(_detect_audio_capabilities(entry))

    return False


def _access_tags(entry: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    tier = str(entry.get("tier", "") or "").strip().lower()
    if bool(entry.get("paid_only")):
        tags.append("[paid]")
    else:
        tags.append("[free]")

    if tier == "seed":
        tags.append("[seed]")
    elif tier == "anonymous":
        tags.append("[anonymous]")
    elif tier and tier not in {"seed", "anonymous"}:
        tags.append(f"[{tier}]")

    return tags


def _runtime_tags(entry: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    if bool(entry.get("community")):
        tags.append("[community]")
    if bool(entry.get("tools")):
        tags.append("[tools]")
    if bool(entry.get("web")):
        tags.append("[web]")
    return tags


def _build_text_display_tags(entry: dict[str, Any], supports_vision: bool) -> list[str]:
    tags = ["[text]"]
    tags.append("[vision]" if supports_vision else "[text-only]")
    tags.extend(_access_tags(entry))
    tags.extend(_runtime_tags(entry))
    return tags


def _build_modality_display_tags(entry: dict[str, Any], modality: str) -> list[str]:
    modality_label = {
        "image": "[image-gen]",
        "video": "[video-gen]",
        "transcription": "[stt]",
        "generation": "[ttaudio]",
        "generation_speech": "[tts]",
        "generation_music": "[music]",
    }.get(modality, f"[{modality}]")

    tags = [modality_label]

    if modality == "image" and _supports_vision_input(entry):
        tags.append("[reference-image?]")
    if modality == "video":
        tags.append("[reference-image?]")

    capabilities = _detect_audio_capabilities(entry)
    if modality.startswith("generation") and "speech" in capabilities and "[tts]" not in tags:
        tags.append("[tts]")
    if modality.startswith("generation") and "music" in capabilities and "[music]" not in tags:
        tags.append("[music]")

    tags.extend(_access_tags(entry))
    tags.extend(_runtime_tags(entry))
    return tags


def _format_display_name(name: str, tags: list[str]) -> str:
    deduped: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        if not tag or tag in seen:
            continue
        seen.add(tag)
        deduped.append(tag)
    return f"{name} {' '.join(deduped)}".strip()


def get_pollinations_model_entry(model_name: str, force_refresh: bool = False) -> dict[str, Any] | None:
    """Return a normalized catalog entry for a raw model id, if present."""
    raw_name = extract_display_model_name(model_name).lower()
    if not raw_name:
        return None

    for entry in _fetch_catalog(force_refresh=force_refresh):
        if _extract_model_name(entry).lower() == raw_name:
            return entry
    return None


def supports_pollinations_family(
    model_name: str,
    family: str,
    force_refresh: bool = False,
) -> bool | None:
    """Return whether a catalog model supports the requested advanced-router family."""
    entry = get_pollinations_model_entry(model_name, force_refresh=force_refresh)
    if not entry:
        return None

    normalized_family = (family or "").strip().lower()
    if normalized_family in {"text", "image", "video"}:
        return _supports_modality(entry, normalized_family)

    capabilities = _detect_audio_capabilities(entry)
    if normalized_family == "stt":
        return "transcription" in capabilities
    if normalized_family == "tts":
        return "speech" in capabilities
    if normalized_family == "ttaudio":
        return bool(capabilities.intersection({"speech", "music"}))

    raise ValueError(f"Unsupported Pollinations family '{family}'")


def _resolve_pollinations_api_key() -> str:
    config = get_config()
    return resolve_setting(
        runtime_value="",
        env_value=os.environ.get("GZ_POLLINATIONS_API_KEY", ""),
        persisted_value=get_persistent_setting("pollinations_api_key", ""),
        default=(config.pollinations.api_key or ""),
    )


def _fetch_catalog(force_refresh: bool = False) -> list[dict[str, Any]]:
    global _CACHE_MODELS, _CACHE_TS

    now = time.time()
    if not force_refresh and _CACHE_MODELS and (now - _CACHE_TS) < _CACHE_TTL_SECONDS:
        return list(_CACHE_MODELS)

    cfg = get_config().pollinations
    headers: dict[str, str] = {}
    api_key = _resolve_pollinations_api_key()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        headers["x-api-key"] = api_key

    all_entries: list[dict[str, Any]] = []
    endpoint_plan = [
        ("text", cfg.models_endpoint),
        ("image", f"{cfg.image_endpoint}/models"),
        ("audio", cfg.audio_models_endpoint),
    ]

    for source_name, endpoint in endpoint_plan:
        try:
            response = requests.get(
                endpoint,
                headers=headers if headers else None,
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()

            raw_entries: list[Any] = []
            if isinstance(payload, list):
                raw_entries = payload
            elif isinstance(payload, dict):
                for key in ("data", "models", "items"):
                    value = payload.get(key)
                    if isinstance(value, list):
                        raw_entries = value
                        break

            for raw_entry in raw_entries:
                normalized = _normalize_model_entry(raw_entry)
                if not normalized:
                    continue

                normalized.setdefault("tags", [])
                tags = _normalize_tokens(normalized.get("tags", []))
                tags.add(source_name)
                normalized["tags"] = sorted(tags)

                all_entries.append(normalized)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to refresh Pollinations model catalog from %s: %s", endpoint, exc)

    if all_entries:
        merged: dict[str, dict[str, Any]] = {}
        for entry in all_entries:
            model_name = _extract_model_name(entry)
            if not model_name:
                continue

            key = model_name.lower()
            if key in merged:
                merged[key] = _merge_catalog_entries(merged[key], entry)
            else:
                merged[key] = dict(entry)

        if merged:
            _CACHE_MODELS = list(merged.values())
            _CACHE_TS = now
            return list(_CACHE_MODELS)

    return list(_CACHE_MODELS)


def fetch_pollinations_text_models(require_vision: bool, fallback_models: list[str]) -> list[str]:
    """Return text chat models with optional strict vision capability filtering."""
    entries = _fetch_catalog()

    discovered: list[str] = []
    seen: set[str] = set()

    for entry in entries:
        name = _extract_model_name(entry)
        if not name:
            continue
        if not _is_text_chat_model(entry):
            continue

        supports_vision = _supports_vision_input(entry)
        if require_vision and not supports_vision:
            continue

        normalized_name = name.lower()
        if normalized_name in seen:
            continue
        seen.add(normalized_name)

        discovered.append(_format_display_name(name, _build_text_display_tags(entry, supports_vision)))

    if discovered:
        return discovered

    return list(fallback_models)


def fetch_pollinations_modality_models(modality: str, fallback_models: list[str]) -> list[str]:
    """Return display model options for a target modality with fallback safety."""
    if modality == "text":
        return fetch_pollinations_text_models(require_vision=False, fallback_models=fallback_models)

    entries = _fetch_catalog()

    discovered: list[str] = []
    seen: set[str] = set()

    for entry in entries:
        name = _extract_model_name(entry)
        if not name:
            continue
        if not _supports_modality(entry, modality):
            continue

        normalized = name.strip()
        if normalized.lower() in seen:
            continue
        seen.add(normalized.lower())

        discovered.append(_format_display_name(normalized, _build_modality_display_tags(entry, modality)))

    if discovered:
        return discovered

    return list(fallback_models)


def get_pollinations_catalog_entries(force_refresh: bool = False) -> list[dict[str, Any]]:
    """Return raw Pollinations catalog entries with cache support."""
    return _fetch_catalog(force_refresh=force_refresh)


def fetch_pollinations_audio_models_for_task(task: str, fallback_models: list[str]) -> list[str]:
    """
    Return audio model options tailored for a task.

    Args:
        task: One of "transcription", "generation", "generation_speech", or "generation_music".
        fallback_models: Used when live catalog has no match.
    """
    normalized_task = (task or "").strip().lower()
    if normalized_task not in {"transcription", "generation", "generation_speech", "generation_music"}:
        raise ValueError(f"Unsupported audio task '{task}'")

    entries = _fetch_catalog()

    discovered: list[str] = []
    seen: set[str] = set()

    for entry in entries:
        name = _extract_model_name(entry)
        if not name:
            continue

        normalized_name = name.lower()
        capabilities = _detect_audio_capabilities(entry)

        if normalized_task == "transcription":
            if "transcription" not in capabilities:
                continue
        elif normalized_task == "generation_speech":
            if "speech" not in capabilities:
                continue
        elif normalized_task == "generation_music":
            if "music" not in capabilities:
                continue
        else:
            if not capabilities.intersection({"speech", "music"}):
                continue

        if normalized_name in seen:
            continue
        seen.add(normalized_name)

        discovered.append(_format_display_name(name, _build_modality_display_tags(entry, normalized_task)))

    if discovered:
        return discovered

    return list(fallback_models)


def fetch_pollinations_advanced_models() -> list[str]:
    """Return a single advanced dropdown sorted by primary modality for the router node."""
    choices: list[str] = ["auto"]
    seen: set[str] = {choice.lower() for choice in choices}

    groups = [
        fetch_pollinations_text_models(require_vision=False, fallback_models=["openai [text] [vision] [free]"]),
        fetch_pollinations_modality_models("image", fallback_models=["flux [image-gen] [free]"]),
        fetch_pollinations_modality_models("video", fallback_models=["wan [video-gen] [free]"]),
        fetch_pollinations_audio_models_for_task("transcription", ["whisper [stt] [free]"]),
        fetch_pollinations_audio_models_for_task("generation_speech", ["openai-audio [tts] [free]"]),
        fetch_pollinations_audio_models_for_task("generation", ["openai-audio [ttaudio] [free]"]),
    ]

    for group in groups:
        for option in group:
            normalized = option.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            choices.append(option)

    return choices

