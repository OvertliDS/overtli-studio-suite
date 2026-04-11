from __future__ import annotations

from .dispatch import resolve_node_class


_EngineClass = resolve_node_class()


class GZ_TextEnhancer(_EngineClass):
    pass
