"""
Persistent prompt-library storage for OVERTLI prompt-saving workflows.

Stores reusable prompts with metadata:
- name
- category
- prompt text
- tags
- notes
- created/updated timestamps
- usage count
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from datetime import datetime, UTC
from typing import Any, TypedDict


logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
PROMPT_LIBRARY_FILENAME = "overtli_prompt_library.json"


class PromptEntry(TypedDict):
    name: str
    category: str
    prompt: str
    tags: list[str]
    notes: str
    created_at: str
    updated_at: str
    uses: int


class PromptLibrary(TypedDict):
    schema_version: int
    entries: list[PromptEntry]


DEFAULT_LIBRARY: PromptLibrary = {
    "schema_version": SCHEMA_VERSION,
    "entries": [],
}


_CACHE_LOCK = threading.Lock()
_CACHE_MTIME: float = -1.0
_CACHE_DATA: PromptLibrary | None = None


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _sanitize_text(value: Any, max_length: int = 200_000) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if len(text) > max_length:
        return text[:max_length]
    return text


def _sanitize_name(value: Any) -> str:
    name = _sanitize_text(value, max_length=200)
    return " ".join(name.split())


def _sanitize_category(value: Any) -> str:
    category = _sanitize_text(value, max_length=120)
    category = " ".join(category.split())
    return category or "General"


def _sanitize_tags(value: Any) -> list[str]:
    if isinstance(value, str):
        raw_items = [part.strip() for part in value.split(",")]
    elif isinstance(value, (list, tuple, set)):
        raw_items = [_sanitize_text(item, max_length=40) for item in value]
    else:
        raw_items = []

    tags: list[str] = []
    for item in raw_items:
        cleaned = " ".join(item.strip().split())
        if cleaned and cleaned not in tags:
            tags.append(cleaned)
    return tags[:16]


def _sanitize_uses(value: Any) -> int:
    try:
        uses = int(value)
    except (TypeError, ValueError):
        uses = 0
    if uses < 0:
        return 0
    return uses


def _get_store_dir() -> str:
    try:
        import folder_paths  # type: ignore

        if hasattr(folder_paths, "get_user_directory"):
            base = folder_paths.get_user_directory()
        elif hasattr(folder_paths, "base_path"):
            base = os.path.join(folder_paths.base_path, "user")
        else:
            base = os.path.join(os.path.expanduser("~"), ".overtli_studio")
    except Exception:
        base = os.path.join(os.path.expanduser("~"), ".overtli_studio")

    os.makedirs(base, exist_ok=True)
    return base


def get_prompt_library_path() -> str:
    return os.path.join(_get_store_dir(), PROMPT_LIBRARY_FILENAME)


def _normalize_entry(raw: Any) -> PromptEntry | None:
    if not isinstance(raw, dict):
        return None

    name = _sanitize_name(raw.get("name"))
    prompt = _sanitize_text(raw.get("prompt"), max_length=400_000)
    if not name or not prompt:
        return None

    created_at = _sanitize_text(raw.get("created_at"), max_length=64) or _utc_now_iso()
    updated_at = _sanitize_text(raw.get("updated_at"), max_length=64) or created_at

    return {
        "name": name,
        "category": _sanitize_category(raw.get("category")),
        "prompt": prompt,
        "tags": _sanitize_tags(raw.get("tags", [])),
        "notes": _sanitize_text(raw.get("notes"), max_length=2000),
        "created_at": created_at,
        "updated_at": updated_at,
        "uses": _sanitize_uses(raw.get("uses", 0)),
    }


def _normalize_library(raw: Any) -> PromptLibrary:
    normalized: PromptLibrary = {
        "schema_version": SCHEMA_VERSION,
        "entries": [],
    }

    if not isinstance(raw, dict):
        return normalized

    entries_value = raw.get("entries", [])
    if not isinstance(entries_value, list):
        return normalized

    seen_names: set[str] = set()
    for item in entries_value:
        entry = _normalize_entry(item)
        if not entry:
            continue
        name_key = entry["name"].casefold()
        if name_key in seen_names:
            continue
        seen_names.add(name_key)
        normalized["entries"].append(entry)

    return normalized


def load_prompt_library(force_reload: bool = False) -> PromptLibrary:
    global _CACHE_DATA, _CACHE_MTIME

    path = get_prompt_library_path()
    mtime = os.path.getmtime(path) if os.path.exists(path) else -1.0

    with _CACHE_LOCK:
        if not force_reload and _CACHE_DATA is not None and mtime == _CACHE_MTIME:
            return json.loads(json.dumps(_CACHE_DATA))

        if not os.path.exists(path):
            _CACHE_DATA = json.loads(json.dumps(DEFAULT_LIBRARY))
            _CACHE_MTIME = -1.0
            return json.loads(json.dumps(_CACHE_DATA))

        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            normalized = _normalize_library(payload)
            _CACHE_DATA = normalized
            _CACHE_MTIME = mtime
            return json.loads(json.dumps(normalized))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load prompt library; using empty default: %s", exc)
            _CACHE_DATA = json.loads(json.dumps(DEFAULT_LIBRARY))
            _CACHE_MTIME = mtime
            return json.loads(json.dumps(_CACHE_DATA))


def save_prompt_library(library: PromptLibrary) -> PromptLibrary:
    normalized = _normalize_library(library)
    normalized["schema_version"] = SCHEMA_VERSION

    path = get_prompt_library_path()
    temp_dir = os.path.dirname(path)
    fd, temp_path = tempfile.mkstemp(prefix="overtli_prompt_library_", suffix=".tmp", dir=temp_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(normalized, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

    return load_prompt_library(force_reload=True)


def _find_entry(entries: list[PromptEntry], name: str) -> PromptEntry | None:
    lookup = _sanitize_name(name).casefold()
    if not lookup:
        return None
    for entry in entries:
        if entry["name"].casefold() == lookup:
            return entry
    return None


def upsert_prompt_entry(
    name: str,
    prompt: str,
    category: str = "General",
    tags: Any = None,
    notes: str = "",
    allow_overwrite: bool = True,
) -> PromptEntry:
    clean_name = _sanitize_name(name)
    clean_prompt = _sanitize_text(prompt, max_length=400_000)
    if not clean_name:
        raise ValueError("Prompt name cannot be empty.")
    if not clean_prompt:
        raise ValueError("Prompt text cannot be empty.")

    library = load_prompt_library(force_reload=True)
    entries = library["entries"]
    now = _utc_now_iso()
    existing = _find_entry(entries, clean_name)

    if existing and not allow_overwrite:
        raise ValueError(f"Prompt '{clean_name}' already exists.")

    if existing:
        existing["prompt"] = clean_prompt
        existing["category"] = _sanitize_category(category)
        existing["tags"] = _sanitize_tags(tags)
        existing["notes"] = _sanitize_text(notes, max_length=2000)
        existing["updated_at"] = now
        saved = save_prompt_library(library)
        refreshed = _find_entry(saved["entries"], clean_name)
        if not refreshed:
            raise ValueError(f"Failed to update prompt '{clean_name}'.")
        return refreshed

    entry: PromptEntry = {
        "name": clean_name,
        "category": _sanitize_category(category),
        "prompt": clean_prompt,
        "tags": _sanitize_tags(tags),
        "notes": _sanitize_text(notes, max_length=2000),
        "created_at": now,
        "updated_at": now,
        "uses": 0,
    }
    entries.append(entry)
    save_prompt_library(library)
    return entry


def delete_prompt_entry(name: str) -> bool:
    clean_name = _sanitize_name(name)
    if not clean_name:
        return False

    library = load_prompt_library(force_reload=True)
    original_count = len(library["entries"])
    library["entries"] = [entry for entry in library["entries"] if entry["name"].casefold() != clean_name.casefold()]
    if len(library["entries"]) == original_count:
        return False

    save_prompt_library(library)
    return True


def rename_prompt_entry(current_name: str, new_name: str, overwrite_existing: bool = False) -> PromptEntry:
    source_name = _sanitize_name(current_name)
    target_name = _sanitize_name(new_name)

    if not source_name:
        raise ValueError("Current prompt name cannot be empty.")
    if not target_name:
        raise ValueError("New prompt name cannot be empty.")

    library = load_prompt_library(force_reload=True)
    source_entry = _find_entry(library["entries"], source_name)
    if not source_entry:
        raise ValueError(f"Prompt '{source_name}' was not found.")

    existing_target = _find_entry(library["entries"], target_name)
    if existing_target and existing_target is not source_entry and not overwrite_existing:
        raise ValueError(f"Prompt '{target_name}' already exists.")

    if existing_target and existing_target is not source_entry:
        library["entries"] = [
            entry
            for entry in library["entries"]
            if entry is source_entry or entry["name"].casefold() != target_name.casefold()
        ]

    source_entry["name"] = target_name
    source_entry["updated_at"] = _utc_now_iso()
    saved = save_prompt_library(library)
    refreshed = _find_entry(saved["entries"], target_name)
    if not refreshed:
        raise ValueError(f"Failed to rename prompt '{source_name}' to '{target_name}'.")
    return refreshed


def get_prompt_entry(name: str, increment_use_count: bool = False) -> PromptEntry | None:
    clean_name = _sanitize_name(name)
    if not clean_name:
        return None

    if not increment_use_count:
        library = load_prompt_library()
        entry = _find_entry(library["entries"], clean_name)
        return entry.copy() if entry else None

    library = load_prompt_library(force_reload=True)
    entry = _find_entry(library["entries"], clean_name)
    if not entry:
        return None

    entry["uses"] = _sanitize_uses(entry.get("uses", 0)) + 1
    entry["updated_at"] = _utc_now_iso()
    saved = save_prompt_library(library)
    refreshed = _find_entry(saved["entries"], clean_name)
    return refreshed.copy() if refreshed else None


def get_prompt_categories() -> list[str]:
    library = load_prompt_library()
    categories = {"General"}
    for entry in library["entries"]:
        categories.add(_sanitize_category(entry.get("category", "General")))
    return sorted(categories)


def list_prompt_entries(
    sort_mode: str = "most_recent",
    category_filter: str = "All",
    search_query: str = "",
    limit: int = 200,
) -> list[PromptEntry]:
    library = load_prompt_library()
    entries = list(library["entries"])

    normalized_category = _sanitize_text(category_filter, max_length=120)
    if normalized_category and normalized_category.lower() not in {"all", "*"}:
        entries = [
            entry
            for entry in entries
            if _sanitize_category(entry.get("category", "General")).casefold() == normalized_category.casefold()
        ]

    query = _sanitize_text(search_query, max_length=200).casefold()
    if query:
        entries = [
            entry
            for entry in entries
            if query in entry["name"].casefold()
            or query in entry["prompt"].casefold()
            or query in entry.get("category", "").casefold()
            or any(query in tag.casefold() for tag in entry.get("tags", []))
        ]

    mode = (sort_mode or "most_recent").strip().lower()
    if mode == "name_az":
        entries.sort(key=lambda item: item["name"].casefold())
    elif mode == "name_za":
        entries.sort(key=lambda item: item["name"].casefold(), reverse=True)
    elif mode == "category_az":
        entries.sort(key=lambda item: (_sanitize_category(item.get("category", "General")).casefold(), item["name"].casefold()))
    elif mode == "oldest_first":
        entries.sort(key=lambda item: item.get("updated_at", ""))
    elif mode == "most_used":
        entries.sort(key=lambda item: (item.get("uses", 0), item.get("updated_at", "")), reverse=True)
    else:
        entries.sort(key=lambda item: item.get("updated_at", ""), reverse=True)

    if limit > 0:
        entries = entries[:limit]

    return [entry.copy() for entry in entries]


def get_prompt_names(
    sort_mode: str = "most_recent",
    category_filter: str = "All",
    search_query: str = "",
    limit: int = 500,
) -> list[str]:
    return [entry["name"] for entry in list_prompt_entries(sort_mode, category_filter, search_query, limit)]


def export_prompt_library_json(pretty: bool = True) -> str:
    library = load_prompt_library()
    if pretty:
        return json.dumps(library, indent=2, ensure_ascii=False)
    return json.dumps(library, ensure_ascii=False)


def import_prompt_library_json(
    payload: str,
    merge: bool = True,
    overwrite_existing: bool = True,
) -> dict[str, int]:
    text = _sanitize_text(payload, max_length=2_000_000)
    if not text:
        raise ValueError("Import payload cannot be empty.")

    try:
        raw = json.loads(text)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Invalid JSON payload: {exc}") from exc

    incoming = _normalize_library(raw)

    if not merge:
        save_prompt_library(incoming)
        return {
            "imported": len(incoming["entries"]),
            "updated": 0,
            "skipped": 0,
        }

    base = load_prompt_library(force_reload=True)
    imported = 0
    updated = 0
    skipped = 0

    for candidate in incoming["entries"]:
        existing = _find_entry(base["entries"], candidate["name"])
        if existing is None:
            base["entries"].append(candidate)
            imported += 1
            continue

        if not overwrite_existing:
            skipped += 1
            continue

        existing.update(candidate)
        existing["updated_at"] = _utc_now_iso()
        updated += 1

    save_prompt_library(base)
    return {
        "imported": imported,
        "updated": updated,
        "skipped": skipped,
    }


__all__ = [
    "PromptEntry",
    "PromptLibrary",
    "get_prompt_library_path",
    "load_prompt_library",
    "save_prompt_library",
    "upsert_prompt_entry",
    "delete_prompt_entry",
    "rename_prompt_entry",
    "get_prompt_entry",
    "get_prompt_categories",
    "list_prompt_entries",
    "get_prompt_names",
    "export_prompt_library_json",
    "import_prompt_library_json",
]
