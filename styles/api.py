from __future__ import annotations

import re
from typing import cast

from .catalog import RAW_PROMPT_STYLES
from .types import PromptStyle, STYLE_OFF_LABEL

_STYLE_CATEGORY_FALLBACK = "Other / Misc"
_DEFAULT_STYLE_KEY = "photograph_real_life"


def _style_label_sort_key(label: str) -> str:
    return label.split("[", 1)[0].strip().casefold()


def _categorize_and_sort_styles(styles: list[PromptStyle]) -> list[PromptStyle]:
    categorized: list[PromptStyle] = []
    seen_keys: set[str] = set()

    for style in styles:
        key = (style.get("key") or "").strip()
        if key:
            if key in seen_keys:
                continue
            seen_keys.add(key)

        raw_label = (style.get("raw_label") or style["label"]).strip()
        category = (style.get("main_category") or _STYLE_CATEGORY_FALLBACK).strip() or _STYLE_CATEGORY_FALLBACK
        display_label = f"{category} :: {raw_label}"

        categorized.append(
            cast(
                PromptStyle,
                {
                    **style,
                    "raw_label": raw_label,
                    "main_category": category,
                    "label": display_label,
                },
            )
        )

    categorized.sort(
        key=lambda style: (
            style.get("main_category", _STYLE_CATEGORY_FALLBACK).casefold(),
            _style_label_sort_key(style.get("raw_label") or style["label"]),
        )
    )
    return categorized


PROMPT_STYLES = _categorize_and_sort_styles(RAW_PROMPT_STYLES)

_STYLE_BY_LABEL: dict[str, PromptStyle] = {}
for style in PROMPT_STYLES:
    decorated_label = (style.get("label") or "").strip()
    raw_label = (style.get("raw_label") or "").strip()
    base_raw_label = re.sub(r"\s*\[[^\]]+\]", "", raw_label).strip()

    if decorated_label:
        _STYLE_BY_LABEL[decorated_label] = style
    if raw_label:
        _STYLE_BY_LABEL[raw_label] = style
    if base_raw_label:
        _STYLE_BY_LABEL.setdefault(base_raw_label, style)

_STYLE_LABELS: list[str] = [STYLE_OFF_LABEL] + [style["label"] for style in PROMPT_STYLES]


def get_style_options() -> list[str]:
    return list(_STYLE_LABELS)


def get_style_stack_default() -> str:
    for style in PROMPT_STYLES:
        if style["key"] == _DEFAULT_STYLE_KEY:
            return style["label"]
    return _STYLE_LABELS[1] if len(_STYLE_LABELS) > 1 else STYLE_OFF_LABEL


def get_style_tags() -> list[str]:
    tags = {"all"}
    for style in PROMPT_STYLES:
        for tag in style["tags"]:
            tags.add(tag)
    return sorted(tags)


def get_style_metadata(style_label: str) -> PromptStyle | None:
    return _STYLE_BY_LABEL.get((style_label or "").strip())


def infer_mode_category(mode_preset: str, fallback: str = "text") -> str:
    mode_name = (mode_preset or "").strip()
    if not mode_name or mode_name == "Off":
        return fallback

    try:
        from ..instruction_modes import ALL_MODES

        for category, mode_map in ALL_MODES.items():
            if mode_name in mode_map:
                return category
    except Exception:
        return fallback

    return fallback


def should_apply_style(mode_category: str) -> bool:
    normalized = (mode_category or "").strip().lower()
    return normalized not in {"tts", "text_to_audio", "speech_to_text", "stt"}


def resolve_style_instruction(style_label: str, mode_category: str) -> str:
    selected = (style_label or "").strip()
    if not selected or selected == STYLE_OFF_LABEL:
        return ""

    if not should_apply_style(mode_category):
        return ""

    style_data = get_style_metadata(selected)
    if not style_data:
        return ""

    description = style_data["description"].strip()
    instruction = style_data["instruction"].strip()
    tags = ", ".join(style_data["tags"]) if style_data["tags"] else ""
    selected_style = (style_data.get("raw_label") or style_data["label"]).strip()
    main_category = (style_data.get("main_category") or "").strip()

    block_parts = [
        "Style requirements:",
        f"- Selected style: {selected_style}",
    ]
    if main_category:
        block_parts.append(f"- Main category: {main_category}")
    if tags:
        block_parts.append(f"- Style tags: {tags}")
    if description:
        block_parts.append(f"- Description: {description}")
    block_parts.append(f"- Execution guidance: {instruction}")
    block_parts.append("- Preserve the user subject, intent, and constraints while applying this style.")

    return "\n".join(block_parts)


def normalize_style_presets(
    style_preset_1: str = STYLE_OFF_LABEL,
    style_preset_2: str = STYLE_OFF_LABEL,
    style_preset_3: str = STYLE_OFF_LABEL,
    style_preset_4: str = STYLE_OFF_LABEL,
    style_preset_5: str = STYLE_OFF_LABEL,
    style_preset_6: str = STYLE_OFF_LABEL,
    style_preset_7: str = STYLE_OFF_LABEL,
) -> list[str]:
    ordered = [
        style_preset_1,
        style_preset_2,
        style_preset_3,
        style_preset_4,
        style_preset_5,
        style_preset_6,
        style_preset_7,
    ]
    selected: list[str] = []

    for value in ordered:
        label = (value or "").strip()
        if label and label != STYLE_OFF_LABEL:
            selected.append(label)

    return selected


def resolve_style_instruction_stack(style_labels: list[str], mode_category: str) -> str:
    blocks: list[str] = []
    for label in style_labels:
        block = resolve_style_instruction(label, mode_category)
        if block:
            blocks.append(block)
    return "\n\n".join(blocks)


def append_style_to_prompt(raw_prompt: str, style_instruction: str) -> str:
    raw_text = (raw_prompt or "").strip()
    style_text = (style_instruction or "").strip()

    if raw_text and style_text:
        return f"{raw_text}\n\n{style_text}".strip()
    return raw_text or style_text


def append_style_stack_to_prompt(raw_prompt: str, style_labels: list[str], mode_category: str) -> str:
    style_stack = resolve_style_instruction_stack(style_labels=style_labels, mode_category=mode_category)
    return append_style_to_prompt(raw_prompt=raw_prompt, style_instruction=style_stack)


def append_additional_styles_to_prompt(raw_prompt: str, additional_styles: str) -> str:
    return append_style_to_prompt(raw_prompt=raw_prompt, style_instruction=additional_styles)


def append_style_layers_to_prompt(
    raw_prompt: str,
    style_labels: list[str],
    mode_category: str,
    additional_styles: str = "",
) -> str:
    prompt_with_local_styles = append_style_stack_to_prompt(
        raw_prompt=raw_prompt,
        style_labels=style_labels,
        mode_category=mode_category,
    )
    return append_additional_styles_to_prompt(
        raw_prompt=prompt_with_local_styles,
        additional_styles=additional_styles,
    )


__all__ = [
    "PromptStyle",
    "STYLE_OFF_LABEL",
    "PROMPT_STYLES",
    "get_style_options",
    "get_style_stack_default",
    "get_style_tags",
    "get_style_metadata",
    "infer_mode_category",
    "should_apply_style",
    "resolve_style_instruction",
    "normalize_style_presets",
    "resolve_style_instruction_stack",
    "append_style_to_prompt",
    "append_style_stack_to_prompt",
    "append_additional_styles_to_prompt",
    "append_style_layers_to_prompt",
]
