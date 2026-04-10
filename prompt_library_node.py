"""ComfyUI node for persistent prompt-library save/load/view workflows."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, Sequence, Tuple

from .exceptions import OvertliInputError
from .prompt_library_store import (
    PromptEntry,
    delete_prompt_entry,
    get_prompt_categories,
    get_prompt_entry,
    get_prompt_names,
    list_prompt_entries,
    load_prompt_library,
    upsert_prompt_entry,
)
from .shared_utils import normalize_string_input


_ACTION_OPTIONS = [
    "save_prompt",
    "load_prompt",
    "view_library",
    "delete_prompt",
    "refresh_cache",
]

_SORT_OPTIONS = [
    "most_recent",
    "name_az",
    "name_za",
    "oldest_first",
    "most_used",
    "category_az",
]


def _prompt_name_options() -> list[str]:
    names = get_prompt_names(sort_mode="most_recent", limit=1000)
    return ["(none)"] + names


def _category_options() -> list[str]:
    categories = get_prompt_categories()
    return ["All"] + categories


def _derive_prompt_name(prompt_text: str) -> str:
    text = (prompt_text or "").strip()
    if not text:
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        return f"Prompt {timestamp}"

    first_line = text.splitlines()[0]
    normalized = re.sub(r"\s+", " ", first_line).strip()
    compact = re.sub(r"[^\w\-\s]", "", normalized, flags=re.UNICODE).strip()
    if not compact:
        compact = "Prompt"

    words = compact.split(" ")
    short_name = " ".join(words[:8]).strip()
    if len(short_name) > 80:
        short_name = short_name[:80].rstrip()
    return short_name or "Prompt"


def _resolve_prompt_name(prompt_name: str, selected_prompt: str, prompt_text: str) -> str:
    typed_name = normalize_string_input(prompt_name)
    if typed_name:
        return typed_name

    selected = normalize_string_input(selected_prompt)
    if selected and selected != "(none)":
        return selected

    return _derive_prompt_name(prompt_text)


def _resolve_category(category: str, category_pick: str) -> str:
    typed = normalize_string_input(category)
    if typed:
        return typed

    selected = normalize_string_input(category_pick)
    if selected and selected != "All":
        return selected

    return "General"


def _format_library_listing(
    entries: Sequence[PromptEntry],
    sort_mode: str,
    category_filter: str,
) -> str:
    if not entries:
        return "Prompt Library is empty for the current filters."

    lines = [
        f"Prompt Library View ({len(entries)} item(s), sort={sort_mode}, category={category_filter})",
        "",
    ]

    for idx, entry in enumerate(entries, start=1):
        tags = ", ".join(entry.get("tags", [])) or "-"
        lines.append(
            f"[{idx}] {entry['name']} | category={entry.get('category', 'General')} | uses={entry.get('uses', 0)} | updated={entry.get('updated_at', '')} | tags={tags}"
        )
        lines.append(entry.get("prompt", ""))
        lines.append("---")

    return "\n".join(lines)


class GZ_PromptLibraryNode:
    """Prompt library node with mode-driven UX and copy-friendly library preview."""

    CATEGORY = "OVERTLI STUDIO/Prompt"
    FUNCTION = "execute"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt_text",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "action": (_ACTION_OPTIONS, {"default": "save_prompt"}),
                "prompt_text": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "placeholder": "Type or connect prompt text here...",
                    },
                ),
            },
            "optional": {
                "prompt_name": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "placeholder": "Optional prompt name (auto-derived if empty)",
                    },
                ),
                "saved_prompt": (_prompt_name_options(), {"default": "(none)"}),
                "category": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "placeholder": "Optional category for save_prompt",
                    },
                ),
                "category_pick": (_category_options(), {"default": "All"}),
                "tags_csv": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "placeholder": "Optional comma-separated tags for save_prompt",
                    },
                ),
                "notes": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "placeholder": "Optional notes for save_prompt",
                    },
                ),
                "sort_mode": (_SORT_OPTIONS, {"default": "most_recent"}),
                "category_filter": (_category_options(), {"default": "All"}),
                "search_query": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "placeholder": "Optional filter: name, prompt, category, or tags",
                    },
                ),
                "max_items": (
                    "INT",
                    {
                        "default": 100,
                        "min": 1,
                        "max": 1000,
                        "step": 1,
                    },
                ),
                "allow_overwrite": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "label_on": "Overwrite Existing",
                        "label_off": "Do Not Overwrite",
                    },
                ),
                "increment_use_on_load": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "label_on": "Increment Usage",
                        "label_off": "Read Only",
                    },
                ),
                "refresh_before_action": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "label_on": "Refresh Before Run",
                        "label_off": "Use Cached",
                    },
                ),
                "show_library_snapshot": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "label_on": "Show Library Snapshot",
                        "label_off": "Status Only",
                    },
                ),
            },
        }

    def execute(
        self,
        action: str,
        prompt_text: str,
        prompt_name: str = "",
        saved_prompt: str = "(none)",
        category: str = "",
        category_pick: str = "All",
        tags_csv: str = "",
        notes: str = "",
        sort_mode: str = "most_recent",
        category_filter: str = "All",
        search_query: str = "",
        max_items: int = 100,
        allow_overwrite: bool = True,
        increment_use_on_load: bool = True,
        refresh_before_action: bool = True,
        show_library_snapshot: bool = True,
    ) -> Any:
        selected_action = normalize_string_input(action, default="save_prompt").lower()
        if selected_action not in _ACTION_OPTIONS:
            raise OvertliInputError(f"Unsupported action '{action}'", input_name="action")

        if refresh_before_action or selected_action == "refresh_cache":
            load_prompt_library(force_reload=True)

        target_name = _resolve_prompt_name(prompt_name, saved_prompt, prompt_text)
        resolved_category = _resolve_category(category, category_pick)

        status_lines: list[str] = []
        output_text = ""

        try:
            if selected_action == "save_prompt":
                cleaned_prompt_text = normalize_string_input(prompt_text)
                if not cleaned_prompt_text:
                    raise OvertliInputError("prompt_text is required for save_prompt", input_name="prompt_text")

                entry = upsert_prompt_entry(
                    name=target_name,
                    prompt=cleaned_prompt_text,
                    category=resolved_category,
                    tags=tags_csv,
                    notes=notes,
                    allow_overwrite=allow_overwrite,
                )
                output_text = entry["prompt"]
                status_lines.append(f"Saved prompt '{entry['name']}' in category '{entry.get('category', 'General')}'.")

            elif selected_action == "load_prompt":
                entry = None
                if target_name and target_name != "Prompt":
                    entry = get_prompt_entry(target_name, increment_use_count=increment_use_on_load)

                if not entry:
                    fallback_entries = list_prompt_entries(
                        sort_mode=sort_mode,
                        category_filter=category_filter,
                        search_query=search_query,
                        limit=max_items,
                    )
                    if fallback_entries:
                        entry = get_prompt_entry(
                            fallback_entries[0]["name"],
                            increment_use_count=increment_use_on_load,
                        )

                if not entry:
                    status_lines.append("No prompt could be loaded for the current selection/filter.")
                    output_text = ""
                else:
                    output_text = entry["prompt"]
                    status_lines.append(f"Loaded prompt '{entry['name']}' (uses={entry.get('uses', 0)}).")

            elif selected_action == "delete_prompt":
                if not target_name:
                    raise OvertliInputError("prompt_name or saved_prompt is required for delete_prompt", input_name="prompt_name")

                removed = delete_prompt_entry(target_name)
                if removed:
                    status_lines.append(f"Deleted prompt '{target_name}'.")
                else:
                    status_lines.append(f"Prompt '{target_name}' was not found.")

            elif selected_action == "refresh_cache":
                load_prompt_library(force_reload=True)
                status_lines.append("Prompt library cache refreshed.")

            elif selected_action == "view_library":
                status_lines.append("Prompt library view generated.")

        except OvertliInputError:
            raise
        except ValueError as exc:
            raise OvertliInputError(str(exc), input_name="prompt_library") from exc
        except Exception as exc:  # noqa: BLE001
            raise OvertliInputError(f"Prompt library action failed: {exc}", input_name="prompt_library") from exc

        entries = list_prompt_entries(
            sort_mode=sort_mode,
            category_filter=category_filter,
            search_query=search_query,
            limit=max_items,
        )
        listing_text = _format_library_listing(entries, sort_mode=sort_mode, category_filter=category_filter)

        category_summary = ", ".join(get_prompt_categories()) or "General"
        status_text = "\n".join(status_lines) if status_lines else "No action status."

        ui_blocks = [status_text, f"Categories: {category_summary}"]
        if show_library_snapshot or selected_action == "view_library":
            ui_blocks.extend(["", listing_text])

        ui_text = "\n".join(ui_blocks).strip()

        if selected_action == "view_library":
            final_output = listing_text
        elif selected_action in {"delete_prompt", "refresh_cache"} and show_library_snapshot:
            final_output = listing_text
        else:
            final_output = output_text

        return {
            "ui": {"text": (ui_text,)},
            "result": (final_output,),
        }


__all__ = ["GZ_PromptLibraryNode"]
