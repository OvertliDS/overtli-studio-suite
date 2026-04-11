"""
OVERTLI STUDIO LLM Suite - Shared Utilities

Central utilities including the 3-Layer Instruction Stack.
This module provides common functions used across all nodes.
"""

import logging
from typing import Optional, Tuple, Dict, Any, List

# Local imports
from .instruction_modes import (
    get_mode,
    resolve_mode_preset,
    get_text_enhancer_modes,
    get_image_gen_modes,
    get_video_gen_modes,
    get_tts_modes,
    get_lm_studio_modes,
    get_copilot_modes,
    ALL_MODES,
)
from .exceptions import OvertliInputError
from .styles import STYLE_OFF_LABEL, append_style_layers_to_prompt, normalize_style_presets


# ============================================================================
# LOGGING SETUP
# ============================================================================

logger = logging.getLogger("OvertliStudioLLM")


def setup_logging(level: str = "INFO") -> None:
    """Configure logging for the OVERTLI STUDIO LLM Suite."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "[%(name)s] %(levelname)s: %(message)s"
        ))
        logger.addHandler(handler)


def build_user_facing_error(
    title: str,
    *,
    what_happened: str,
    what_we_tried: str = "",
    next_steps: str = "",
    details: str = "",
) -> str:
    """Create a structured, user-friendly diagnostic message.

    The format is intentionally consistent across providers so errors are easy to
    scan in ComfyUI terminal logs and in raised exceptions.
    """
    lines: list[str] = [title.strip()]

    happened = normalize_string_input(what_happened)
    tried = normalize_string_input(what_we_tried)
    next_step = normalize_string_input(next_steps)
    extra = normalize_string_input(details)

    if happened:
        lines.append(f"What happened: {happened}")
    if tried:
        lines.append(f"What we tried: {tried}")
    if next_step:
        lines.append(f"What to do next: {next_step}")
    if extra:
        lines.append(f"Details: {extra}")

    return "\n".join(lines)


# ============================================================================
# 3-LAYER INSTRUCTION STACK
# ============================================================================

def build_prompt(
    mode_preset: str,
    custom_instructions: str,
    raw_prompt: str,
    mode_category: str = "text",
    style_preset_1: str = STYLE_OFF_LABEL,
    style_preset_2: str = STYLE_OFF_LABEL,
    style_preset_3: str = STYLE_OFF_LABEL,
    additional_styles: str = "",
) -> str:
    """
    Build the final prompt using the 3-Layer Instruction Stack.

    Flow:
    1. Resolve system+instruction layer from mode/custom settings.
    2. Keep user raw_prompt as the core user layer.
    3. Append selected style guidance directly after the user prompt.

    Args:
        mode_preset: Name of the mode preset (e.g., "📝 Enhance")
        custom_instructions: User-provided custom instruction text
        raw_prompt: The core prompt/idea to process
        mode_category: Category hint for mode lookup ('text', 'image', 'video', 'tts')

    Returns:
        str: The assembled prompt ready for LLM processing

    Example:
        >>> build_prompt("📝 Enhance", "", "A cat on the moon")
        "[📝 Enhance instruction text]\\n\\nA cat on the moon"

        >>> build_prompt("📝 Enhance", "You are a poet.", "A cat on the moon")
        "You are a poet.\\n\\nA cat on the moon"  # Mode ignored!
    """
    # Normalize inputs
    raw = (raw_prompt or "").strip()
    mode = (mode_preset or "").strip()

    base_instruction = resolve_mode_preset(
        mode_preset=mode,
        custom_instructions=custom_instructions,
        mode_category_hint=mode_category,
        include_system_prompt=True,
    )

    style_labels = normalize_style_presets(
        style_preset_1=style_preset_1,
        style_preset_2=style_preset_2,
        style_preset_3=style_preset_3,
    )
    raw_with_style = append_style_layers_to_prompt(
        raw_prompt=raw,
        style_labels=style_labels,
        mode_category=mode_category,
        additional_styles=additional_styles,
    )

    # Assemble final prompt
    parts = [p for p in [base_instruction, raw_with_style] if p]
    return "\n\n".join(parts)


def get_mode_instruction(mode_name: str, category: str = "text") -> str:
    """
    Get the instruction text for a mode preset.

    Args:
        mode_name: Name of the mode (with emoji prefix)
        category: Category to search in ('text', 'image', 'video', 'tts')

    Returns:
        str: The instruction prompt, or empty string if not found
    """
    # First try the specified category
    instruction = get_mode(category, mode_name)
    if instruction:
        return instruction

    # Fallback: search all categories
    for cat_name, cat_modes in ALL_MODES.items():
        if mode_name in cat_modes:
            return cat_modes[mode_name]

    logger.warning(f"Mode '{mode_name}' not found in any category")
    return ""


def build_chat_messages(
    system_prompt: str,
    user_prompt: str,
    image_data_url: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Build OpenAI-compatible chat messages array.

    Args:
        system_prompt: System/instruction message
        user_prompt: User's prompt text
        image_data_url: Optional base64 data URL for vision models

    Returns:
        List of message dicts for chat API
    """
    messages = []

    # System message (if provided)
    if system_prompt:
        messages.append({
            "role": "system",
            "content": system_prompt
        })

    # User message
    if image_data_url:
        # Multimodal: text + image
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": user_prompt},
                {"type": "image_url", "image_url": {"url": image_data_url}}
            ]
        })
    else:
        # Text only
        messages.append({
            "role": "user",
            "content": user_prompt
        })

    return messages


def split_instruction_and_prompt(full_prompt: str) -> Tuple[str, str]:
    """
    Split a combined prompt back into instruction and raw prompt parts.

    Used when we need to separate system and user content for chat APIs.
    Looks for double newline as separator.

    Args:
        full_prompt: Combined prompt from build_prompt()

    Returns:
        Tuple[str, str]: (instruction_part, prompt_part)
    """
    if "\n\n" in full_prompt:
        parts = full_prompt.split("\n\n", 1)
        return parts[0], parts[1]
    return "", full_prompt


# ============================================================================
# INPUT VALIDATION HELPERS
# ============================================================================

def validate_single_image_source(
    image_tensor: Any = None,
    file_path: Optional[str] = None,
    base64_data: Optional[str] = None,
) -> Tuple[str, Any]:
    """
    Validate that only one image source is provided.

    Precedence: IMAGE_TENSOR > FILE_PATH > BASE64

    Args:
        image_tensor: ComfyUI IMAGE tensor
        file_path: Path to image file
        base64_data: Base64 encoded image

    Returns:
        Tuple[str, Any]: (source_type, source_value) where source_type is
                         'tensor', 'file', 'base64', or 'none'

    Raises:
        OvertliInputError: If multiple sources are provided
    """
    sources = []

    if image_tensor is not None:
        sources.append(("tensor", image_tensor))
    if file_path and str(file_path).strip():
        sources.append(("file", file_path))
    if base64_data and str(base64_data).strip():
        sources.append(("base64", base64_data))

    if len(sources) > 1:
        source_names = [s[0] for s in sources]
        raise OvertliInputError(
            f"Only one image source allowed. Got: {', '.join(source_names)}",
            input_name="image_source"
        )

    if sources:
        return sources[0]
    return ("none", None)


def normalize_string_input(value: Any, default: str = "") -> str:
    """
    Normalize various input types to string.

    Handles None, empty strings, and whitespace-only strings.

    Args:
        value: Input value (str, None, or other)
        default: Default value if input is empty/None

    Returns:
        str: Normalized string
    """
    if value is None:
        return default
    s = str(value).strip()
    return s if s else default


def is_truthy(value: Any) -> bool:
    """
    Check if a value is truthy in a UI context.

    Handles booleans, strings like "true"/"false", and numeric values.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "on")
    if isinstance(value, (int, float)):
        return value != 0
    return bool(value)


def select_image_batch_indices(
    batch_size: int,
    batch_image_mode: str = "all_frames",
    max_batch_frames: int = 0,
) -> List[int]:
    """
    Select frame indices from a ComfyUI IMAGE batch according to a mode.

    Args:
        batch_size: Number of frames in the IMAGE batch dimension.
        batch_image_mode: One of "all_frames", "first_middle_last", "first_frame".
        max_batch_frames: Optional cap for "all_frames" mode. 0 means unlimited.

    Returns:
        Ordered list of unique frame indices.
    """
    if batch_size <= 0:
        return []

    mode = (batch_image_mode or "all_frames").strip().lower()

    if mode == "first_frame":
        return [0]

    if mode == "first_middle_last":
        if batch_size == 1:
            return [0]
        if batch_size == 2:
            return [0, 1]
        mid = batch_size // 2
        return [0, mid, batch_size - 1]

    # Default to all frames.
    if max_batch_frames > 0:
        return list(range(min(batch_size, max_batch_frames)))
    return list(range(batch_size))


# ============================================================================
# MODEL TAG UTILITIES
# ============================================================================

def format_model_display_name(model_data: Dict[str, Any]) -> str:
    """
    Format a model's display name with capability tags.

    Pollinations model data has boolean flags (not string tags).
    This creates a user-friendly display name.

    Args:
        model_data: Model dict from Pollinations API

    Returns:
        str: Formatted name like "openai-large [vision] [reasoning]"

    Example:
        >>> format_model_display_name({"name": "gpt-5", "vision": True, "reasoning": True})
        "gpt-5 [vision] [reasoning]"
    """
    name = model_data.get("name", "unknown")
    tags = []

    # Capability flags
    if model_data.get("vision"):
        tags.append("[vision]")
    if model_data.get("reasoning"):
        tags.append("[reasoning]")
    if model_data.get("audio"):
        tags.append("[audio]")
    if model_data.get("tools"):
        tags.append("[tools]")

    # Tier/access flags
    tier = model_data.get("tier", "")
    if model_data.get("paid_only"):
        tags.append("[paid]")
    elif tier == "seed":
        tags.append("[seed]")
    elif tier == "anonymous":
        tags.append("[free]")

    if model_data.get("community"):
        tags.append("[community]")

    if tags:
        return f"{name} {' '.join(tags)}"
    return name


def filter_models_by_capability(
    models: List[Dict[str, Any]],
    require_vision: bool = False,
    require_audio: bool = False,
    exclude_paid: bool = False,
) -> List[Dict[str, Any]]:
    """
    Filter a list of models by capability requirements.

    Args:
        models: List of model dicts from Pollinations API
        require_vision: Only include vision-capable models
        require_audio: Only include audio-capable models
        exclude_paid: Exclude paid-only models

    Returns:
        List of models matching the criteria
    """
    result = []
    for model in models:
        if require_vision and not model.get("vision"):
            continue
        if require_audio and not model.get("audio"):
            continue
        if exclude_paid and model.get("paid_only"):
            continue
        result.append(model)
    return result


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Logging
    "logger",
    "setup_logging",
    "build_user_facing_error",

    # 3-Layer Instruction Stack
    "build_prompt",
    "get_mode_instruction",
    "build_chat_messages",
    "split_instruction_and_prompt",

    # Input validation
    "validate_single_image_source",
    "normalize_string_input",
    "is_truthy",

    # Model utilities
    "format_model_display_name",
    "filter_models_by_capability",
]

