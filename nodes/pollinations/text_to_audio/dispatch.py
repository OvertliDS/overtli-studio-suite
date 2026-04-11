from __future__ import annotations

from ....engine.pollinations.text_to_audio import GZ_TextToAudio as _EngineClass
from .routing import resolve_engine_class_name


def resolve_node_class():
    _ = resolve_engine_class_name()
    return _EngineClass
