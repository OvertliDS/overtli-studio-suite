# ============================================================================
# copilot_agent.py
# GZ_CopilotAgent - GitHub Copilot CLI bridge with multimodal file context
# ============================================================================
"""
GZ_CopilotAgent: Copilot CLI Node
=================================
Bridges ComfyUI prompts to the local `copilot` CLI in non-interactive mode.

Current capabilities:
- Multimodal input support via IMAGE tensor or FILE_PATH context
- Prompt-mode non-interactive Copilot CLI execution (`--prompt`)
- Auth mode controls: Auto / Existing login / Sign in
- Reconnect trigger + status-only auth check mode
- Model vision capability cache with runtime fallback updates
- Environment token override detection and explicit error mapping
"""

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any, Optional, Tuple

from ..base_node import GZBaseNode
from ..exceptions import (
    OvertliAPIError,
    OvertliConfigError,
    OvertliInputError,
    OvertliModelError,
    OvertliSuiteError,
    OvertliTimeoutError,
)
from ..image_utils import cleanup_temp_file, comfy_image_to_tempfile
from ..instruction_modes import (
    IMAGE_MODE_NAMES,
    TEXT_MODE_NAMES,
    TTS_MODE_NAMES,
    VIDEO_MODE_NAMES,
    resolve_mode_family_preset,
)
from ..output_sanitizer import sanitize_text_output
from ..styles import STYLE_OFF_LABEL, get_style_options, infer_mode_category
from ..settings_store import get_settings_path, resolve_config_value, save_persistent_settings
from ..shared_utils import (
    build_prompt,
    build_user_facing_error,
    normalize_string_input,
    select_image_batch_indices,
    validate_single_image_source,
)
from ..suite_config import get_config

logger = logging.getLogger(__name__)

_AUTH_MODE_OPTIONS = ["Auto", "Existing login", "Sign in"]
_TOKEN_OVERRIDE_ENV_VARS = ("COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN")
_PREFS_SCHEMA_VERSION = 1
_PREFS_FILENAME = "overtli_copilot_prefs.json"
_MAX_IMAGE_FILE_MB = 20
_MAX_IMAGE_DIMENSION = 8192
_IMAGE_ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
_WINDOWS_PROMPT_ARG_SAFE_CHARS = 3500
_DEFAULT_MAX_OUTPUT_TOKENS = 1000
_COPILOT_OUTPUT_CHARS_PER_TOKEN = 4
_COPILOT_HEARTBEAT_SECONDS = 15
_COPILOT_TIMEOUT_RETRY_MIN_SECONDS = 300
_COPILOT_TIMEOUT_RETRY_MAX_SECONDS = 900
_COPILOT_MODEL_DISCOVERY_TIMEOUT_SECONDS = 5
_COPILOT_MODEL_CACHE_SECONDS = 300
_COPILOT_MODEL_LINE_PATTERN = re.compile(r'^\s*-\s+"([^"]+)"\s*$')
_COPILOT_MODEL_OPTIONS_CACHE: tuple[float, list[str]] = (0.0, [])
_SESSION_MODEL_CAPABILITIES: dict[str, dict[str, Any]] = {}
_TEXT_ONLY_IMAGE_REPLY_MARKERS = (
    "unable to directly view or analyze images",
    "unable to directly analyze images",
    "can't directly view images",
    "cannot directly view images",
    "can't view images",
    "cannot view images",
    "i don't have the ability to view images",
    "i see you've referenced an image at",
    "please provide a description of the image",
    "no action taken—there was no user request",
    "no action taken-there was no user request",
)


def _get_prefs_path() -> str:
    settings_path = get_settings_path()
    settings_dir = os.path.dirname(settings_path) if settings_path else ""
    if not settings_dir:
        settings_dir = os.path.join(os.path.expanduser("~"), ".overtli_studio")
    os.makedirs(settings_dir, exist_ok=True)
    return os.path.join(settings_dir, _PREFS_FILENAME)


def _load_prefs() -> dict[str, Any]:
    path = _get_prefs_path()
    default_payload: dict[str, Any] = {
        "schema_version": _PREFS_SCHEMA_VERSION,
        "last_auth_status": "unknown",
        "last_auth_check_epoch": 0,
    }

    if not os.path.exists(path):
        return default_payload

    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            return default_payload

        merged = default_payload.copy()
        merged.update(payload)
        return merged
    except Exception:  # noqa: BLE001
        return default_payload


def _save_prefs(prefs: dict[str, Any]) -> None:
    if not isinstance(prefs, dict):
        return

    path = _get_prefs_path()
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(prefix="overtli_copilot_prefs_", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(prefs, handle, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            cleanup_temp_file(temp_path)


def _model_cache_key(model_name: str) -> str:
    return normalize_string_input(model_name).lower()


def _infer_vision_support(model_name: str) -> bool:
    normalized = normalize_string_input(model_name).lower()
    if not normalized:
        return True

    # Copilot CLI commonly treats gpt-4.1 as text-only for @file image references.
    if "gpt-4.1" in normalized and "vision" not in normalized and "gpt-4o" not in normalized:
        return False

    positive_markers = (
        "vision",
        "gpt-4o",
        "gpt-5",
        "o3",
        "o4",
        "claude",
        "gemini",
    )
    if any(marker in normalized for marker in positive_markers):
        return True

    return False


def _looks_like_text_only_image_response(response_text: str) -> bool:
    normalized = normalize_string_input(response_text).lower()
    if not normalized:
        return False
    return any(marker in normalized for marker in _TEXT_ONLY_IMAGE_REPLY_MARKERS)


def _vision_model_preference_score(model_name: str) -> int:
    normalized = normalize_string_input(model_name).lower()
    if not normalized:
        return 999
    if "gpt-4o" in normalized:
        return 0
    if "vision" in normalized:
        return 1
    if "gpt-5" in normalized:
        return 2
    if "claude-opus" in normalized:
        return 3
    if "claude-sonnet" in normalized:
        return 4
    if "claude" in normalized:
        return 5
    if "gemini" in normalized:
        return 6
    if "o3" in normalized or "o4" in normalized:
        return 7
    # Avoid retrying to known text-only selections when we can choose better.
    if "gpt-4.1" in normalized:
        return 95
    return 50


def _select_vision_retry_model(current_model: str, excluded_models: set[str] | None = None) -> str:
    excluded = excluded_models or set()
    current_key = _model_cache_key(current_model)
    candidates: list[tuple[int, str]] = []

    discovered_models = _discover_copilot_cli_models()
    model_pool = discovered_models if discovered_models else _build_model_options()

    for candidate in model_pool:
        model_name = normalize_string_input(candidate)
        if not model_name:
            continue

        model_key = _model_cache_key(model_name)
        if model_key == current_key or model_key in excluded:
            continue

        supports_vision, source = _get_model_capability(model_name)
        if not supports_vision and source == "runtime":
            continue

        if not supports_vision and source != "runtime":
            continue

        score = _vision_model_preference_score(model_name)
        candidates.append((score, model_name))

    if not candidates:
        return ""

    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][1]


def _is_model_listed(model_name: str, model_list: list[str]) -> bool:
    wanted = _model_cache_key(model_name)
    if not wanted:
        return False
    return any(_model_cache_key(candidate) == wanted for candidate in model_list)


def _select_retry_model_from_discovered(
    current_model: str,
    discovered_models: list[str],
    *,
    excluded_models: set[str] | None = None,
    require_vision: bool = False,
) -> str:
    excluded = excluded_models or set()
    current_key = _model_cache_key(current_model)

    if require_vision:
        candidates: list[tuple[int, str]] = []
        for candidate in discovered_models:
            model_name = normalize_string_input(candidate)
            if not model_name:
                continue

            model_key = _model_cache_key(model_name)
            if model_key == current_key or model_key in excluded:
                continue

            supports_vision, _source = _get_model_capability(model_name)
            if not supports_vision:
                continue

            candidates.append((_vision_model_preference_score(model_name), model_name))

        if not candidates:
            return ""

        candidates.sort(key=lambda item: (item[0], item[1]))
        return candidates[0][1]

    for candidate in discovered_models:
        model_name = normalize_string_input(candidate)
        if not model_name:
            continue
        model_key = _model_cache_key(model_name)
        if model_key == current_key or model_key in excluded:
            continue
        return model_name

    return ""


def _get_model_capability(model_name: str) -> tuple[bool, str]:
    key = _model_cache_key(model_name)
    if not key:
        return True, "default"

    entry = _SESSION_MODEL_CAPABILITIES.get(key)
    if isinstance(entry, dict):
        supports_vision = bool(entry.get("supports_vision", True))
        source = normalize_string_input(entry.get("source", "session"), default="session")
        return supports_vision, source

    inferred = _infer_vision_support(model_name)
    _SESSION_MODEL_CAPABILITIES[key] = {
        "supports_vision": inferred,
        "source": "heuristic",
    }
    return inferred, "heuristic"


def _set_model_capability(model_name: str, supports_vision: bool, source: str) -> None:
    key = _model_cache_key(model_name)
    if not key:
        return

    _SESSION_MODEL_CAPABILITIES[key] = {
        "supports_vision": bool(supports_vision),
        "source": normalize_string_input(source, default="runtime"),
    }


def _set_last_auth_status(status: str) -> None:
    prefs = _load_prefs()
    prefs["last_auth_status"] = normalize_string_input(status, default="unknown")
    prefs["last_auth_check_epoch"] = int(time.time())
    _save_prefs(prefs)


def _detect_token_override() -> tuple[str, str]:
    for env_name in _TOKEN_OVERRIDE_ENV_VARS:
        value = normalize_string_input(os.environ.get(env_name))
        if value:
            return env_name, value
    return "", ""


def _classify_cli_error(stderr_text: str, stdout_text: str, env_override_var: str = "") -> str:
    combined = f"{stderr_text}\n{stdout_text}".lower()

    if any(term in combined for term in ("command line is too long", "filename or extension is too long", "argument list too long")):
        return "command_too_long"

    if env_override_var and any(term in combined for term in ("token", "auth", "unauthorized", "401", "403")):
        return "env_token_override"

    if any(term in combined for term in ("not signed", "login", "authenticate", "unauthorized", "401", "invalid token")):
        return "not_signed_in"

    if any(term in combined for term in ("subscription", "plan", "upgrade", "entitled", "not available for your account")):
        return "subscription_issue"

    if any(
        term in combined
        for term in (
            "rate limit",
            "too many requests",
            "429",
            "quota",
            "out of requests",
            "usage limit",
            "request limit",
            "resource exhausted",
            "limit exceeded",
        )
    ):
        return "rate_limited"

    if any(
        term in combined
        for term in (
            "gateway timeout",
            "504",
            "deadline exceeded",
            "upstream request timeout",
            "timed out waiting",
            "request timed out",
        )
    ):
        return "upstream_timeout"

    if any(
        term in combined
        for term in (
            "temporarily unavailable",
            "service unavailable",
            "server overloaded",
            "overloaded",
            "heavy usage",
            "high demand",
            "temporarily at capacity",
            "try again later",
            "503",
        )
    ):
        return "service_busy"

    if any(
        term in combined
        for term in (
            "unknown model",
            "invalid model",
            "unsupported model",
            "model not found",
            "does not have access to model",
            "model is not available",
            "from --model flag is not available",
            "unrecognized model",
        )
    ):
        return "model_unavailable"

    if any(term in combined for term in ("vision", "image input", "does not support images", "unsupported image")):
        return "vision_unsupported"

    return "unknown"


def _cli_excerpt(stderr_text: str, stdout_text: str, limit: int = 500) -> str:
    """Return a compact CLI excerpt for logs and user-facing diagnostics."""
    return (stderr_text or stdout_text or "No output")[:limit]


def _build_copilot_cli_failure(
    classification: str,
    *,
    selected_model: str,
    stderr_text: str,
    stdout_text: str,
    env_override_var: str = "",
) -> tuple[str, type[OvertliSuiteError]]:
    """Map Copilot CLI failures to structured, actionable diagnostics."""
    excerpt = _cli_excerpt(stderr_text, stdout_text)

    if classification == "subscription_issue":
        return (
            build_user_facing_error(
                "Copilot subscription or entitlement issue.",
                what_happened=(
                    f"The selected Copilot model '{selected_model}' appears unavailable for this account plan or entitlement."
                ),
                what_we_tried="Ran the local Copilot CLI and captured the provider error output.",
                next_steps=(
                    "Try a different model from the dropdown, verify your Copilot subscription/plan, "
                    "or test the same model manually with `copilot --model <name>`."
                ),
                details=f"CLI excerpt: {excerpt}",
            ),
            OvertliAPIError,
        )

    if classification == "rate_limited":
        return (
            build_user_facing_error(
                "Copilot request was rate-limited.",
                what_happened=(
                    f"The Copilot CLI reported a usage cap, quota limit, or too-many-requests condition for model '{selected_model}'."
                ),
                what_we_tried="Captured the CLI response and preserved the partial diagnostic text.",
                next_steps=(
                    "Wait and retry, lower request frequency, switch to another model, or check whether your Copilot quota/usage bucket is exhausted."
                ),
                details=f"CLI excerpt: {excerpt}",
            ),
            OvertliAPIError,
        )

    if classification == "upstream_timeout":
        return (
            build_user_facing_error(
                "Copilot upstream service timed out.",
                what_happened=(
                    f"The request reached Copilot, but the upstream service timed out before model '{selected_model}' returned a result."
                ),
                what_we_tried="Captured the CLI output and kept the local timeout/retry diagnostics separate from upstream timeouts.",
                next_steps=(
                    "Retry after a short wait, reduce prompt/context size, or switch to a faster/lighter model."
                ),
                details=f"CLI excerpt: {excerpt}",
            ),
            OvertliTimeoutError,
        )

    if classification == "service_busy":
        return (
            build_user_facing_error(
                "Copilot service is temporarily busy.",
                what_happened=(
                    f"The Copilot CLI reported temporary capacity or heavy-usage issues while running model '{selected_model}'."
                ),
                what_we_tried="Captured the CLI response and categorized the provider-side availability problem.",
                next_steps=(
                    "Retry after a short wait, try again during lower traffic, or switch to a different model."
                ),
                details=f"CLI excerpt: {excerpt}",
            ),
            OvertliAPIError,
        )

    if classification == "model_unavailable":
        return (
            build_user_facing_error(
                "Selected Copilot model is unavailable.",
                what_happened=(
                    f"The installed Copilot CLI rejected model '{selected_model}' as unavailable, unsupported, or inaccessible for this account."
                ),
                what_we_tried="Used the local CLI model name exactly as configured and captured the returned error text.",
                next_steps=(
                    "Pick another model from the dropdown, restart ComfyUI so the latest CLI model list is reloaded, or test the model manually in a terminal."
                ),
                details=f"CLI excerpt: {excerpt}",
            ),
            OvertliModelError,
        )

    if classification == "env_token_override":
        return (
            build_user_facing_error(
                "Copilot authentication is being overridden by an environment token.",
                what_happened=(
                    f"Environment variable '{env_override_var}' is overriding the stored Copilot OAuth session, and the override token appears invalid or unauthorized."
                ),
                what_we_tried="Detected token override precedence and inspected the CLI auth error response.",
                next_steps=(
                    f"Unset or fix '{env_override_var}' if you want to use the existing Copilot login stored by the CLI."
                ),
                details=f"CLI excerpt: {excerpt}",
            ),
            OvertliAPIError,
        )

    if classification == "not_signed_in":
        return (
            build_user_facing_error(
                "Copilot is not signed in.",
                what_happened="The local Copilot CLI reported that no valid authenticated session is available.",
                what_we_tried="Ran the configured Copilot executable and inspected the returned auth error.",
                next_steps="Use auth_mode='Sign in', enable reconnect, or run `copilot login` manually in a terminal.",
                details=f"CLI excerpt: {excerpt}",
            ),
            OvertliAPIError,
        )

    return (
        build_user_facing_error(
            "Copilot CLI request failed.",
            what_happened=(
                f"The Copilot CLI returned a non-zero exit while running model '{selected_model}', but the error did not match a known category."
            ),
            what_we_tried="Captured stdout/stderr from the local CLI process for diagnosis.",
            next_steps="Check the CLI excerpt below, retry manually in a terminal, or switch models to isolate whether this is model-specific.",
            details=f"CLI excerpt: {excerpt}",
        ),
        OvertliAPIError,
    )


def _validate_image_file_context(file_path: str) -> tuple[bool, str]:
    extension = os.path.splitext(file_path)[1].lower()
    if extension and extension not in _IMAGE_ALLOWED_EXTENSIONS:
        return False, f"unsupported file extension '{extension}'"

    try:
        file_size = os.path.getsize(file_path)
    except OSError as exc:
        return False, f"failed to read file size ({exc})"

    max_size_bytes = _MAX_IMAGE_FILE_MB * 1024 * 1024
    if file_size > max_size_bytes:
        return False, f"file exceeds {_MAX_IMAGE_FILE_MB}MB"

    return True, ""


def _resolve_output_char_limit(max_output_tokens: int, max_output_chars: int) -> int:
    if int(max_output_chars or 0) > 0:
        return max(1024, min(int(max_output_chars), 2_000_000))

    safe_tokens = max(64, min(int(max_output_tokens or _DEFAULT_MAX_OUTPUT_TOKENS), 32768))
    return max(1024, min(safe_tokens * _COPILOT_OUTPUT_CHARS_PER_TOKEN, 2_000_000))


def _coerce_timeout_stream(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    return normalize_string_input(value)


def _run_copilot_command(
    executable_path: str,
    temp_dir: str,
    args: list[str],
    timeout_seconds: int,
    max_output_chars: int,
    stdin_text: str = "",
) -> tuple[int, str, str]:
    stdout_path: Optional[str] = None
    stderr_path: Optional[str] = None
    wrapper_path: Optional[str] = None
    os.makedirs(temp_dir, exist_ok=True)

    try:
        command_prefix, wrapper_path = _prepare_copilot_command(executable_path, temp_dir)
        command = [*command_prefix, *args]

        stdout_fd, stdout_path = tempfile.mkstemp(
            prefix="overtli_copilot_stdout_",
            suffix=".log",
            dir=temp_dir,
        )
        stderr_fd, stderr_path = tempfile.mkstemp(
            prefix="overtli_copilot_stderr_",
            suffix=".log",
            dir=temp_dir,
        )
        os.close(stdout_fd)
        os.close(stderr_fd)

        with open(stdout_path, "wb") as stdout_file, open(stderr_path, "wb") as stderr_file:
            stdin_handle = subprocess.PIPE if stdin_text else None
            process = subprocess.Popen(
                command,
                stdin=stdin_handle,
                stdout=stdout_file,
                stderr=stderr_file,
            )

            if stdin_text:
                if process.stdin is None:
                    raise OvertliAPIError(
                        "Copilot CLI stdin transport was requested, but stdin was unavailable.",
                        endpoint="copilot stdin",
                    )
                process.stdin.write(stdin_text.encode("utf-8"))
                process.stdin.close()

            start_time = time.monotonic()
            next_heartbeat = _COPILOT_HEARTBEAT_SECONDS

            while True:
                return_code = process.poll()
                elapsed = time.monotonic() - start_time

                if return_code is not None:
                    process.wait(timeout=1)
                    break

                if elapsed >= timeout_seconds:
                    process.kill()
                    try:
                        process.wait(timeout=2)
                    except Exception:  # noqa: BLE001
                        pass

                    stdout_file.flush()
                    stderr_file.flush()
                    stdout_file.close()
                    stderr_file.close()

                    partial_stdout = _read_limited_text(stdout_path, max_output_chars).strip()
                    partial_stderr = _read_limited_text(stderr_path, max_output_chars).strip()

                    logger.error(
                        "Copilot CLI timeout after %ss (partial stdout=%s chars, stderr=%s chars).",
                        timeout_seconds,
                        len(partial_stdout),
                        len(partial_stderr),
                    )

                    timeout_exc = subprocess.TimeoutExpired(command, timeout_seconds)
                    timeout_exc.output = partial_stdout.encode("utf-8", errors="ignore")
                    timeout_exc.stderr = partial_stderr.encode("utf-8", errors="ignore")
                    raise timeout_exc

                if elapsed >= next_heartbeat:
                    logger.info(
                        "Copilot CLI still running (%ss/%ss elapsed).",
                        int(elapsed),
                        timeout_seconds,
                    )
                    next_heartbeat += _COPILOT_HEARTBEAT_SECONDS

                time.sleep(0.5)

        stdout_text = _read_limited_text(stdout_path, max_output_chars).strip()
        stderr_text = _read_limited_text(stderr_path, max_output_chars).strip()
        return process.returncode, stdout_text, stderr_text
    finally:
        if wrapper_path:
            cleanup_temp_file(wrapper_path)
        if stdout_path:
            cleanup_temp_file(stdout_path)
        if stderr_path:
            cleanup_temp_file(stderr_path)


def _build_model_options() -> list[str]:
    """Return Copilot model options from the local CLI when available."""
    config = get_config()
    defaults = [
        config.copilot.default_model,
        "gpt-4o",
        "gpt-5.3-codex",
        "gpt-5.4",
        "gpt-5.4-mini",
        "gpt-5.2-codex",
        "gpt-5.2",
        "gpt-5.1",
        "gpt-5-mini",
        "gpt-4.1",
        "claude-sonnet-4.6",
        "claude-sonnet-4.5",
        "claude-haiku-4.5",
        "claude-opus-4.6",
        "claude-opus-4.6-fast",
        "claude-opus-4.5",
        "claude-sonnet-4",
        "o3",
    ]

    unique_models: list[str] = []
    for model_name in [config.copilot.default_model, *_discover_copilot_cli_models(), *defaults]:
        name = normalize_string_input(model_name)
        if name and name not in unique_models:
            unique_models.append(name)

    return unique_models


def _discover_copilot_cli_models() -> list[str]:
    """Best-effort model discovery from the installed Copilot CLI help output."""
    global _COPILOT_MODEL_OPTIONS_CACHE

    cache_epoch, cached_models = _COPILOT_MODEL_OPTIONS_CACHE
    now = time.monotonic()
    if cached_models and (now - cache_epoch) <= _COPILOT_MODEL_CACHE_SECONDS:
        return list(cached_models)

    config = get_config()
    configured_executable = normalize_string_input(config.copilot.executable)
    if not configured_executable:
        configured_executable = resolve_config_value(
            "copilot_executable",
            default="copilot",
        )

    try:
        resolved_executable = _resolve_copilot_executable(configured_executable)
    except Exception:  # noqa: BLE001
        return []

    command_temp_dir = config.temp_dir or tempfile.gettempdir()
    wrapper_path: Optional[str] = None
    try:
        command_prefix, wrapper_path = _prepare_copilot_command(resolved_executable, command_temp_dir)
        help_result = subprocess.run(
            [*command_prefix, "help", "config"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_COPILOT_MODEL_DISCOVERY_TIMEOUT_SECONDS,
            check=False,
        )
    except Exception:  # noqa: BLE001
        return []
    finally:
        if wrapper_path:
            cleanup_temp_file(wrapper_path)

    if help_result.returncode != 0:
        logger.debug(
            "Copilot model discovery skipped because `copilot help config` exited with %s.",
            help_result.returncode,
        )
        return []

    discovered_models: list[str] = []
    in_model_section = False
    for line in help_result.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("`model`"):
            in_model_section = True
            continue
        if in_model_section and stripped and not line.startswith(" "):
            break

        if not in_model_section:
            continue

        match = _COPILOT_MODEL_LINE_PATTERN.match(line)
        if not match:
            continue

        model_name = normalize_string_input(match.group(1))
        if model_name and model_name not in discovered_models:
            discovered_models.append(model_name)

    if discovered_models:
        _COPILOT_MODEL_OPTIONS_CACHE = (now, list(discovered_models))

    return discovered_models


def _resolve_copilot_executable(executable: str) -> str:
    """Resolve Copilot executable path with Windows-aware fallbacks."""
    configured = normalize_string_input(executable)
    variants: list[str] = []
    if configured:
        variants.append(configured)
        _, ext = os.path.splitext(configured)
        if not ext:
            variants.extend([f"{configured}.cmd", f"{configured}.bat", f"{configured}.exe"])

    canonical = configured.lower()
    if not configured or canonical in {"copilot", "copilot.exe", "copilot.cmd", "copilot.bat"}:
        variants.extend(["copilot", "copilot.cmd", "copilot.bat", "copilot.exe"])
        variants.extend(["Copilot-Bridge.bat", "Copilot.bat", "copilot-bridge.bat"])

    deduped_variants: list[str] = []
    seen_variants: set[str] = set()
    for candidate in variants:
        normalized = normalize_string_input(candidate)
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen_variants:
            continue
        seen_variants.add(key)
        deduped_variants.append(normalized)
    variants = deduped_variants

    for candidate in variants:
        if os.path.isabs(candidate) and os.path.exists(candidate):
            return candidate
        found = shutil.which(candidate)
        if found:
            return found

    addon_candidates: list[str] = []
    try:
        this_dir = os.path.dirname(os.path.abspath(__file__))
        comfyui_dir = os.path.abspath(os.path.join(this_dir, "..", ".."))
        easy_install_dir = os.path.abspath(os.path.join(comfyui_dir, ".."))
        addon_candidates.extend(
            [
                os.path.join(easy_install_dir, "Add-Ons"),
                os.path.join(easy_install_dir, "Add-Ons", "Tools"),
                os.path.join(easy_install_dir, "python_embeded", "Scripts"),
                os.path.join(comfyui_dir, "python_embeded", "Scripts"),
            ]
        )
    except Exception:  # noqa: BLE001
        pass

    for base_dir in addon_candidates:
        if not os.path.isdir(base_dir):
            continue
        for variant in variants:
            candidate_path = os.path.join(base_dir, variant)
            if os.path.exists(candidate_path):
                return candidate_path

    requested = configured or "copilot"
    raise OvertliConfigError(
        f"Copilot executable not found: {requested}",
        config_key="COPILOT_EXECUTABLE",
    )


def _create_windows_copilot_wrapper(executable_path: str, temp_dir: str) -> str | None:
    """Create a temporary .bat wrapper for script-based Copilot launch targets on Windows."""
    _, ext = os.path.splitext((executable_path or "").strip())
    normalized_ext = ext.lower()
    if normalized_ext not in {".ps1", ".js", ".cjs", ".mjs"}:
        return None

    if normalized_ext == ".ps1":
        runner = 'powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File'
    else:
        node_path = shutil.which("node")
        if not node_path:
            raise OvertliConfigError(
                (
                    f"Copilot script target '{executable_path}' requires Node.js, but 'node' was not found in PATH.\n"
                    "What happened: the configured Copilot executable resolves to a JavaScript launcher.\n"
                    "What we tried: we attempted to build a temporary Windows batch wrapper around that script.\n"
                    "What to do next: install Node.js or point copilot_executable to a .cmd/.bat/.exe launcher."
                ),
                config_key="COPILOT_EXECUTABLE",
            )
        runner = f'"{node_path}"'

    os.makedirs(temp_dir, exist_ok=True)
    fd, wrapper_path = tempfile.mkstemp(prefix="overtli_copilot_wrapper_", suffix=".bat", dir=temp_dir)
    os.close(fd)
    wrapper_text = (
        "@echo off\r\n"
        "setlocal\r\n"
        f"{runner} \"{executable_path}\" %*\r\n"
        "exit /b %ERRORLEVEL%\r\n"
    )
    with open(wrapper_path, "w", encoding="utf-8", newline="") as handle:
        handle.write(wrapper_text)
    return wrapper_path


def _prepare_copilot_command(executable_path: str, temp_dir: str) -> tuple[list[str], str | None]:
    """Return a Windows-safe launch command and optional temporary wrapper path."""
    wrapper_path = _create_windows_copilot_wrapper(executable_path, temp_dir)
    launch_target = wrapper_path or executable_path

    if launch_target.lower().endswith((".bat", ".cmd")):
        return (["cmd", "/c", launch_target], wrapper_path)
    if launch_target.lower().endswith(".ps1"):
        return (
            ["powershell", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", launch_target],
            wrapper_path,
        )

    return ([launch_target], wrapper_path)


def _extract_text_from_payload(payload: Any) -> str:
    """Best-effort extraction of text from JSON payloads."""
    if isinstance(payload, str):
        return payload

    if isinstance(payload, list):
        parts = [_extract_text_from_payload(item) for item in payload]
        return "\n".join(part for part in parts if part)

    if not isinstance(payload, dict):
        return ""

    for key in ("content", "text", "response", "output"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    for key in ("message", "delta", "choices"):
        nested_text = _extract_text_from_payload(payload.get(key))
        if nested_text:
            return nested_text

    return ""


def _extract_text_from_jsonl(raw_output: str) -> str:
    """Parse JSONL output from Copilot CLI into readable text."""
    extracted_parts: list[str] = []

    for line in raw_output.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue

        try:
            payload = json.loads(cleaned)
            text = _extract_text_from_payload(payload)
            if text:
                extracted_parts.append(text)
        except json.JSONDecodeError:
            extracted_parts.append(cleaned)

    return "\n".join(part for part in extracted_parts if part).strip()


def _read_limited_text(file_path: str, max_chars: int) -> str:
    """Read output file with a defensive character cap."""
    if not os.path.exists(file_path):
        return ""

    max_chars = max(1024, min(max_chars, 2_000_000))

    with open(file_path, "rb") as handle:
        data = handle.read(max_chars + 1)

    text = data.decode("utf-8", errors="replace")
    if len(text) > max_chars:
        return text[:max_chars] + "\n...[output truncated]"
    return text


class GZ_CopilotAgent(GZBaseNode):
    """GitHub Copilot CLI bridge node with optional multimodal file context."""

    CATEGORY = "OVERTLI STUDIO/LLM"
    FUNCTION = "execute"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("copilot_response",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        model_options = _build_model_options()

        return {
            "required": {
                "prompt": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "placeholder": "Ask Copilot to analyze, write, or explain...",
                    },
                ),
                "text_mode_enabled": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "Text Mode ON",
                        "label_off": "Text Mode OFF",
                    },
                ),
                "text_mode": (TEXT_MODE_NAMES, {"default": "Off"}),
                "image_mode_enabled": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "Image Mode ON",
                        "label_off": "Image Mode OFF",
                    },
                ),
                "image_mode": (IMAGE_MODE_NAMES, {"default": "Off"}),
                "video_mode_enabled": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "Video Mode ON",
                        "label_off": "Video Mode OFF",
                    },
                ),
                "video_mode": (VIDEO_MODE_NAMES, {"default": "Off"}),
                "tts_mode_enabled": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "TTS Mode ON",
                        "label_off": "TTS Mode OFF",
                    },
                ),
                "tts_mode": (TTS_MODE_NAMES, {"default": "Off"}),
                "model": (
                    model_options,
                    {
                        "default": model_options[0],
                    },
                ),
            },
            "optional": {
                "image": ("IMAGE",),
                "file_path": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "placeholder": "Optional local file path for context...",
                    },
                ),
                "copilot_executable": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "placeholder": "Optional executable override (copilot, copilot.cmd, C:/.../copilot.bat)",
                    },
                ),
                "custom_instructions": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "forceInput": True,
                        "placeholder": "Custom instructions (overrides mode preset)...",
                    },
                ),
                "style_preset_1": (
                    get_style_options(),
                    {"default": STYLE_OFF_LABEL},
                ),
                "style_preset_2": (
                    get_style_options(),
                    {"default": STYLE_OFF_LABEL},
                ),
                "style_preset_3": (
                    get_style_options(),
                    {"default": STYLE_OFF_LABEL},
                ),
                "additional_styles": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "forceInput": True,
                        "placeholder": "Connect OVERTLI Style Stack output (STRING)...",
                    },
                ),
                "vision_enabled": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "label_on": "Vision ON",
                        "label_off": "Vision OFF",
                    },
                ),
                "batch_image_mode": (
                    ["all_frames", "first_middle_last", "first_frame"],
                    {"default": "all_frames"},
                ),
                "max_batch_frames": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 512,
                        "step": 1,
                    },
                ),
                "allow_all_paths": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "Allow All Paths",
                        "label_off": "Restricted Paths",
                    },
                ),
                "allow_all_tools": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "Allow All Tools",
                        "label_off": "Restricted Tools",
                    },
                ),
                "silent": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "label_on": "Silent Output",
                        "label_off": "Verbose Output",
                    },
                ),
                "output_format": (
                    ["text", "json"],
                    {
                        "default": "text",
                    },
                ),
                "timeout_seconds": (
                    "INT",
                    {
                        "default": 60,
                        "min": 5,
                        "max": 1200,
                        "step": 5,
                    },
                ),
                "max_output_tokens": (
                    "INT",
                    {
                        "default": _DEFAULT_MAX_OUTPUT_TOKENS,
                        "min": 64,
                        "max": 32768,
                        "step": 64,
                    },
                ),
            },
        }

    def execute(
        self,
        prompt: str,
        text_mode_enabled: bool,
        text_mode: str,
        image_mode_enabled: bool,
        image_mode: str,
        video_mode_enabled: bool,
        video_mode: str,
        tts_mode_enabled: bool,
        tts_mode: str,
        model: str,
        image: Optional[Any] = None,
        file_path: str = "",
        custom_model: str = "",
        copilot_executable: str = "",
        persist_copilot_executable: bool = True,
        persist_selected_model: bool = True,
        auth_mode: str = "Auto",
        auth_status_only: bool = False,
        reconnect: bool = False,
        custom_instructions: str = "",
        style_preset_1: str = STYLE_OFF_LABEL,
        style_preset_2: str = STYLE_OFF_LABEL,
        style_preset_3: str = STYLE_OFF_LABEL,
        additional_styles: str = "",
        vision_enabled: bool = True,
        retry_cached_vision_models: bool = True,
        batch_image_mode: str = "all_frames",
        max_batch_frames: int = 0,
        allow_all_paths: bool = False,
        allow_all_tools: bool = False,
        silent: bool = True,
        output_format: str = "text",
        timeout_seconds: int = 60,
        max_output_tokens: int = _DEFAULT_MAX_OUTPUT_TOKENS,
        max_output_chars: int = 0,
    ) -> Tuple[str]:
        """Execute the Copilot CLI command and return response text."""
        config = get_config()

        runtime_executable = normalize_string_input(copilot_executable)
        if runtime_executable and persist_copilot_executable:
            save_persistent_settings(
                {"copilot_executable": runtime_executable},
                source="GZ_CopilotAgent",
            )

        configured_executable = resolve_config_value(
            "copilot_executable",
            runtime_executable,
            default=normalize_string_input(config.copilot.executable, default="copilot"),
        )

        resolved_executable = _resolve_copilot_executable(configured_executable)

        selected_model = normalize_string_input(model)
        if not selected_model:
            selected_model = resolve_config_value(
                "copilot_model",
                default=config.copilot.default_model,
            )

        if selected_model and persist_selected_model:
            save_persistent_settings(
                {"copilot_model": selected_model},
                source="GZ_CopilotAgent",
            )

        selected_auth_mode = normalize_string_input(auth_mode, default="Auto")
        if selected_auth_mode not in _AUTH_MODE_OPTIONS:
            selected_auth_mode = "Auto"

        env_override_var, _env_override_value = _detect_token_override()

        if output_format not in ("text", "json"):
            raise OvertliInputError(
                f"Invalid output_format '{output_format}'. Must be 'text' or 'json'.",
                input_name="output_format",
            )

        source_type, source_value = validate_single_image_source(
            image_tensor=image,
            file_path=file_path,
        )
        image_tensor = image if source_type == "tensor" else None

        effective_timeout = self.clamp_timeout(timeout_seconds or config.copilot.timeout)
        login_timeout = self.clamp_timeout(max(effective_timeout, 300), minimum=30, maximum=1800)
        command_temp_dir = config.temp_dir or tempfile.gettempdir()
        effective_max_output_chars = _resolve_output_char_limit(max_output_tokens, max_output_chars)

        notices: list[str] = []

        def _add_notice(text: str) -> None:
            cleaned = normalize_string_input(text)
            if cleaned and cleaned not in notices:
                notices.append(cleaned)

        if env_override_var:
            _add_notice(
                (
                    f"Auth token source is overridden by environment variable '{env_override_var}'. "
                    "Stored Copilot OAuth credentials are ignored while this variable is set."
                )
            )

        if auth_status_only:
            status_args = [
                "--model",
                selected_model,
                "--prompt",
                "Reply with exactly: AUTH_OK",
                "--output-format",
                "text",
                "--allow-all-tools",
                "--silent",
            ]

            try:
                status_code, status_stdout, status_stderr = _run_copilot_command(
                    executable_path=resolved_executable,
                    temp_dir=command_temp_dir,
                    args=status_args,
                    timeout_seconds=effective_timeout,
                    max_output_chars=effective_max_output_chars,
                )
            except subprocess.TimeoutExpired as exc:
                raise OvertliTimeoutError(
                    f"Copilot auth status probe timed out after {effective_timeout} seconds",
                    timeout_seconds=effective_timeout,
                    operation="copilot --prompt (status probe)",
                ) from exc

            if status_code == 0:
                _set_last_auth_status("authenticated")
                lines = [
                    "Auth status: authenticated",
                    f"Auth mode: {selected_auth_mode}",
                    f"Model: {selected_model}",
                ]
                lines.extend([f"Notice: {notice}" for notice in notices])
                return ("\n".join(lines),)

            classification = _classify_cli_error(status_stderr, status_stdout, env_override_var)
            _set_last_auth_status(classification)
            lines = [
                f"Auth status: {classification}",
                f"Auth mode: {selected_auth_mode}",
                f"Model: {selected_model}",
            ]

            if classification == "env_token_override":
                lines.append(
                    (
                        f"Authentication failed while '{env_override_var}' is set. "
                        "Unset/fix that variable to use the stored Copilot login."
                    )
                )
            elif classification == "not_signed_in":
                lines.append("No active Copilot login detected. Use auth_mode='Sign in' or enable reconnect.")
            elif classification == "subscription_issue":
                lines.append("Copilot plan/subscription appears unavailable for this account.")
            elif classification == "rate_limited":
                lines.append("Copilot reported a rate limit or exhausted usage bucket.")
            elif classification == "upstream_timeout":
                lines.append("Copilot accepted the request, but the upstream service timed out.")
            elif classification == "service_busy":
                lines.append("Copilot service reported temporary heavy usage or capacity issues.")
            elif classification == "model_unavailable":
                lines.append("The selected model appears unavailable or unsupported for this CLI/account.")

            if status_stderr:
                lines.append(f"stderr: {status_stderr[:400]}")

            lines.extend([f"Notice: {notice}" for notice in notices])
            return ("\n".join(lines),)

        temp_image_paths: list[str] = []
        context_paths: list[str] = []

        try:
            login_attempted = False

            if reconnect or selected_auth_mode == "Sign in":
                if env_override_var:
                    _add_notice(
                        (
                            "Reconnect/login flow skipped because an environment token override is active. "
                            f"Current override: {env_override_var}."
                        )
                    )
                else:
                    login_code, login_stdout, login_stderr = _run_copilot_command(
                        executable_path=resolved_executable,
                        temp_dir=command_temp_dir,
                        args=["login"],
                        timeout_seconds=login_timeout,
                        max_output_chars=effective_max_output_chars,
                    )
                    login_attempted = True
                    if login_code != 0:
                        classification = _classify_cli_error(login_stderr, login_stdout, env_override_var)
                        _set_last_auth_status(classification)
                        raise OvertliAPIError(
                            (
                                "Copilot login flow failed. "
                                f"Classification: {classification}. "
                                f"Details: {(login_stderr or login_stdout or 'No output')[:400]}"
                            ),
                            endpoint="copilot login",
                            status_code=login_code,
                        )
                    _set_last_auth_status("authenticated")

            if source_type == "file" and vision_enabled:
                resolved_file = os.path.abspath(str(source_value))
                if not os.path.exists(resolved_file):
                    raise OvertliInputError(
                        f"Provided file_path does not exist: {resolved_file}",
                        input_name="file_path",
                    )
                is_valid, reason = _validate_image_file_context(resolved_file)
                if not is_valid:
                    _add_notice(f"Image skipped for size/format: {reason}.")
                else:
                    context_paths = [resolved_file]

            elif source_type == "tensor" and vision_enabled and image_tensor is not None:
                if len(image_tensor.shape) >= 3:
                    height = int(image_tensor.shape[1])
                    width = int(image_tensor.shape[2])
                    if height > _MAX_IMAGE_DIMENSION or width > _MAX_IMAGE_DIMENSION:
                        _add_notice(
                            (
                                "Image skipped for size/format: "
                                f"dimensions {width}x{height} exceed max {_MAX_IMAGE_DIMENSION}px per side."
                            )
                        )
                        image_tensor = None

                if image_tensor is None:
                    indices = []
                elif len(image_tensor.shape) == 4 and image_tensor.shape[0] > 1:
                    indices = select_image_batch_indices(
                        batch_size=image_tensor.shape[0],
                        batch_image_mode=batch_image_mode,
                        max_batch_frames=max_batch_frames,
                    )
                else:
                    indices = [0]

                for index in indices:
                    temp_path = comfy_image_to_tempfile(
                        image_tensor,
                        batch_index=index,
                        prefix="overtli_copilot_",
                        temp_dir=config.temp_dir,
                    )
                    is_valid, reason = _validate_image_file_context(temp_path)
                    if not is_valid:
                        _add_notice(f"Image skipped for size/format: {reason}.")
                        cleanup_temp_file(temp_path)
                        continue

                    temp_image_paths.append(temp_path)

                context_paths = list(temp_image_paths)
            elif source_type != "none" and not vision_enabled:
                _add_notice("Image context skipped because vision is disabled.")

            if context_paths:
                supports_vision, capability_source = _get_model_capability(selected_model)
                if not supports_vision and capability_source == "heuristic":
                    if retry_cached_vision_models:
                        retry_model = _select_vision_retry_model(
                            selected_model,
                            excluded_models={_model_cache_key(selected_model)},
                        )
                        if retry_model:
                            previous_model = selected_model
                            selected_model = retry_model
                            _add_notice(
                                (
                                    f"Model '{previous_model}' appears text-only for image input. "
                                    f"Automatically switched to vision-capable model '{selected_model}'."
                                )
                            )
                        else:
                            raise OvertliModelError(
                                build_user_facing_error(
                                    "Selected Copilot model does not support image analysis in this environment.",
                                    what_happened=(
                                        f"The model '{selected_model}' appears text-only for image inputs, "
                                        "and no vision-capable fallback model was discovered from your Copilot CLI."
                                    ),
                                    what_we_tried=(
                                        "Validated image attachments, checked cached model capability, and attempted "
                                        "automatic fallback to a vision-capable model."
                                    ),
                                    next_steps=(
                                        "Choose a known vision-capable model in the Copilot model dropdown "
                                        "(for example gpt-5-mini), or verify available models with `copilot help config`."
                                    ),
                                ),
                                model_name=selected_model,
                                context={"endpoint": "copilot --prompt", "reason": "vision_fallback_missing"},
                            )
                    else:
                        raise OvertliModelError(
                            build_user_facing_error(
                                "Selected Copilot model does not support image analysis in this environment.",
                                what_happened=(
                                    f"The model '{selected_model}' appears text-only for image inputs."
                                ),
                                what_we_tried=(
                                    "Validated image attachments and model capability before dispatch."
                                ),
                                next_steps=(
                                    "Enable retry_cached_vision_models for automatic model switching, "
                                    "or select a vision-capable model manually."
                                ),
                            ),
                            model_name=selected_model,
                            context={"endpoint": "copilot --prompt", "reason": "vision_retry_disabled"},
                        )

                elif not supports_vision and capability_source == "runtime":
                    if retry_cached_vision_models:
                        _add_notice(
                            (
                                f"Model '{selected_model}' was previously cached as vision-unsupported, "
                                "but image attachments will be retried because vision is enabled."
                            )
                        )
                    else:
                        _add_notice(
                            (
                                f"Vision unsupported for model '{selected_model}' (cached runtime result). "
                                "Image context skipped."
                            )
                        )
                        context_paths = []

            if context_paths:
                attachment_names = [os.path.basename(path) for path in context_paths]
                preview_names = ", ".join(attachment_names[:3])
                if len(attachment_names) > 3:
                    preview_names += ", ..."
                logger.info(
                    "Copilot image context prepared: %s attachment(s): %s",
                    len(context_paths),
                    preview_names,
                )
            elif source_type != "none" and vision_enabled:
                logger.info(
                    "Copilot image context prepared: 0 attachment(s) after validation/limits checks."
                )

            if context_paths and not normalize_string_input(prompt):
                logger.info(
                    (
                        "Copilot request has empty user prompt; adding explicit image-analysis instruction "
                        "before attachment references."
                    )
                )

            resolved_mode = resolve_mode_family_preset(
                text_mode_enabled=text_mode_enabled,
                text_mode=text_mode,
                image_mode_enabled=image_mode_enabled,
                image_mode=image_mode,
                video_mode_enabled=video_mode_enabled,
                video_mode=video_mode,
                tts_mode_enabled=tts_mode_enabled,
                tts_mode=tts_mode,
            )

            fallback_category = "text"
            if image_mode_enabled:
                fallback_category = "image"
            elif video_mode_enabled:
                fallback_category = "video"
            elif tts_mode_enabled:
                fallback_category = "tts"

            mode_category = infer_mode_category(resolved_mode, fallback=fallback_category)

            base_prompt = build_prompt(
                mode_preset=resolved_mode,
                custom_instructions=custom_instructions,
                raw_prompt=prompt,
                mode_category=mode_category,
                style_preset_1=style_preset_1,
                style_preset_2=style_preset_2,
                style_preset_3=style_preset_3,
                additional_styles=additional_styles,
            ).strip()

            allow_all_tools_effective = True
            if not allow_all_tools:
                logger.info(
                    (
                        "Non-interactive Copilot mode requires --allow-all-tools; "
                        "auto-enabling it for reliability."
                    )
                )

            def _build_cli_args(current_context_paths: list[str], force_prompt_pipe: bool = False) -> tuple[list[str], bool, str]:
                prompt_parts = [base_prompt] if base_prompt else []
                if current_context_paths:
                    if not normalize_string_input(prompt):
                        # Copilot may ignore attachment references unless a concrete task is present.
                        prompt_parts.append(
                            "Analyze the attached image files and describe what is visible in clear detail."
                        )

                    context_lines = []
                    for path in current_context_paths:
                        # Node-based CLIs can treat backslashes as escapes in prompt text.
                        safe_path = str(path).replace("\\", "/")
                        safe_path = safe_path.replace('"', '\\"')

                        # Keep spaced paths as one attachment token.
                        if " " in safe_path:
                            context_lines.append(f'@"{safe_path}"')
                        else:
                            context_lines.append(f"@{safe_path}")

                    prompt_parts.append(
                        "Reference image attachments:\n"
                        + "\n".join(context_lines)
                        + "\nUse these files as required input and base your response only on visible content."
                    )

                cli_prompt = "\n\n".join(prompt_parts).strip()
                cli_prompt = self.require_prompt(cli_prompt, input_name="prompt")

                # Keep --prompt as the default transport, including multiline/image prompts.
                # Copilot's @file attachment parsing is most reliable when prompt text comes
                # through the explicit --prompt argument. Only fall back to stdin when the
                # caller explicitly requests it (command-length retry path).
                use_prompt_pipe = bool(force_prompt_pipe)
                if len(cli_prompt) > _WINDOWS_PROMPT_ARG_SAFE_CHARS:
                    use_prompt_pipe = True

                args = [
                    "--model",
                    selected_model,
                    "--output-format",
                    output_format,
                ]

                stdin_prompt_text = ""
                if use_prompt_pipe:
                    stdin_prompt_text = cli_prompt
                else:
                    args.extend(["--prompt", cli_prompt])

                if silent:
                    args.append("--silent")

                if allow_all_paths:
                    args.append("--allow-all-paths")
                else:
                    parent_dirs = sorted({os.path.dirname(path) for path in current_context_paths if os.path.dirname(path)})
                    for parent_dir in parent_dirs:
                        args.extend(["--add-dir", parent_dir])

                if allow_all_tools_effective:
                    args.append("--allow-all-tools")

                return args, use_prompt_pipe, stdin_prompt_text

            active_context_paths = list(context_paths)
            retried_without_vision = False
            retried_after_login = False
            force_prompt_pipe = False
            timeout_retried = False
            command_timeout = effective_timeout
            vision_retry_attempted_models: set[str] = {_model_cache_key(selected_model)}
            model_availability_checked: set[str] = set()

            result_stdout = ""

            while True:
                selected_model_key = _model_cache_key(selected_model)
                if selected_model_key not in model_availability_checked:
                    model_availability_checked.add(selected_model_key)
                    discovered_models = _discover_copilot_cli_models()
                    if discovered_models and not _is_model_listed(selected_model, discovered_models):
                        retry_model = ""
                        if active_context_paths:
                            retry_model = _select_retry_model_from_discovered(
                                selected_model,
                                discovered_models,
                                excluded_models=vision_retry_attempted_models,
                                require_vision=True,
                            )
                            if not retry_model:
                                retry_model = _select_vision_retry_model(
                                    selected_model,
                                    excluded_models=vision_retry_attempted_models,
                                )
                        else:
                            retry_model = _select_retry_model_from_discovered(
                                selected_model,
                                discovered_models,
                                excluded_models=vision_retry_attempted_models,
                                require_vision=False,
                            )

                        if retry_model:
                            previous_model = selected_model
                            selected_model = retry_model
                            vision_retry_attempted_models.add(_model_cache_key(selected_model))
                            _add_notice(
                                (
                                    f"Model '{previous_model}' is not listed by current Copilot CLI availability. "
                                    f"Automatically rerouted to '{selected_model}' before dispatch."
                                )
                            )
                            continue

                cli_args, used_prompt_pipe, stdin_prompt_text = _build_cli_args(
                    active_context_paths,
                    force_prompt_pipe=force_prompt_pipe,
                )

                prompt_payload_text = stdin_prompt_text
                if not used_prompt_pipe and "--prompt" in cli_args:
                    prompt_payload_text = cli_args[cli_args.index("--prompt") + 1]

                transport_label = "stdin" if used_prompt_pipe else "--prompt"
                logger.info(
                    "Copilot CLI dispatch: model='%s' transport=%s prompt_chars=%s attachments=%s add_dirs=%s has_attachment_block=%s.",
                    selected_model,
                    transport_label,
                    len(prompt_payload_text),
                    len(active_context_paths),
                    cli_args.count("--add-dir"),
                    "Reference image attachments:" in prompt_payload_text,
                )

                try:
                    return_code, stdout_text, stderr_text = _run_copilot_command(
                        executable_path=resolved_executable,
                        temp_dir=command_temp_dir,
                        args=cli_args,
                        timeout_seconds=command_timeout,
                        max_output_chars=effective_max_output_chars,
                        stdin_text=stdin_prompt_text,
                    )
                except subprocess.TimeoutExpired as exc:
                    timeout_stdout = _coerce_timeout_stream(getattr(exc, "output", ""))
                    timeout_stderr = _coerce_timeout_stream(getattr(exc, "stderr", ""))
                    timeout_excerpt = (timeout_stderr or timeout_stdout or "No CLI output before timeout")[:500]

                    if not timeout_retried:
                        timeout_retried = True
                        command_timeout = min(
                            _COPILOT_TIMEOUT_RETRY_MAX_SECONDS,
                            max(_COPILOT_TIMEOUT_RETRY_MIN_SECONDS, command_timeout * 2),
                        )
                        retry_notice = (
                            "Copilot response was slower than expected. "
                            f"Automatically retrying once with timeout={command_timeout}s."
                        )
                        logger.warning(retry_notice)
                        _add_notice(retry_notice)
                        continue

                    timeout_message = build_user_facing_error(
                        "Copilot request timed out.",
                        what_happened=(
                            f"Copilot CLI did not finish within {command_timeout} seconds."
                        ),
                        what_we_tried=(
                            "Ran non-interactive Copilot CLI with direct prompt/stdin transport, "
                            "captured partial output, and retried once with an extended timeout."
                        ),
                        next_steps=(
                            "Increase timeout_seconds, reduce prompt/context size, verify `copilot login`, "
                            "or switch to a faster model for this run."
                        ),
                        details=f"CLI excerpt: {timeout_excerpt}",
                    )
                    logger.error(timeout_message)
                    raise OvertliTimeoutError(
                        timeout_message,
                        timeout_seconds=command_timeout,
                        operation="copilot --prompt",
                    ) from exc

                result_stdout = stdout_text

                if return_code == 0:
                    if active_context_paths and _looks_like_text_only_image_response(result_stdout):
                        _set_model_capability(selected_model, supports_vision=False, source="runtime")
                        retry_model = _select_vision_retry_model(
                            selected_model,
                            excluded_models=vision_retry_attempted_models,
                        )
                        if retry_model:
                            previous_model = selected_model
                            selected_model = retry_model
                            vision_retry_attempted_models.add(_model_cache_key(selected_model))
                            _add_notice(
                                (
                                    f"Model '{previous_model}' returned a text-only image response. "
                                    f"Automatically retried with vision-capable model '{selected_model}'."
                                )
                            )
                            continue

                        _add_notice(
                            (
                                f"Model '{selected_model}' appears to ignore image attachments in this CLI setup. "
                                "No vision-capable fallback model was detected automatically."
                            )
                        )

                    _set_last_auth_status("authenticated")
                    break

                classification = _classify_cli_error(stderr_text, stdout_text, env_override_var)

                if classification == "command_too_long" and not used_prompt_pipe:
                    force_prompt_pipe = True
                    _add_notice(
                        (
                            "Prompt exceeded Windows command-line limits. "
                            "Retrying with stdin prompt transport."
                        )
                    )
                    continue

                if classification == "command_too_long" and used_prompt_pipe:
                    raise OvertliAPIError(
                        (
                            "Copilot CLI still hit command-line limits even after stdin prompt fallback. "
                            "Try reducing context payload size or simplifying prompt content."
                        ),
                        endpoint="copilot --prompt",
                        status_code=return_code,
                    )

                if classification == "vision_unsupported" and active_context_paths and not retried_without_vision:
                    _set_model_capability(selected_model, supports_vision=False, source="runtime")
                    _add_notice(
                        (
                            f"Vision unsupported for model '{selected_model}'. "
                            "Image context was skipped and the request was retried as text-only."
                        )
                    )
                    active_context_paths = []
                    retried_without_vision = True
                    continue

                if classification == "model_unavailable":
                    vision_retry_attempted_models.add(_model_cache_key(selected_model))
                    discovered_models = _discover_copilot_cli_models()
                    retry_model = ""
                    if active_context_paths:
                        retry_model = _select_retry_model_from_discovered(
                            selected_model,
                            discovered_models,
                            excluded_models=vision_retry_attempted_models,
                            require_vision=True,
                        )
                        if not retry_model:
                            retry_model = _select_vision_retry_model(
                                selected_model,
                                excluded_models=vision_retry_attempted_models,
                            )
                    else:
                        retry_model = _select_retry_model_from_discovered(
                            selected_model,
                            discovered_models,
                            excluded_models=vision_retry_attempted_models,
                            require_vision=False,
                        )

                    if retry_model:
                        previous_model = selected_model
                        selected_model = retry_model
                        vision_retry_attempted_models.add(_model_cache_key(selected_model))
                        _add_notice(
                            (
                                f"Model '{previous_model}' was unavailable for this account. "
                                f"Automatically retried with '{selected_model}'."
                            )
                        )
                        continue

                if classification == "not_signed_in":
                    _set_last_auth_status("not_signed_in")

                    should_auto_login = (
                        selected_auth_mode == "Auto"
                        and not retried_after_login
                        and not login_attempted
                        and not env_override_var
                    )

                    if should_auto_login:
                        try:
                            login_code, login_stdout, login_stderr = _run_copilot_command(
                                executable_path=resolved_executable,
                                temp_dir=command_temp_dir,
                                args=["login"],
                                timeout_seconds=login_timeout,
                                max_output_chars=effective_max_output_chars,
                            )
                        except subprocess.TimeoutExpired as exc:
                            login_timeout_message = build_user_facing_error(
                                "Copilot sign-in timed out.",
                                what_happened=f"`copilot login` did not complete within {login_timeout} seconds.",
                                what_we_tried="Triggered automatic sign-in because auth_mode='Auto'.",
                                next_steps=(
                                    "Run `copilot login` manually in a terminal and complete OAuth, "
                                    "then retry the node."
                                ),
                                details=(
                                    f"CLI excerpt: {(_coerce_timeout_stream(getattr(exc, 'stderr', '')) or _coerce_timeout_stream(getattr(exc, 'output', '')) or 'No output')[:500]}"
                                ),
                            )
                            logger.error(login_timeout_message)
                            raise OvertliTimeoutError(
                                login_timeout_message,
                                timeout_seconds=login_timeout,
                                operation="copilot login",
                            ) from exc
                        login_attempted = True
                        if login_code == 0:
                            _set_last_auth_status("authenticated")
                            retried_after_login = True
                            continue

                        login_excerpt = login_stderr or login_stdout or "No output"
                        login_message = build_user_facing_error(
                            "Copilot auto-login failed.",
                            what_happened="Automatic sign-in did not complete successfully after the CLI reported a missing login state.",
                            what_we_tried="Triggered `copilot login` from auth_mode='Auto' and captured the CLI result.",
                            next_steps="Run `copilot login` manually in a terminal, complete the auth flow, then retry the node.",
                            details=f"CLI excerpt: {login_excerpt[:400]}",
                        )
                        logger.error(login_message)
                        raise OvertliAPIError(
                            login_message,
                            endpoint="copilot login",
                            status_code=login_code,
                        )

                if classification in {
                    "not_signed_in",
                    "subscription_issue",
                    "env_token_override",
                    "rate_limited",
                    "upstream_timeout",
                    "service_busy",
                    "model_unavailable",
                    "unknown",
                }:
                    if classification in {"subscription_issue", "env_token_override", "not_signed_in"}:
                        _set_last_auth_status(classification)
                    message, error_type = _build_copilot_cli_failure(
                        classification,
                        selected_model=selected_model,
                        stderr_text=stderr_text,
                        stdout_text=stdout_text,
                        env_override_var=env_override_var,
                    )
                    logger.error(message)
                    if error_type is OvertliTimeoutError:
                        raise OvertliTimeoutError(
                            message,
                            timeout_seconds=command_timeout,
                            operation="copilot --prompt",
                        )
                    if error_type is OvertliModelError:
                        raise OvertliModelError(
                            message,
                            model_name=selected_model,
                            context={"endpoint": "copilot --prompt", "status_code": return_code},
                        )
                    raise OvertliAPIError(
                        message,
                        endpoint="copilot --prompt",
                        status_code=return_code,
                    )

            if output_format == "json":
                parsed_text = _extract_text_from_jsonl(result_stdout)
                result_text = parsed_text or result_stdout
            else:
                result_text = result_stdout

            result_text = sanitize_text_output(result_text, mode_hint="text").strip()
            if not result_text:
                raise OvertliAPIError(
                    "Copilot CLI returned an empty response",
                    endpoint="copilot --prompt",
                )

            if notices:
                for notice in notices:
                    logger.info("Copilot notice: %s", notice)

            logger.info(
                "GZ_CopilotAgent completed with model '%s' (attachments_sent=%s).",
                selected_model,
                len(active_context_paths),
            )
            return (result_text,)

        except subprocess.TimeoutExpired as exc:
            timeout_stdout = _coerce_timeout_stream(getattr(exc, "output", ""))
            timeout_stderr = _coerce_timeout_stream(getattr(exc, "stderr", ""))
            timeout_message = build_user_facing_error(
                "Copilot command timed out.",
                what_happened=f"The Copilot CLI did not complete within {effective_timeout} seconds.",
                what_we_tried="Captured command output and preserved partial diagnostics.",
                next_steps="Increase timeout_seconds or test `copilot` manually in a terminal.",
                details=f"CLI excerpt: {(timeout_stderr or timeout_stdout or 'No output')[:500]}",
            )
            logger.error(timeout_message)
            raise OvertliTimeoutError(
                timeout_message,
                timeout_seconds=effective_timeout,
                operation="copilot --prompt",
            ) from exc
        except FileNotFoundError as exc:
            raise OvertliConfigError(
                f"Copilot executable not found: {configured_executable}",
                config_key="COPILOT_EXECUTABLE",
            ) from exc
        finally:
            for temp_image_path in temp_image_paths:
                removed = cleanup_temp_file(temp_image_path)
                if not removed:
                    logger.warning("Failed to cleanup temporary image: %s", temp_image_path)

