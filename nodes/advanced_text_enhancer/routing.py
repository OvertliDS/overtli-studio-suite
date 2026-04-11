from __future__ import annotations

import logging

from ...exceptions import OvertliInputError
from .constants import (
    _ENGINE_OPTION_LABEL_TO_VALUE,
    _ENGINE_VALUE_TO_LABEL,
    _PROVIDER_SUPPORTED_ENGINES,
)

logger = logging.getLogger(__name__)


def _normalize_provider_name(provider: str) -> str:
    """Normalize provider aliases used by the advanced router."""
    normalized = (provider or "pollinations").strip().lower().replace("_", "-")
    alias_map = {
        "lm-studio": "lm_studio",
        "copilot-cli": "copilot",
        "copilotcli": "copilot",
        "openai-compatible": "openai_compatible",
    }
    return alias_map.get(normalized, normalized.replace("-", "_"))


def _normalize_active_engine_name(active_engine: str) -> str:
    """Normalize active-engine labels/aliases to canonical engine keys."""
    engine_value = (active_engine or "text").strip()
    if engine_value in _ENGINE_OPTION_LABEL_TO_VALUE:
        return _ENGINE_OPTION_LABEL_TO_VALUE[engine_value]

    normalized = engine_value.lower().replace("-", "_")
    if "(" in normalized:
        normalized = normalized.split("(", 1)[0].strip()

    alias_map = {
        "text": "text",
        "image": "image",
        "video": "video",
        "text_to_speech": "text_to_speech",
        "speech_to_text": "speech_to_text",
        "text_to_music": "text_to_music",
    }
    return alias_map.get(normalized, normalized)


def _validate_provider_engine(provider_name: str, selected_engine: str) -> None:
    """Fail early when the chosen engine is not supported by the chosen provider."""
    supported = _PROVIDER_SUPPORTED_ENGINES.get(provider_name, set())
    if selected_engine in supported:
        return

    selected_label = _ENGINE_VALUE_TO_LABEL.get(selected_engine, selected_engine)
    supported_labels = [
        _ENGINE_VALUE_TO_LABEL[engine]
        for engine in _PROVIDER_SUPPORTED_ENGINES.get(provider_name, set())
        if engine in _ENGINE_VALUE_TO_LABEL
    ]
    supported_text = "; ".join(supported_labels) if supported_labels else "text"
    logger.error(
        "AdvancedTextEnhancer provider/engine mismatch provider='%s' engine='%s' supported='%s'",
        provider_name,
        selected_engine,
        supported_text,
    )
    raise OvertliInputError(
        (
            f"Active engine '{selected_label}' is not supported for provider '{provider_name}'.\n"
            f"Supported engines for provider '{provider_name}': {supported_text}.\n"
            "What to do next: choose one of the supported engines shown in the active_engine dropdown."
        ),
        input_name="active_engine",
    )
