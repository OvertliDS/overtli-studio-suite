# ============================================================================
# pollinations/compat_retry.py
# Shared compatibility-aware request retry helper
# ============================================================================
"""
Compatibility retry helper for Pollinations media endpoints.

Behavior:
- Attempt 1 always uses the full payload/params.
- On HTTP 400 with compatibility-like signals, retries by removing optional
  knobs in a deterministic order.
- Logs every attempt with endpoint, model, removed keys, and a redacted body
  preview.
- Raises actionable errors after retries are exhausted.
"""

from __future__ import annotations

import importlib
import logging
import re
from typing import Any, Callable, Iterable

requests = importlib.import_module("requests")

from ..exceptions import OvertliAPIError
from ..shared_utils import build_user_facing_error


COMPATIBILITY_DROP_ORDER = (
    "seed",
    "style",
    "instrumental",
    "voice",
    "response_format",
)

COMPATIBILITY_SIGNAL_KEYWORDS = (
    "unsupported",
    "not support",
    "unknown parameter",
    "unknown field",
    "unrecognized",
    "unexpected",
    "invalid parameter",
    "invalid field",
    "not allowed",
    "not permitted",
    "does not allow",
    "additional properties",
    "must not have",
    "bad request",
)


def _redact_sensitive_text(value: str) -> str:
    """Redact likely secrets in logs/errors without over-processing content."""
    if not value:
        return ""

    redacted = value
    patterns = (
        (r"(?i)(bearer\s+)([A-Za-z0-9._\-=]+)", r"\1[REDACTED]"),
        (r"(?i)(x-api-key\s*[:=]\s*)([^\s,;]+)", r"\1[REDACTED]"),
        (r"(?i)(api[_-]?key\s*[:=]\s*)([^\s,;]+)", r"\1[REDACTED]"),
        (r'(?i)("api[_-]?key"\s*:\s*")([^"]+)(")', r"\1[REDACTED]\3"),
        (r'(?i)("authorization"\s*:\s*"bearer\s+)([^"]+)(")', r"\1[REDACTED]\3"),
    )
    for pattern, replacement in patterns:
        redacted = re.sub(pattern, replacement, redacted)
    return redacted


def _body_preview(response: Any | None, fallback: str, max_chars: int) -> str:
    raw = ""
    if response is not None:
        try:
            raw = response.text or ""
        except Exception:  # noqa: BLE001
            raw = ""
    if not raw:
        raw = fallback

    compact = " ".join((raw or "").split())
    compact = _redact_sensitive_text(compact)
    return compact[:max_chars]


def _is_compatibility_error(status_code: int | None, preview: str, optional_keys: set[str]) -> bool:
    if status_code != 400:
        return False

    lowered = (preview or "").lower()
    if any(keyword in lowered for keyword in COMPATIBILITY_SIGNAL_KEYWORDS):
        return True

    return any(optional_key in lowered for optional_key in optional_keys)


def _ordered_optional_keys(
    params: dict[str, Any],
    payload: dict[str, Any],
    optional_param_keys: set[str],
    optional_payload_keys: set[str],
) -> list[str]:
    available = {
        key
        for key in optional_param_keys
        if key in params
    } | {
        key
        for key in optional_payload_keys
        if key in payload
    }

    ordered = [key for key in COMPATIBILITY_DROP_ORDER if key in available]
    ordered.extend(sorted(key for key in available if key not in set(COMPATIBILITY_DROP_ORDER)))
    return ordered


def _drop_optional_key(
    key: str,
    params: dict[str, Any],
    payload: dict[str, Any],
    optional_param_keys: set[str],
    optional_payload_keys: set[str],
) -> list[str]:
    removed: list[str] = []
    if key in optional_param_keys and key in params:
        params.pop(key, None)
        removed.append(f"params.{key}")
    if key in optional_payload_keys and key in payload:
        payload.pop(key, None)
        removed.append(f"json.{key}")
    return removed


def _build_attempt_summary(
    endpoint: str,
    model_name: str,
    attempts: list[dict[str, Any]],
) -> str:
    parts: list[str] = []
    for record in attempts:
        removed = ", ".join(record["removed"]) if record["removed"] else "none"
        parts.append(
            f"attempt={record['attempt']} status={record['status']} removed={removed} body='{record['body']}'"
        )
    joined = " | ".join(parts) if parts else "no attempts recorded"
    return build_user_facing_error(
        "Pollinations compatibility fallback exhausted.",
        what_happened=(
            "The provider kept rejecting requests even after optional-parameter fallback retries."
        ),
        what_we_tried=(
            "Retried request by progressively removing optional parameters such as seed/style/voice "
            "when compatibility-like HTTP 400 errors were detected."
        ),
        next_steps=(
            "Try a simpler payload, switch models, or check provider-side compatibility changes. "
            "If this persists, inspect the attempt log details below."
        ),
        details=f"endpoint={endpoint}, model={model_name}, attempts={joined}",
    )


def execute_with_compat_retry(
    *,
    send_request: Callable[[dict[str, Any], dict[str, Any]], Any],
    endpoint: str,
    model_name: str,
    logger: logging.Logger,
    params: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
    optional_param_keys: Iterable[str] | None = None,
    optional_payload_keys: Iterable[str] | None = None,
    max_attempts: int = 3,
    body_preview_chars: int = 220,
) -> Any:
    """
    Execute a request with compatibility-aware optional-field fallback.

    Non-HTTP failures (timeouts, connection errors, etc.) are intentionally not
    retried here so node-specific timeout handling remains authoritative.
    """
    if max_attempts < 1:
        max_attempts = 1

    current_params = dict(params or {})
    current_payload = dict(payload or {})
    opt_param_keys = {str(k).strip().lower() for k in (optional_param_keys or []) if str(k).strip()}
    opt_payload_keys = {str(k).strip().lower() for k in (optional_payload_keys or []) if str(k).strip()}

    # Normalize keys for matching while preserving original values.
    param_key_lookup = {k.lower(): k for k in current_params.keys()}
    payload_key_lookup = {k.lower(): k for k in current_payload.keys()}

    normalized_params = {k.lower(): v for k, v in current_params.items()}
    normalized_payload = {k.lower(): v for k, v in current_payload.items()}

    ordered_keys = _ordered_optional_keys(
        params=normalized_params,
        payload=normalized_payload,
        optional_param_keys=opt_param_keys,
        optional_payload_keys=opt_payload_keys,
    )

    attempt_records: list[dict[str, Any]] = []
    removed_chain: list[str] = []

    for attempt in range(1, max_attempts + 1):
        # Rehydrate dicts with original key casing before each send.
        send_params = {
            (param_key_lookup.get(k, k)): v
            for k, v in normalized_params.items()
        }
        send_payload = {
            (payload_key_lookup.get(k, k)): v
            for k, v in normalized_payload.items()
        }

        try:
            response = send_request(send_params, send_payload)
            response.raise_for_status()

            if attempt > 1:
                logger.info(
                    "Compatibility retry succeeded on attempt %s/%s endpoint='%s' model='%s' removed=%s",
                    attempt,
                    max_attempts,
                    endpoint,
                    model_name,
                    removed_chain or ["none"],
                )
            return response

        except requests.exceptions.HTTPError as exc:
            response = exc.response
            status = response.status_code if response is not None else None
            preview = _body_preview(response, str(exc), body_preview_chars)

            attempt_records.append(
                {
                    "attempt": attempt,
                    "status": status,
                    "removed": list(removed_chain),
                    "body": preview,
                }
            )

            logger.warning(
                "Compatibility attempt %s/%s failed endpoint='%s' model='%s' status=%s removed=%s body='%s'",
                attempt,
                max_attempts,
                endpoint,
                model_name,
                status,
                removed_chain or ["none"],
                preview,
            )

            should_retry = (
                attempt < max_attempts
                and _is_compatibility_error(status, preview, set(ordered_keys))
            )

            if not should_retry:
                if attempt > 1:
                    raise OvertliAPIError(
                        _build_attempt_summary(endpoint, model_name, attempt_records),
                        endpoint=endpoint,
                        status_code=status,
                    ) from exc
                raise

            next_key = next(
                (
                    key
                    for key in ordered_keys
                    if (key in opt_param_keys and key in normalized_params)
                    or (key in opt_payload_keys and key in normalized_payload)
                ),
                None,
            )

            if not next_key:
                raise OvertliAPIError(
                    _build_attempt_summary(endpoint, model_name, attempt_records),
                    endpoint=endpoint,
                    status_code=status,
                ) from exc

            removed: list[str] = []
            if next_key in opt_param_keys and next_key in normalized_params:
                normalized_params.pop(next_key, None)
                removed.append(f"params.{next_key}")
            if next_key in opt_payload_keys and next_key in normalized_payload:
                normalized_payload.pop(next_key, None)
                removed.append(f"json.{next_key}")

            if not removed:
                raise OvertliAPIError(
                    _build_attempt_summary(endpoint, model_name, attempt_records),
                    endpoint=endpoint,
                    status_code=status,
                ) from exc

            removed_chain.extend(removed)
            logger.info(
                "Compatibility retry removing optional key '%s' (%s) before next attempt endpoint='%s' model='%s'",
                next_key,
                ", ".join(removed),
                endpoint,
                model_name,
            )

            if response is not None:
                try:
                    response.close()
                except Exception:  # noqa: BLE001
                    pass

    # Defensive fallback; loop should always return or raise before this point.
    raise OvertliAPIError(
        "Compatibility retry failed without explicit error state.",
        endpoint=endpoint,
    )
