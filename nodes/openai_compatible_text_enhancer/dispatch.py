from __future__ import annotations

from ...engine.openai_compatible_text_enhancer import GZ_OpenAICompatibleTextEnhancer as _EngineClass
from .routing import resolve_engine_class_name


def resolve_node_class():
    _ = resolve_engine_class_name()
    return _EngineClass

