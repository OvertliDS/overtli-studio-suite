from __future__ import annotations

from ....engine.pollinations.video_gen import GZ_VideoGen as _EngineClass
from .routing import resolve_engine_class_name


def resolve_node_class():
    _ = resolve_engine_class_name()
    return _EngineClass
