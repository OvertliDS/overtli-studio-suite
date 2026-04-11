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

POLLINATIONS_NODE_CONFIG = {
    "GZ_TextEnhancer": {"class": GZ_TextEnhancer, "name": "🌸 OVERTLI Pollinations Text Enhancer"},
    "GZ_ImageGen": {"class": GZ_ImageGen, "name": "🌸 OVERTLI Pollinations Image Generator"},
    "GZ_VideoGen": {"class": GZ_VideoGen, "name": "🌸 OVERTLI Pollinations Video Generator"},
    "GZ_TextToSpeech": {"class": GZ_TextToSpeech, "name": "🌸 OVERTLI Pollinations Text-to-Speech"},
    "GZ_SpeechToText": {"class": GZ_SpeechToText, "name": "🌸 OVERTLI Pollinations Speech-to-Text"},
    "GZ_TextToAudio": {"class": GZ_TextToAudio, "name": "🌸 OVERTLI Pollinations Text-to-Music"},
}
