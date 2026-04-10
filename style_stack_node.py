"""Standalone style-stack utility node for composing additional style guidance."""

from __future__ import annotations

from typing import Tuple

from .prompt_styles import (
    STYLE_OFF_LABEL,
    get_style_options,
    get_style_stack_default,
    normalize_style_presets,
    resolve_style_instruction_stack,
)


class GZ_StyleStackNode:
    """Build stacked style instructions from up to seven dropdown presets."""

    CATEGORY = "OVERTLI STUDIO/Prompt"
    FUNCTION = "execute"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("additional_styles",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        style_options = get_style_options()
        return {
            "required": {
                "style_preset_1": (
                    style_options,
                    {"default": get_style_stack_default()},
                ),
                "style_preset_2": (
                    style_options,
                    {"default": STYLE_OFF_LABEL},
                ),
                "style_preset_3": (
                    style_options,
                    {"default": STYLE_OFF_LABEL},
                ),
                "style_preset_4": (
                    style_options,
                    {"default": STYLE_OFF_LABEL},
                ),
                "style_preset_5": (
                    style_options,
                    {"default": STYLE_OFF_LABEL},
                ),
                "style_preset_6": (
                    style_options,
                    {"default": STYLE_OFF_LABEL},
                ),
                "style_preset_7": (
                    style_options,
                    {"default": STYLE_OFF_LABEL},
                ),
            }
        }

    def execute(
        self,
        style_preset_1: str,
        style_preset_2: str,
        style_preset_3: str,
        style_preset_4: str,
        style_preset_5: str,
        style_preset_6: str,
        style_preset_7: str,
    ) -> Tuple[str]:
        style_labels = normalize_style_presets(
            style_preset_1=style_preset_1,
            style_preset_2=style_preset_2,
            style_preset_3=style_preset_3,
            style_preset_4=style_preset_4,
            style_preset_5=style_preset_5,
            style_preset_6=style_preset_6,
            style_preset_7=style_preset_7,
        )
        style_stack = resolve_style_instruction_stack(style_labels=style_labels, mode_category="text")
        return (style_stack,)
