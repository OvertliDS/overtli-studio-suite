from __future__ import annotations

from .constants import ENGINE_CLASS, LEGACY_ENGINE_CLASS


def resolve_engine_class_name() -> str:
    return ENGINE_CLASS


def resolve_legacy_engine_class_name() -> str:
    return LEGACY_ENGINE_CLASS

