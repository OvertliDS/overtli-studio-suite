"""Pollinations media upload helpers for reference-image forwarding."""

from __future__ import annotations

import base64
import importlib
import logging
import re
from typing import Optional

requests = importlib.import_module("requests")

from ...exceptions import OvertliInputError
from ...image_utils import comfy_image_to_base64

_MEDIA_UPLOAD_ENDPOINT = "https://media.pollinations.ai/upload"
_DATA_URL_PATTERN = re.compile(
    r"^data:(?P<mime>[\w.+-]+/[\w.+-]+);base64,(?P<data>[A-Za-z0-9+/=\s]+)$",
    re.IGNORECASE,
)


def _normalize_data_url(image_data_url: str) -> str:
    value = (image_data_url or "").strip()
    if value.startswith("data:image/"):
        return value
    return f"data:image/png;base64,{value}"


def _parse_data_url(image_data_url: str) -> tuple[str, str] | None:
    match = _DATA_URL_PATTERN.match((image_data_url or "").strip())
    if not match:
        return None
    mime_type = match.group("mime").lower()
    encoded_data = "".join(match.group("data").split())
    if not encoded_data:
        return None
    return mime_type, encoded_data


def _upload_json_payload(
    *,
    mime_type: str,
    encoded_data: str,
    api_key: str,
    timeout_seconds: int,
) -> Optional[str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "x-api-key": api_key,
    }
    payload = {
        "data": encoded_data,
        "contentType": mime_type,
        "name": "overtli_reference_image",
    }
    response = requests.post(
        _MEDIA_UPLOAD_ENDPOINT,
        json=payload,
        headers=headers,
        timeout=timeout_seconds,
    )
    if not response.ok:
        return None
    body = response.json() if response.content else {}
    if isinstance(body, dict):
        url = body.get("url")
        if isinstance(url, str) and url.startswith("http"):
            return url
        media_id = body.get("id")
        if isinstance(media_id, str) and media_id:
            return f"https://media.pollinations.ai/{media_id}"
    return None


def _upload_multipart_payload(
    *,
    mime_type: str,
    encoded_data: str,
    api_key: str,
    timeout_seconds: int,
) -> Optional[str]:
    try:
        binary_payload = base64.b64decode(encoded_data, validate=True)
    except Exception:
        return None

    extension = mime_type.split("/", 1)[-1] or "bin"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "x-api-key": api_key,
    }
    files = {
        "file": (f"overtli_reference_image.{extension}", binary_payload, mime_type),
    }
    response = requests.post(
        _MEDIA_UPLOAD_ENDPOINT,
        files=files,
        headers=headers,
        timeout=timeout_seconds,
    )
    if not response.ok:
        return None
    body = response.json() if response.content else {}
    if isinstance(body, dict):
        url = body.get("url")
        if isinstance(url, str) and url.startswith("http"):
            return url
        media_id = body.get("id")
        if isinstance(media_id, str) and media_id:
            return f"https://media.pollinations.ai/{media_id}"
    return None


def resolve_reference_image_value(
    *,
    image: object,
    api_key: str,
    logger: logging.Logger,
    context_label: str,
) -> str:
    """Return a Pollinations-compatible `image` value (URL preferred, data URL fallback)."""

    try:
        image_data_url = _normalize_data_url(comfy_image_to_base64(image))
    except Exception as exc:  # noqa: BLE001
        raise OvertliInputError(
            f"Failed to encode {context_label} reference image: {exc}",
            input_name="image",
        ) from exc

    parsed = _parse_data_url(image_data_url)
    if not parsed:
        return image_data_url

    mime_type, encoded_data = parsed
    effective_api_key = (api_key or "").strip()
    if not effective_api_key:
        logger.info(
            "Reference image forwarding for %s using data URL fallback (no Pollinations API key available).",
            context_label,
        )
        return image_data_url

    try:
        uploaded_url = _upload_json_payload(
            mime_type=mime_type,
            encoded_data=encoded_data,
            api_key=effective_api_key,
            timeout_seconds=30,
        )
        if not uploaded_url:
            uploaded_url = _upload_multipart_payload(
                mime_type=mime_type,
                encoded_data=encoded_data,
                api_key=effective_api_key,
                timeout_seconds=30,
            )

        if uploaded_url:
            logger.info(
                "Reference image forwarding for %s using uploaded Pollinations media URL.",
                context_label,
            )
            return uploaded_url

        logger.warning(
            "Reference image upload failed for %s; falling back to data URL forwarding.",
            context_label,
        )
        return image_data_url
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Reference image upload attempt failed for %s (%s). Falling back to data URL forwarding.",
            context_label,
            exc,
        )
        return image_data_url

