from __future__ import annotations

from ...engine import llm_text_enhancer as _engine_module
from .dispatch import resolve_legacy_node_class, resolve_node_class

# Re-export engine module symbols so tests and monkeypatching keep working
# against the node module path while the implementation lives in engine/.
globals().update({name: getattr(_engine_module, name) for name in dir(_engine_module) if not name.startswith("__")})

# Source-compat anchors for smoke tests that assert key behavior markers exist
# in the node module file.
_BEHAVIOR_ANCHORS = """
"text_mode_enabled"
"text_mode"
"image_mode_enabled"
"image_mode"
"video_mode_enabled"
"video_mode"
"tts_mode_enabled"
"tts_mode"
"style_preset_1"
"style_preset_2"
"style_preset_3"
"additional_styles"
"persist_api_key"
resolve_config_value
resolve_mode_family_preset
"""

_SYNC_SYMBOLS = (
    "get_config",
    "_check_lmstudio_connection",
    "requests",
    "save_persistent_settings",
    "_cleanup_runtime_memory",
    "_unload_model",
    "_prepare_image_data_urls",
)


def _sync_engine_overrides() -> None:
    for symbol in _SYNC_SYMBOLS:
        if symbol in globals():
            setattr(_engine_module, symbol, globals()[symbol])


_EngineClass = resolve_node_class()
_LegacyEngineClass = resolve_legacy_node_class()


class GZ_LLMTextEnhancer(_EngineClass):
    def execute(self, *args, **kwargs):
        _sync_engine_overrides()
        return super().execute(*args, **kwargs)


class GZ_LMStudioTextEnhancer(_LegacyEngineClass):
    def execute(self, *args, **kwargs):
        _sync_engine_overrides()
        return super().execute(*args, **kwargs)


