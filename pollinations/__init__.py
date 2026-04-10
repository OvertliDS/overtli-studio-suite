# ============================================================================
# pollinations/__init__.py
# Submodule initializer for Pollinations.ai node integration
# ============================================================================
"""
Pollinations Submodule
======================
Six specialized nodes leveraging the Pollinations.ai cloud API:

- GZ_TextEnhancer: Text/vision chat completions with dynamic model selection
- GZ_ImageGen: Text/image-to-image generation (returns binary PNG/JPEG)
- GZ_VideoGen: Synchronous video generation with timeout handling
- GZ_TextToSpeech: TTS via elevenlabs/openai-audio models
- GZ_SpeechToText: Audio transcription via /v1/audio/transcriptions
- GZ_TextToAudio: Speech/music generation via /v1/audio/speech and /audio/{text}
"""

from .text_enhancer import GZ_TextEnhancer
from .image_gen import GZ_ImageGen
from .video_gen import GZ_VideoGen
from .text_to_speech import GZ_TextToSpeech
from .speech_to_text import GZ_SpeechToText
from .text_to_audio import GZ_TextToAudio

__all__ = [
    "GZ_TextEnhancer",
    "GZ_ImageGen",
    "GZ_VideoGen",
    "GZ_TextToSpeech",
    "GZ_SpeechToText",
    "GZ_TextToAudio",
]

# Node registration config for parent __init__.py
POLLINATIONS_NODE_CONFIG = {
    "GZ_TextEnhancer": {
        "class": GZ_TextEnhancer,
        "name": "🌸 OVERTLI Pollinations Text Enhancer",
    },
    "GZ_ImageGen": {
        "class": GZ_ImageGen,
        "name": "🌸 OVERTLI Pollinations Image Generator",
    },
    "GZ_VideoGen": {
        "class": GZ_VideoGen,
        "name": "🌸 OVERTLI Pollinations Video Generator",
    },
    "GZ_TextToSpeech": {
        "class": GZ_TextToSpeech,
        "name": "🌸 OVERTLI Pollinations Text-to-Speech",
    },
    "GZ_SpeechToText": {
        "class": GZ_SpeechToText,
        "name": "🌸 OVERTLI Pollinations Speech-to-Text",
    },
    "GZ_TextToAudio": {
        "class": GZ_TextToAudio,
        "name": "🌸 OVERTLI Pollinations Text-to-Music",
    },
}
