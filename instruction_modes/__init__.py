# 🎯 OVERTLI STUDIO LLM Suite - Instruction Modes Package
# Central exports for instruction modes, grouped mode-family resolution,
# and system-prompt layering.

"""
Instruction modes are organized by category and can be consumed either as:
- a direct mode preset
- grouped family toggles (text/image/video/tts)

The resolver prepends an internal category system prompt before the selected
mode instruction, then nodes append the user prompt separately.
"""

from __future__ import annotations

from .text_modes import TEXT_MODES, TEXT_MODE_NAMES, get_text_mode
from .image_modes import (
    IMAGE_MODES,
    IMAGE_MODE_NAMES,
    VISION_MODES,
    VISION_MODE_NAMES,
    IMAGE_GEN_MODES,
    IMAGE_GEN_MODE_NAMES,
    EDITING_MODES,
    EDITING_MODE_NAMES,
    NARRATIVE_MODES,
    NARRATIVE_MODE_NAMES,
    get_image_mode,
)
from .video_modes import (
    VIDEO_MODES,
    VIDEO_MODE_NAMES,
    VIDEO_GEN_MODES,
    VIDEO_GEN_MODE_NAMES,
    VIDEO_ANALYSIS_MODES,
    VIDEO_ANALYSIS_MODE_NAMES,
    get_video_mode,
)
from .tts_modes import (
    TTS_MODES,
    TTS_MODE_NAMES,
    get_tts_mode,
    TEXT_TO_AUDIO_MODES,
    TEXT_TO_AUDIO_MODE_NAMES,
    get_text_to_audio_mode,
    SPEECH_TO_TEXT_MODES,
    SPEECH_TO_TEXT_MODE_NAMES,
    get_speech_to_text_mode,
)
from .system_prompts import MODE_SYSTEM_PROMPTS


# ============================================================================
# MODE CATEGORIES AND HELPERS
# ============================================================================

PRIMARY_MODE_CATEGORIES = (
    "text",
    "image",
    "video",
    "tts",
    "text_to_audio",
    "speech_to_text",
)

MODE_CATEGORY_ALIASES = {
    "text": "text",
    "image": "image",
    "video": "video",
    "tts": "tts",
    "text_to_audio": "text_to_audio",
    "text-to-audio": "text_to_audio",
    "audio": "text_to_audio",
    "speech_to_text": "speech_to_text",
    "speech-to-text": "speech_to_text",
    "stt": "speech_to_text",
    "transcription": "speech_to_text",
}

MODE_OPTIONS_BY_FAMILY = {
    "text": set(TEXT_MODE_NAMES),
    "image": set(IMAGE_MODE_NAMES),
    "video": set(VIDEO_MODE_NAMES),
    "tts": set(TTS_MODE_NAMES),
}

OFF_MODE_INSTRUCTION = "Provide only the final response or generation."


def normalize_mode_category(category: str) -> str:
    """Normalize category aliases (e.g. audio -> text_to_audio)."""
    normalized = (category or "").strip().lower()
    return MODE_CATEGORY_ALIASES.get(normalized, "")


# ============================================================================
# NODE-SPECIFIC MODE SETS
# ============================================================================

def get_text_enhancer_modes() -> dict:
    """
    Modes for text-oriented enhancers.
    Includes: Text + Vision + Video Summary + Narrative
    """
    modes = {"Off": ""}
    modes.update(TEXT_MODES)
    modes.update(VISION_MODES)
    modes["📹 Video Summary"] = VIDEO_ANALYSIS_MODES.get("📹 Video Summary", "")
    modes.update(NARRATIVE_MODES)
    return modes


def get_image_gen_modes() -> dict:
    """
    Modes for image generation.
    Includes: Text (subset) + Image Gen + Editing + Character-focused narrative
    """
    relevant_text_modes = [
        "📝 Enhance",
        "📝 Refine",
        "📝 Creative Rewrite",
        "📝 Detailed Visual",
        "📝 Artistic Style",
        "📝 Technical Specs",
        "📝 Ultra Detailed Prompt",
        "📝 Prompt Expansion",
        "📝 Style Transfer Prompt",
        "📝 Negative Prompt",
    ]

    modes = {"Off": ""}
    for mode in relevant_text_modes:
        if mode in TEXT_MODES:
            modes[mode] = TEXT_MODES[mode]

    modes.update(IMAGE_GEN_MODES)
    modes.update(EDITING_MODES)
    modes["🧍 Consistent Character Prompt"] = NARRATIVE_MODES.get("🧍 Consistent Character Prompt", "")
    modes["📸 Recreate This Image Prompt"] = NARRATIVE_MODES.get("📸 Recreate This Image Prompt", "")
    return modes


def get_video_gen_modes() -> dict:
    """Modes for video generation (generation + analysis/I2V guidance)."""
    modes = {"Off": ""}
    modes.update(VIDEO_GEN_MODES)
    modes.update(VIDEO_ANALYSIS_MODES)
    return modes


def get_tts_modes() -> dict:
    """Modes for TTS optimization."""
    return TTS_MODES.copy()


def get_text_to_audio_modes() -> dict:
    """Modes for text-to-audio/music prompt optimization."""
    return TEXT_TO_AUDIO_MODES.copy()


def get_speech_to_text_modes() -> dict:
    """Modes for speech-to-text transcript post-processing."""
    return SPEECH_TO_TEXT_MODES.copy()


def get_lm_studio_modes() -> dict:
    """Modes for LM Studio text/vision enhancer."""
    return get_text_enhancer_modes()


def get_copilot_modes() -> dict:
    """Modes for Copilot-focused prompt guidance (text modes only)."""
    modes = {"Off": ""}
    modes.update(TEXT_MODES)
    return modes


# ============================================================================
# MASTER MODE REGISTRY
# ============================================================================

ALL_MODES = {
    "text": TEXT_MODES,
    "image": IMAGE_MODES,
    "video": VIDEO_MODES,
    "tts": TTS_MODES,
    "text_to_audio": TEXT_TO_AUDIO_MODES,
    "speech_to_text": SPEECH_TO_TEXT_MODES,
}


def get_mode(category: str, mode_name: str) -> str:
    """Get mode instruction text by category and name."""
    normalized_category = normalize_mode_category(category)

    if normalized_category:
        return ALL_MODES.get(normalized_category, {}).get(mode_name, "")

    for primary_category in PRIMARY_MODE_CATEGORIES:
        category_modes = ALL_MODES.get(primary_category, {})
        if mode_name in category_modes:
            return category_modes[mode_name]

    return ""


def get_all_mode_names() -> list:
    """Get all unique mode names across primary categories."""
    all_names = set()
    for primary_category in PRIMARY_MODE_CATEGORIES:
        all_names.update(ALL_MODES.get(primary_category, {}).keys())
    all_names.discard("Off")
    return sorted(list(all_names))


def get_mode_system_prompt(mode_category: str) -> str:
    """Get internal system prompt for a category."""
    normalized_category = normalize_mode_category(mode_category)
    return MODE_SYSTEM_PROMPTS.get(normalized_category, "")


def _infer_mode_category(mode_name: str, mode_category_hint: str = "") -> str:
    normalized_hint = normalize_mode_category(mode_category_hint)
    if mode_name and normalized_hint and mode_name in ALL_MODES.get(normalized_hint, {}):
        return normalized_hint

    if mode_name:
        for primary_category in PRIMARY_MODE_CATEGORIES:
            if mode_name in ALL_MODES.get(primary_category, {}):
                return primary_category

    return normalized_hint


# ============================================================================
# SECTIONED MODE LIST (LEGACY INCLUSIVE DROPDOWN SUPPORT)
# ============================================================================

def get_inclusive_mode_list() -> list:
    """Build sectioned dropdown list with visual separators."""
    sections = [
        ("📝 Text", TEXT_MODE_NAMES),
        ("🖼️ Image", IMAGE_MODE_NAMES),
        ("🎥 Video", VIDEO_MODE_NAMES),
        ("🎤 TTS", TTS_MODE_NAMES),
        ("🔊 Text to Audio", TEXT_TO_AUDIO_MODE_NAMES),
        ("🧾 Speech to Text", SPEECH_TO_TEXT_MODE_NAMES),
    ]

    result = ["Off"]
    for section_name, mode_names in sections:
        modes = [mode for mode in mode_names if mode and mode != "Off"]
        if modes:
            result.append(f"───── {section_name} ─────")
            result.extend(modes)

    return result


INCLUSIVE_MODE_LIST = get_inclusive_mode_list()


# ============================================================================
# GROUPED MODE FAMILY RESOLUTION
# ============================================================================

def resolve_mode_family_preset(
    text_mode_enabled: bool = False,
    text_mode: str = "Off",
    image_mode_enabled: bool = False,
    image_mode: str = "Off",
    video_mode_enabled: bool = False,
    video_mode: str = "Off",
    tts_mode_enabled: bool = False,
    tts_mode: str = "Off",
) -> str:
    """
    Resolve grouped mode-family toggles to a single mode preset.

    Rules:
    - zero enabled families -> Off
    - one enabled family -> selected mode from that family (or Off)
    - more than one enabled family -> ValueError
    """
    toggles = [
        ("text", bool(text_mode_enabled), (text_mode or "Off").strip()),
        ("image", bool(image_mode_enabled), (image_mode or "Off").strip()),
        ("video", bool(video_mode_enabled), (video_mode or "Off").strip()),
        ("tts", bool(tts_mode_enabled), (tts_mode or "Off").strip()),
    ]

    enabled = [(family, selected_mode) for family, is_enabled, selected_mode in toggles if is_enabled]

    if len(enabled) > 1:
        enabled_families = ", ".join(family for family, _ in enabled)
        raise ValueError(f"Only one mode family can be enabled at a time. Enabled: {enabled_families}")

    if not enabled:
        return "Off"

    family, selected_mode = enabled[0]
    if selected_mode == "Off":
        return "Off"

    if selected_mode not in MODE_OPTIONS_BY_FAMILY[family]:
        raise ValueError(f"Invalid {family} mode selection: '{selected_mode}'")

    return selected_mode


def resolve_mode_preset(
    mode_preset: str,
    custom_instructions: str,
    mode_category_hint: str = "",
    include_system_prompt: bool = True,
) -> str:
    """
    Resolve instruction text from mode + custom instructions.

    Precedence:
    1. custom instructions override mode-specific instruction content
    2. mode "Off" with no custom instructions returns OFF_MODE_INSTRUCTION
    3. blank/separator modes with no custom instructions return ""
    4. prepend category internal system prompt before resolved instruction when enabled
    """
    custom = (custom_instructions or "").strip()
    mode = (mode_preset or "").strip()

    is_off_mode = mode == "Off"
    mode_disabled = (not mode) or is_off_mode or is_separator(mode)
    category = _infer_mode_category(mode if not mode_disabled else "", mode_category_hint=mode_category_hint)

    if custom:
        if include_system_prompt and (not mode_disabled) and category:
            system_prompt = get_mode_system_prompt(category)
            if system_prompt:
                return f"{system_prompt}\n\n{custom}"
        return custom

    if mode_disabled:
        if is_off_mode:
            return OFF_MODE_INSTRUCTION
        return ""

    mode_instruction = get_mode(category, mode)
    if not mode_instruction:
        return ""

    if include_system_prompt and category:
        system_prompt = get_mode_system_prompt(category)
        if system_prompt:
            return f"{system_prompt}\n\n{mode_instruction}"

    return mode_instruction


def is_separator(mode_name: str) -> bool:
    """Check if a mode name is a visual dropdown separator."""
    return (mode_name or "").startswith("─")


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Text (canonical)
    "TEXT_MODES",
    "TEXT_MODE_NAMES",
    "get_text_mode",
    # Image
    "IMAGE_MODES",
    "IMAGE_MODE_NAMES",
    "VISION_MODES",
    "VISION_MODE_NAMES",
    "IMAGE_GEN_MODES",
    "IMAGE_GEN_MODE_NAMES",
    "EDITING_MODES",
    "EDITING_MODE_NAMES",
    "NARRATIVE_MODES",
    "NARRATIVE_MODE_NAMES",
    "get_image_mode",
    # Video
    "VIDEO_MODES",
    "VIDEO_MODE_NAMES",
    "VIDEO_GEN_MODES",
    "VIDEO_GEN_MODE_NAMES",
    "VIDEO_ANALYSIS_MODES",
    "VIDEO_ANALYSIS_MODE_NAMES",
    "get_video_mode",
    # TTS
    "TTS_MODES",
    "TTS_MODE_NAMES",
    "get_tts_mode",
    "TEXT_TO_AUDIO_MODES",
    "TEXT_TO_AUDIO_MODE_NAMES",
    "get_text_to_audio_mode",
    "SPEECH_TO_TEXT_MODES",
    "SPEECH_TO_TEXT_MODE_NAMES",
    "get_speech_to_text_mode",
    # Node-specific getters
    "get_text_enhancer_modes",
    "get_image_gen_modes",
    "get_video_gen_modes",
    "get_tts_modes",
    "get_text_to_audio_modes",
    "get_speech_to_text_modes",
    "get_lm_studio_modes",
    "get_copilot_modes",
    # Registry and resolvers
    "ALL_MODES",
    "MODE_SYSTEM_PROMPTS",
    "normalize_mode_category",
    "get_mode",
    "get_mode_system_prompt",
    "get_all_mode_names",
    "INCLUSIVE_MODE_LIST",
    "get_inclusive_mode_list",
    "resolve_mode_family_preset",
    "resolve_mode_preset",
    "is_separator",
]
