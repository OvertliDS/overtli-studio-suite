"""
OVERTLI STUDIO LLM Suite - ComfyUI Custom Nodes

A unified modular suite for LLM integration in ComfyUI:
- Pollinations.ai (text, image, video, TTS, STT, audio/music generation)
- LM Studio (local text + optional vision)
- GitHub Copilot CLI (code assistance)

All nodes use the 3-Layer Instruction Stack:
1. Custom Instructions (highest priority)
2. Mode Presets (57 built-in modes)
3. Raw Prompt (always appended)
"""

__version__ = "0.7.4"
__author__ = "OVERTLI STUDIO"

# ============================================================================
# NODE IMPORTS
# ============================================================================

# Pollinations Nodes (Phase 3 - Implemented)
from .pollinations.text_enhancer import GZ_TextEnhancer
from .pollinations.image_gen import GZ_ImageGen
from .pollinations.video_gen import GZ_VideoGen
from .pollinations.text_to_speech import GZ_TextToSpeech
from .pollinations.speech_to_text import GZ_SpeechToText
from .pollinations.text_to_audio import GZ_TextToAudio

# Local Nodes (Phase 4 - Implemented)
from .lm_studio_vision import GZ_LMStudioTextEnhancer
from .copilot_agent import GZ_CopilotAgent
from .advanced_text_enhancer import GZ_AdvancedTextEnhancer
from .provider_settings import GZ_ProviderSettings
from .prompt_library_node import GZ_PromptLibraryNode
from .style_stack_node import GZ_StyleStackNode


# ============================================================================
# NODE CONFIGURATION
# ============================================================================

# Central node registry
# Format: "InternalName": {"class": NodeClass, "display": "Display Name"}
NODE_CONFIG = {
    # === Pollinations Nodes (Cloud) ===
    "GZ_TextEnhancer": {
        "class": GZ_TextEnhancer,
        "display": "🌸 OVERTLI Pollinations Text Enhancer",
    },
    "GZ_ImageGen": {
        "class": GZ_ImageGen,
        "display": "🌸 OVERTLI Pollinations Image Generator",
    },
    "GZ_VideoGen": {
        "class": GZ_VideoGen,
        "display": "🌸 OVERTLI Pollinations Video Generator",
    },
    "GZ_TextToSpeech": {
        "class": GZ_TextToSpeech,
        "display": "🌸 OVERTLI Pollinations Text to Speech",
    },
    "GZ_SpeechToText": {
        "class": GZ_SpeechToText,
        "display": "🌸 OVERTLI Pollinations Speech to Text",
    },
    "GZ_TextToAudio": {
        "class": GZ_TextToAudio,
        "display": "🌸 OVERTLI Pollinations Text to Music",
    },
    
    # === Local Nodes (Phase 4 - Implemented) ===
    "GZ_LMStudioTextEnhancer": {
        "class": GZ_LMStudioTextEnhancer,
        "display": "🏠 OVERTLI LM Studio Text Enhancer",
    },
    "GZ_CopilotAgent": {
        "class": GZ_CopilotAgent,
        "display": "🚀 OVERTLI Copilot Text Enhancer",
    },

    # === Unified Router + Utilities ===
    "GZ_AdvancedTextEnhancer": {
        "class": GZ_AdvancedTextEnhancer,
        "display": "⭐ OVERTLI Advanced Studio",
    },
    "GZ_ProviderSettings": {
        "class": GZ_ProviderSettings,
        "display": "⚙️ OVERTLI Provider Settings",
    },
    "GZ_PromptLibraryNode": {
        "class": GZ_PromptLibraryNode,
        "display": "📚 OVERTLI Prompt Library",
    },
    "GZ_StyleStackNode": {
        "class": GZ_StyleStackNode,
        "display": "🎨 OVERTLI Style Stack (7)",
    },
}


def generate_node_mappings(config: dict) -> tuple:
    """
    Generate NODE_CLASS_MAPPINGS and NODE_DISPLAY_NAME_MAPPINGS from config.
    
    Args:
        config: Dict of {"InternalName": {"class": Class, "display": "Name"}}
    
    Returns:
        Tuple of (class_mappings, display_mappings)
    """
    class_mappings = {}
    display_mappings = {}
    
    for internal_name, node_info in config.items():
        class_mappings[internal_name] = node_info["class"]
        display_mappings[internal_name] = node_info["display"]
    
    return class_mappings, display_mappings


# ============================================================================
# COMFYUI REGISTRATION
# ============================================================================

# Generate mappings from config
NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS = generate_node_mappings(NODE_CONFIG)

# Web directory for custom JS (if needed in the future)
# WEB_DIRECTORY = "./web"

# Print load confirmation
print(f"[OVERTLI STUDIO LLM Suite] v{__version__} loaded - {len(NODE_CLASS_MAPPINGS)} nodes registered")


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "__version__",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
]
