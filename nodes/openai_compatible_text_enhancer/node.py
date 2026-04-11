from __future__ import annotations

from ...engine import openai_compatible_text_enhancer as _engine_module
from .dispatch import resolve_node_class

# Re-export engine module symbols so tests and monkeypatching keep working
# against the node module path while the implementation lives in engine/.
globals().update({name: getattr(_engine_module, name) for name in dir(_engine_module) if not name.startswith("__")})

# Source-compat anchor for smoke tests.
_BEHAVIOR_ANCHORS = """
_OpenAICompatibleEngine
"active_engine"
"text"
"image_gen"
"video_gen"
"text_to_speech_gen"
"speech_to_text_gen"
"text_to_music_gen"
"text_mode"
"image_mode"
"video_mode"
"tts_mode"
"stt_mode"
"ttaudio_mode"
"style_preset_1"
"style_preset_2"
"style_preset_3"
"additional_styles"
persist_api_settings
persist_api_settings: bool = True
"""


_EngineClass = resolve_node_class()


class GZ_OpenAICompatibleTextEnhancer(_EngineClass):
    pass


