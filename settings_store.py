"""
OVERTLI STUDIO - Persistent Settings Store

Centralized persistence for optional provider defaults. The live settings file is
always stored in the ComfyUI user directory so repository checkouts do not carry
machine-local secrets or runtime overrides.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 2
_SETTINGS_FILENAME = "overtli_studio_settings.json"
_SAMPLE_SETTINGS_FILENAME = "overtli_studio_settings.sample.json"


@dataclass(frozen=True)
class SettingSpec:
    """Metadata for a persisted local setting."""

    key: str
    default: str = ""
    secret: bool = False
    env_vars: tuple[str, ...] = ()
    description: str = ""


SETTING_SPECS: Dict[str, SettingSpec] = {
    "pollinations_api_key": SettingSpec(
        key="pollinations_api_key",
        secret=True,
        env_vars=("GZ_POLLINATIONS_API_KEY", "POLLINATIONS_API_KEY"),
        description="Optional Pollinations paid-tier API key.",
    ),
    "lmstudio_base_url": SettingSpec(
        key="lmstudio_base_url",
        env_vars=("GZ_LMSTUDIO_BASE_URL", "GZ_LMSTUDIO_URL", "LMSTUDIO_BASE_URL", "LMSTUDIO_URL"),
        description="LM Studio local server base URL override.",
    ),
    "lmstudio_api_key": SettingSpec(
        key="lmstudio_api_key",
        secret=True,
        env_vars=("GZ_LMSTUDIO_API_KEY", "LMSTUDIO_API_KEY"),
        description="Optional LM Studio API key.",
    ),
    "openai_compatible_api_key": SettingSpec(
        key="openai_compatible_api_key",
        secret=True,
        env_vars=(
            "GZ_OPENAI_COMPAT_API_KEY",
            "GZ_OPENAI_API_KEY",
            "OPENAI_COMPAT_API_KEY",
            "OPENAI_API_KEY",
        ),
        description="API key for OpenAI-compatible providers.",
    ),
    "openai_compatible_base_url": SettingSpec(
        key="openai_compatible_base_url",
        env_vars=(
            "GZ_OPENAI_COMPAT_BASE_URL",
            "GZ_OPENAI_BASE_URL",
            "OPENAI_COMPAT_BASE_URL",
            "OPENAI_BASE_URL",
        ),
        description="Base URL for OpenAI-compatible providers.",
    ),
    "openai_compatible_model": SettingSpec(
        key="openai_compatible_model",
        default="gpt-4.1-mini",
        env_vars=("GZ_OPENAI_COMPAT_MODEL", "OPENAI_COMPAT_MODEL"),
        description="Default model slug for OpenAI-compatible providers.",
    ),
    "copilot_executable": SettingSpec(
        key="copilot_executable",
        env_vars=("GZ_COPILOT_EXECUTABLE", "COPILOT_EXECUTABLE"),
        description="GitHub Copilot CLI executable or absolute path.",
    ),
    "copilot_model": SettingSpec(
        key="copilot_model",
        env_vars=("GZ_COPILOT_MODEL", "COPILOT_MODEL"),
        description="Default GitHub Copilot model slug.",
    ),
}

DEFAULT_SETTINGS: Dict[str, Any] = {"schema_version": SCHEMA_VERSION}
DEFAULT_SETTINGS.update({key: spec.default for key, spec in SETTING_SPECS.items()})

_CACHE_LOCK = threading.Lock()
_CACHE_MTIME: float = -1.0
_CACHE_DATA: Dict[str, Any] | None = None


def _sanitize_string(value: Any, max_length: int = 4096) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if len(text) > max_length:
        return text[:max_length]
    return text


def _derived_comfyui_user_dir() -> Path:
    """Fallback user directory when ComfyUI path helpers are unavailable."""
    return Path(__file__).resolve().parents[2] / "user"


def get_settings_dir() -> str:
    """
    Return the ComfyUI user directory used for local OVERTLI settings.

    This never falls back to the home directory. If the ComfyUI helper module is
    unavailable, the path is derived from the checked-out plugin location.
    """
    base_path: Path
    try:
        import folder_paths  # type: ignore

        if hasattr(folder_paths, "get_user_directory"):
            base_path = Path(folder_paths.get_user_directory())
        elif hasattr(folder_paths, "base_path"):
            base_path = Path(folder_paths.base_path) / "user"
        else:
            base_path = _derived_comfyui_user_dir()
    except Exception:
        base_path = _derived_comfyui_user_dir()

    base_path.mkdir(parents=True, exist_ok=True)
    return str(base_path)


def get_settings_path() -> str:
    return str(Path(get_settings_dir()) / _SETTINGS_FILENAME)


def get_sample_settings_path() -> str:
    return str(Path(__file__).resolve().parent / _SAMPLE_SETTINGS_FILENAME)


def _normalize_settings(raw: Any) -> Dict[str, Any]:
    normalized = DEFAULT_SETTINGS.copy()

    if not isinstance(raw, dict):
        return normalized

    schema_value = raw.get("schema_version", SCHEMA_VERSION)
    try:
        normalized["schema_version"] = int(schema_value)
    except (TypeError, ValueError):
        normalized["schema_version"] = SCHEMA_VERSION

    for key in SETTING_SPECS:
        if key in raw:
            normalized[key] = _sanitize_string(raw.get(key))

    return normalized


def _write_settings_file(payload: Mapping[str, Any], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(
        prefix="overtli_settings_",
        suffix=".tmp",
        dir=str(destination.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(dict(payload), handle, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, destination)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


def ensure_settings_file() -> str:
    """Create the local settings file with defaults when it does not yet exist."""
    path = Path(get_settings_path())
    if not path.exists():
        _write_settings_file(DEFAULT_SETTINGS, path)
    return str(path)


def load_persistent_settings(force_reload: bool = False) -> Dict[str, Any]:
    global _CACHE_DATA, _CACHE_MTIME

    path = Path(get_settings_path())
    if not path.exists():
        try:
            ensure_settings_file()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to initialize local settings file at %s: %s", path, exc)

    mtime = path.stat().st_mtime if path.exists() else -1.0

    with _CACHE_LOCK:
        if not force_reload and _CACHE_DATA is not None and mtime == _CACHE_MTIME:
            return _CACHE_DATA.copy()

        if not path.exists():
            _CACHE_DATA = DEFAULT_SETTINGS.copy()
            _CACHE_MTIME = -1.0
            return _CACHE_DATA.copy()

        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            normalized = _normalize_settings(payload)
            _CACHE_DATA = normalized
            _CACHE_MTIME = mtime
            return normalized.copy()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load persistent settings from %s; using defaults: %s", path, exc)
            _CACHE_DATA = DEFAULT_SETTINGS.copy()
            _CACHE_MTIME = mtime
            return _CACHE_DATA.copy()


def get_persistent_setting(key: str, default: str = "") -> str:
    settings = load_persistent_settings()
    value = settings.get(key, default)
    return _sanitize_string(value) if value is not None else default


def resolve_setting(
    runtime_value: str,
    env_value: str,
    persisted_value: str,
    default: str = "",
) -> str:
    runtime_text = _sanitize_string(runtime_value)
    if runtime_text:
        return runtime_text

    env_text = _sanitize_string(env_value)
    if env_text:
        return env_text

    persisted_text = _sanitize_string(persisted_value)
    if persisted_text:
        return persisted_text

    return default


def get_setting_env_value(key: str) -> str:
    spec = SETTING_SPECS.get(key)
    if spec is None:
        return ""
    for env_name in spec.env_vars:
        value = _sanitize_string(os.environ.get(env_name, ""))
        if value:
            return value
    return ""


def resolve_config_value(key: str, runtime_value: str = "", default: str = "") -> str:
    """
    Resolve a configurable string with unified precedence.

    Precedence:
    1. Runtime input
    2. Environment variable(s) declared for the setting
    3. Local ComfyUI user settings file
    4. Explicit default passed by the caller
    5. Registry default
    """
    spec = SETTING_SPECS.get(key)
    resolved_default = default if default != "" else (spec.default if spec else "")
    return resolve_setting(
        runtime_value=runtime_value,
        env_value=get_setting_env_value(key),
        persisted_value=get_persistent_setting(key, ""),
        default=resolved_default,
    )


def redact_secret(value: str) -> str:
    text = _sanitize_string(value)
    if not text:
        return ""
    if len(text) <= 8:
        return "****"
    return f"{text[:4]}...{text[-4:]}"


def format_setting_updates(updates: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for key, value in updates.items():
        spec = SETTING_SPECS.get(key)
        normalized = _sanitize_string(value)
        if not normalized:
            continue
        display_value = redact_secret(normalized) if spec and spec.secret else normalized
        parts.append(f"{key}={display_value}")
    return ", ".join(parts)


def save_persistent_settings(
    updates: Mapping[str, Any],
    skip_empty: bool = True,
    source: str = "OVERTLI runtime",
) -> Dict[str, Any]:
    if not isinstance(updates, Mapping):
        return load_persistent_settings()

    current = load_persistent_settings(force_reload=True)
    applied: Dict[str, str] = {}

    for key, value in updates.items():
        if key not in SETTING_SPECS:
            continue
        normalized = _sanitize_string(value)
        if skip_empty and not normalized:
            continue
        current[key] = normalized
        applied[key] = normalized

    current["schema_version"] = SCHEMA_VERSION

    destination = Path(get_settings_path())
    _write_settings_file(current, destination)
    saved = load_persistent_settings(force_reload=True)

    if applied:
        logger.info("%s saved local settings to %s: %s", source, destination, format_setting_updates(applied))

    return saved


__all__ = [
    "DEFAULT_SETTINGS",
    "SCHEMA_VERSION",
    "SETTING_SPECS",
    "SettingSpec",
    "ensure_settings_file",
    "format_setting_updates",
    "get_persistent_setting",
    "get_sample_settings_path",
    "get_setting_env_value",
    "get_settings_dir",
    "get_settings_path",
    "load_persistent_settings",
    "redact_secret",
    "resolve_config_value",
    "resolve_setting",
    "save_persistent_settings",
]
