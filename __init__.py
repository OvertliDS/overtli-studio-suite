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

__version__ = "1.1.0"
__author__ = "OVERTLI STUDIO"

# ============================================================================
# NODE IMPORTS
# ============================================================================

# Pollinations Nodes (Phase 3 - Implemented)
try:
    from .nodes.pollinations import (
        GZ_ImageGen,
        GZ_SpeechToText,
        GZ_TextEnhancer,
        GZ_TextToAudio,
        GZ_TextToSpeech,
        GZ_VideoGen,
    )

    # Local Nodes (Phase 4 - Implemented)
    from .nodes.advanced_text_enhancer import GZ_AdvancedTextEnhancer
    from .nodes.copilot_agent import GZ_CopilotAgent
    from .nodes.llm_text_enhancer import GZ_LLMTextEnhancer
    from .nodes.openai_compatible_text_enhancer import GZ_OpenAICompatibleTextEnhancer
    from .nodes.prompt_library import GZ_PromptLibraryNode
    from .nodes.provider_settings import GZ_ProviderSettings
    from .nodes.style_stack import GZ_StyleStackNode
except ImportError:
    # Pytest may import this file as a plain module (`__package__` is empty)
    # while collecting tests. Keep import-time behavior non-fatal in that mode.
    if __package__:
        raise
    GZ_ImageGen = None
    GZ_SpeechToText = None
    GZ_TextEnhancer = None
    GZ_TextToAudio = None
    GZ_TextToSpeech = None
    GZ_VideoGen = None
    GZ_AdvancedTextEnhancer = None
    GZ_CopilotAgent = None
    GZ_LLMTextEnhancer = None
    GZ_OpenAICompatibleTextEnhancer = None
    GZ_PromptLibraryNode = None
    GZ_ProviderSettings = None
    GZ_StyleStackNode = None


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
    "GZ_LLMTextEnhancer": {
        "class": GZ_LLMTextEnhancer,
        "display": "🏠 OVERTLI LLM Text Enhancer",
    },
    # Legacy node id retained for workflow compatibility.
    "GZ_LMStudioTextEnhancer": {
        "class": GZ_LLMTextEnhancer,
        "display": "🏠 OVERTLI LLM Text Enhancer (Legacy ID)",
    },
    "GZ_CopilotAgent": {
        "class": GZ_CopilotAgent,
        "display": "🚀 OVERTLI Copilot Text Enhancer",
    },
    "GZ_OpenAICompatibleTextEnhancer": {
        "class": GZ_OpenAICompatibleTextEnhancer,
        "display": "🔌 OVERTLI OpenAI-Compatible Studio",
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
