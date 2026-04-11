from __future__ import annotations

from ...engine.llm_text_enhancer import (
    GZ_LLMTextEnhancer as _EngineClass,
    GZ_LMStudioTextEnhancer as _LegacyEngineClass,
)
from .routing import resolve_engine_class_name, resolve_legacy_engine_class_name


def resolve_node_class():
    _ = resolve_engine_class_name()
    return _EngineClass


def resolve_legacy_node_class():
    _ = resolve_legacy_engine_class_name()
    return _LegacyEngineClass

