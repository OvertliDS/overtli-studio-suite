# ============================================================================
# pollinations/text_to_audio.py
# GZ_TextToAudio - Text-to-audio/music via Pollinations audio endpoints
# ============================================================================
"""
GZ_TextToAudio: Pollinations Text-to-Audio Node
===============================================
Generates music from text prompts using Pollinations audio APIs.

Features:
- Uses /v1/audio/speech for rich text-to-audio generation controls
- Supports music-oriented controls (instrumental, style mode, duration)
- Returns native ComfyUI AUDIO output
"""

import logging
import importlib
import os
import tempfile
import time
from typing import Any, Tuple

requests = importlib.import_module("requests")

from ..audio_style_presets import (
    AUDIO_STYLE_OFF,
    get_audio_style_options,
    resolve_audio_style_hint,
    resolve_audio_style_instruction,
)
from ..exceptions import OvertliAPIError, OvertliInputError
from .compat_retry import execute_with_compat_retry
from ..settings_store import resolve_config_value, save_persistent_settings
from ..shared_utils import build_user_facing_error
from ..suite_config import get_config
from .model_catalog import extract_display_model_name, fetch_pollinations_audio_models_for_task

logger = logging.getLogger(__name__)


DEFAULT_AUDIO_GEN_MODELS = [
    "openai-audio [speech] [fallback]",
    "openai-audio-large [speech] [fallback]",
    "elevenlabs [speech] [fallback]",
    "elevenmusic [music] [fallback]",
    "acestep [music] [fallback]",
]

VOICE_OPTIONS = (
    "alloy",
    "echo",
    "fable",
    "onyx",
    "nova",
    "shimmer",
    "coral",
    "verse",
    "ballad",
    "ash",
    "sage",
    "amuch",
    "dan",
)

RESPONSE_FORMATS = (
    "mp3",
    "wav",
    "opus",
    "aac",
    "flac",
    "pcm",
)


def _extract_model_name(model_display: str) -> str:
    if not model_display:
        return "openai-audio"
    return extract_display_model_name(model_display) or "openai-audio"


def _extract_text_content(value):
    """Normalize chat content payload into plain text."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = [_extract_text_content(item) for item in value]
        return "\n".join(part for part in parts if part)
    if isinstance(value, dict):
        if isinstance(value.get("text"), str):
            return value["text"]
        if "content" in value:
            return _extract_text_content(value["content"])
    return ""


def _is_music_model(model_name: str) -> bool:
    lowered = (model_name or "").lower()
    return any(token in lowered for token in ("music", "acestep", "udio", "riffusion"))


def _cleanup_stale_audio_files(temp_dir: str, max_age_hours: int = 24) -> None:
    """Best-effort cleanup for old temporary audio files."""
    try:
        cutoff = time.time() - (max_age_hours * 3600)
        for filename in os.listdir(temp_dir):
            if not (filename.startswith("overtli_audio_") or filename.startswith("overtli_tts_")):
                continue
            path = os.path.join(temp_dir, filename)
            if not os.path.isfile(path):
                continue
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
    except Exception as exc:  # noqa: BLE001
        logger.debug("GZ_TextToAudio: stale cleanup skipped due to error: %s", exc)


def _suffix_from_audio_response(content_type: str, requested_format: str) -> str:
    normalized_format = (requested_format or "").lower()
    if normalized_format in RESPONSE_FORMATS:
        if normalized_format == "pcm":
            return ".pcm"
        return f".{normalized_format}"

    lowered = (content_type or "").lower()
    if "wav" in lowered:
        return ".wav"
    if "ogg" in lowered or "opus" in lowered:
        return ".opus"
    if "aac" in lowered:
        return ".aac"
    if "flac" in lowered:
        return ".flac"
    if "pcm" in lowered:
        return ".pcm"
    return ".mp3"


def _stream_response_to_temp_file(
    response: Any,
    temp_dir: str,
    requested_format: str,
    max_audio_bytes: int,
) -> str:
    content_length = response.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > max_audio_bytes:
        raise OvertliAPIError(
            f"Audio exceeds max_audio_bytes ({content_length} > {max_audio_bytes})",
            status_code=response.status_code,
        )

    suffix = _suffix_from_audio_response(response.headers.get("content-type", ""), requested_format)
    bytes_written = 0

    with tempfile.NamedTemporaryFile(
        prefix="overtli_audio_",
        suffix=suffix,
        delete=False,
        dir=temp_dir,
    ) as temp_file:
        for chunk in response.iter_content(chunk_size=8192):
            if not chunk:
                continue
            bytes_written += len(chunk)
            if bytes_written > max_audio_bytes:
                raise OvertliAPIError(
                    f"Audio stream exceeded max_audio_bytes ({bytes_written} > {max_audio_bytes})",
                    status_code=response.status_code,
                )
            temp_file.write(chunk)
        return temp_file.name


def _audio_path_to_output(audio_path: str) -> dict[str, Any]:
    """Load a local audio file and convert it to ComfyUI AUDIO format."""
    from comfy_extras.nodes_audio import load as load_audio_file

    waveform, sample_rate = load_audio_file(audio_path)
    return {
        "waveform": waveform.unsqueeze(0),
        "sample_rate": int(sample_rate),
    }


class GZ_TextToAudio:
    """Pollinations text-to-music node."""

    CATEGORY = "OVERTLI STUDIO/Media"
    FUNCTION = "execute"
    RETURN_TYPES = ("AUDIO",)
    RETURN_NAMES = ("audio",)
    OUTPUT_NODE = False

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        from ..instruction_modes import get_text_to_audio_modes

        model_options = fetch_pollinations_audio_models_for_task("generation", DEFAULT_AUDIO_GEN_MODELS)

        return {
            "required": {
                "text": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "placeholder": "Describe speech content, ambience, or a music concept...",
                    },
                ),
                "mode_preset": (list(get_text_to_audio_modes().keys()), {"default": "Off"}),
                "model": (
                    model_options,
                    {"default": model_options[0] if model_options else DEFAULT_AUDIO_GEN_MODELS[0]},
                ),
                "response_format": (RESPONSE_FORMATS, {"default": "mp3"}),
            },
            "optional": {
                "custom_instructions": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "forceInput": True,
                        "placeholder": "Optional text-to-audio prompt guidance...",
                    },
                ),
                "music_style_preset": (
                    get_audio_style_options("ttaudio"),
                    {"default": AUDIO_STYLE_OFF},
                ),
                "speed": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": 0.25,
                        "max": 4.0,
                        "step": 0.05,
                    },
                ),
                "duration": (
                    "INT",
                    {
                        "default": 10,
                        "min": 0,
                        "max": 600,
                        "step": 1,
                    },
                ),
                "instrumental": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "Instrumental",
                        "label_off": "With Vocals/Voice",
                    },
                ),
                "api_key": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "placeholder": "Optional Pollinations API key...",
                    },
                ),
                "persist_api_key": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "Persist API Key",
                        "label_off": "Session Only",
                    },
                ),
            },
        }

    def execute(
        self,
        text: str,
        mode_preset: str,
        model: str,
        response_format: str = "mp3",
        custom_instructions: str = "",
        music_style_preset: str = AUDIO_STYLE_OFF,
        speed: float = 1.0,
        duration: int = 10,
        instrumental: bool = False,
        max_audio_bytes: int = 52428800,
        api_key: str = "",
        persist_api_key: bool = False,
    ) -> Tuple[dict[str, Any]]:
        config = get_config()
        pollinations_cfg = config.pollinations
        temp_dir = config.temp_dir or tempfile.gettempdir()

        prompt = (text or "").strip()
        if not prompt:
            raise OvertliInputError("Input text cannot be empty for audio generation", input_name="text")

        style_hint = (resolve_audio_style_hint("ttaudio", music_style_preset) or "").strip()
        style_instruction = (resolve_audio_style_instruction("ttaudio", music_style_preset) or "").strip()
        merged_custom_instructions = (custom_instructions or "").strip()
        if style_instruction:
            merged_custom_instructions = (
                f"{merged_custom_instructions}\n\n{style_instruction}" if merged_custom_instructions else style_instruction
            )

        _cleanup_stale_audio_files(temp_dir)

        model_name = _extract_model_name(model)
        if not model_name:
            model_name = "openai-audio"

        instrumental_flag = bool(instrumental)

        if not _is_music_model(model_name):
            logger.warning(
                "GZ_TextToAudio: non-music model '%s' selected on text-to-music node; forcing elevenmusic.",
                model_name,
            )
            model_name = "elevenmusic"

        runtime_api_key = (api_key or "").strip()
        if runtime_api_key and persist_api_key:
            save_persistent_settings(
                {"pollinations_api_key": runtime_api_key},
                source="GZ_TextToAudio",
            )

        effective_api_key = resolve_config_value(
            "pollinations_api_key",
            runtime_api_key,
            default=(pollinations_cfg.api_key or ""),
        )

        auth_headers: dict[str, str] = {}
        if effective_api_key:
            auth_headers["Authorization"] = f"Bearer {effective_api_key}"
            auth_headers["x-api-key"] = effective_api_key

        requested_format = (response_format or "mp3").strip().lower()
        if requested_format not in RESPONSE_FORMATS:
            requested_format = "mp3"

        effective_style = style_hint

        output_path = ""
        payload: dict[str, object] = {
            "model": model_name,
            "input": prompt,
            "response_format": requested_format,
            "speed": max(0.25, min(float(speed), 4.0)),
            "instrumental": instrumental_flag,
        }
        if duration > 0:
            payload["duration"] = int(duration)
        if effective_style:
            payload["style"] = effective_style

        headers = {"Content-Type": "application/json"}
        headers.update(auth_headers)

        request_timeout = max(30, pollinations_cfg.audio_generation_timeout)

        try:
            logger.info(
                "Pollinations text-to-audio request started (/v1/audio/speech, model=%s, timeout=%ss).",
                model_name,
                request_timeout,
            )
            started_at = time.monotonic()
            response = execute_with_compat_retry(
                send_request=lambda _req_params, req_payload: requests.post(
                    pollinations_cfg.audio_speech_endpoint,
                    json=req_payload,
                    headers=headers,
                    timeout=request_timeout,
                    stream=True,
                ),
                endpoint=pollinations_cfg.audio_speech_endpoint,
                model_name=model_name,
                logger=logger,
                payload=payload,
                optional_payload_keys={
                    "response_format",
                    "style",
                    "instrumental",
                    "speed",
                    "duration",
                },
                max_attempts=3,
            )

            with response:
                output_path = _stream_response_to_temp_file(
                    response=response,
                    temp_dir=temp_dir,
                    requested_format=requested_format,
                    max_audio_bytes=max_audio_bytes,
                )

            elapsed = time.monotonic() - started_at
            logger.info(
                "Pollinations text-to-audio request completed in %.2fs (/v1/audio/speech, model=%s).",
                elapsed,
                model_name,
            )

            audio_output = _audio_path_to_output(output_path)
            return (audio_output,)
        except requests.exceptions.Timeout as exc:
            timeout_message = build_user_facing_error(
                "Pollinations text-to-audio timed out.",
                what_happened=(
                    f"No audio response was received within {request_timeout} seconds."
                ),
                what_we_tried=f"Requested model '{model_name}' via /v1/audio/speech endpoint.",
                next_steps="Try shorter input, reduce controls, or increase GZ_POLLINATIONS_AUDIO_TIMEOUT.",
            )
            raise OvertliAPIError(timeout_message, endpoint=pollinations_cfg.audio_speech_endpoint) from exc
        except requests.exceptions.HTTPError as exc:
            response = getattr(exc, "response", None)
            status = response.status_code if response is not None else None
            body = response.text[:300] if response is not None else str(exc)
            endpoint_error = build_user_facing_error(
                "Pollinations /v1/audio/speech API request failed.",
                what_happened=f"Provider returned HTTP {status}.",
                what_we_tried=f"Submitted generation payload using model '{model_name}'.",
                next_steps="Check model availability, API key limits, and payload compatibility.",
                details=f"Response excerpt: {body}",
            )
            raise OvertliAPIError(endpoint_error, endpoint=pollinations_cfg.audio_speech_endpoint, status_code=status) from exc
        except OvertliAPIError:
            raise
        except Exception as exc:  # noqa: BLE001
            endpoint_error = build_user_facing_error(
                "Pollinations /v1/audio/speech request failed.",
                what_happened=f"Unexpected error: {exc}",
                what_we_tried="Executed audio generation request with compatibility fallback logic.",
                next_steps="Review terminal logs for full stack details.",
            )
            raise OvertliAPIError(endpoint_error, endpoint=pollinations_cfg.audio_speech_endpoint) from exc
        finally:
            if output_path and os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except Exception:  # noqa: BLE001
                    pass
