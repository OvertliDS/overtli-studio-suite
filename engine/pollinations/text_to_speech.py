# ============================================================================
# pollinations/text_to_speech.py
# GZ_TextToSpeech - TTS via Pollinations.ai audio models
# ============================================================================
"""
GZ_TextToSpeech: Pollinations Text-to-Speech Node
==================================================
Uses openai-audio and elevenlabs models for high-quality speech synthesis.

Features:
- Multiple voice options (alloy, echo, fable, onyx, nova, shimmer, etc.)
- TTS-optimized mode presets for script formatting
- Returns native ComfyUI AUDIO output
"""

import logging
import importlib
import os
import tempfile
import time
import urllib.parse
from typing import Any, Tuple

requests = importlib.import_module("requests")

from ...styles.audio_styles import AUDIO_STYLE_OFF, get_audio_style_options, resolve_audio_style_instruction
from ...exceptions import OvertliAPIError, OvertliInputError, OvertliTimeoutError
from .compat_retry import execute_with_compat_retry
from .model_catalog import extract_display_model_name, fetch_pollinations_audio_models_for_task
from ...settings_store import resolve_config_value, save_persistent_settings
from ...shared_utils import build_user_facing_error
from ...suite_config import get_config

logger = logging.getLogger(__name__)


def _extract_text_content(value):
    """Normalize chat content into plain text."""
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


def _cleanup_stale_audio_files(temp_dir: str, max_age_hours: int = 24) -> None:
    """Best-effort cleanup of old OVERTLI and legacy Grizzy temporary audio files."""
    try:
        cutoff = time.time() - (max_age_hours * 3600)
        for filename in os.listdir(temp_dir):
            if not (filename.startswith("grizzy_tts_") or filename.startswith("overtli_tts_")):
                continue
            path = os.path.join(temp_dir, filename)
            if not os.path.isfile(path):
                continue
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
    except Exception as exc:  # noqa: BLE001
        logger.debug("GZ_TextToSpeech: stale cleanup skipped due to error: %s", exc)


def _audio_path_to_output(audio_path: str) -> dict[str, Any]:
    """Load a local audio file and convert it to ComfyUI AUDIO format."""
    audio_module = importlib.import_module("comfy_extras.nodes_audio")
    load_audio_file = getattr(audio_module, "load")

    waveform, sample_rate = load_audio_file(audio_path)
    return {
        "waveform": waveform.unsqueeze(0),
        "sample_rate": int(sample_rate),
    }


# ============================================================================
# Voice Options
# ============================================================================

VOICE_OPTIONS = [
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
]

DEFAULT_TTS_MODELS = [
    "openai-audio [speech] [fallback]",
    "elevenlabs [speech] [fallback]",
    "elevenmusic [music] [fallback]",
]


# ============================================================================
# GZ_TextToSpeech Node
# ============================================================================


class GZ_TextToSpeech:
    """
    Pollinations Text-to-Speech Node

    Converts text to speech using cloud TTS models.
    Can also generate music with elevenmusic model.
    """

    CATEGORY = "OVERTLI STUDIO/Media"
    FUNCTION = "execute"
    RETURN_TYPES = ("AUDIO", "STRING")
    RETURN_NAMES = ("audio", "script_text")
    OUTPUT_NODE = False

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        from ...instruction_modes import get_tts_modes

        model_options = fetch_pollinations_audio_models_for_task("generation", DEFAULT_TTS_MODELS)

        return {
            "required": {
                "text": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "placeholder": "Enter text to convert to speech...",
                    },
                ),
                "mode_preset": (list(get_tts_modes().keys()), {"default": "Off"}),
                "model": (
                    model_options,
                    {"default": model_options[0] if model_options else "openai-audio [speech] [fallback]"},
                ),
                "voice": (VOICE_OPTIONS, {"default": "nova"}),
            },
            "optional": {
                "custom_instructions": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "forceInput": True,
                        "placeholder": "Custom script formatting instructions...",
                    },
                ),
                "tts_style_preset": (
                    get_audio_style_options("tts"),
                    {"default": AUDIO_STYLE_OFF},
                ),
                "format_script": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "Format for TTS",
                        "label_off": "Raw Text",
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
        voice: str,
        custom_instructions: str = "",
        tts_style_preset: str = AUDIO_STYLE_OFF,
        format_script: bool = False,
        max_audio_bytes: int = 52428800,
        api_key: str = "",
        persist_api_key: bool = False,
    ) -> Tuple[dict[str, Any], str]:
        """Execute TTS via Pollinations API."""
        config = get_config()
        pollinations_cfg = config.pollinations
        temp_dir = config.temp_dir or tempfile.gettempdir()

        model_name = extract_display_model_name(model) or "openai-audio"
        if "music" in model_name.lower():
            logger.warning(
                "GZ_TextToSpeech: music-capable model '%s' selected on speech-only node; forcing openai-audio.",
                model_name,
            )
            model_name = "openai-audio"
        is_music = False

        if api_key and persist_api_key:
            save_persistent_settings(
                {"pollinations_api_key": api_key},
                source="GZ_TextToSpeech",
            )

        effective_api_key = resolve_config_value(
            "pollinations_api_key",
            api_key,
            default=(pollinations_cfg.api_key or ""),
        )

        headers: dict[str, str] = {}
        if effective_api_key:
            headers["Authorization"] = f"Bearer {effective_api_key}"
            headers["x-api-key"] = effective_api_key

        final_text = (text or "").strip()

        if not final_text:
            raise OvertliInputError("Input text cannot be empty for TTS generation", input_name="text")

        style_instruction = resolve_audio_style_instruction("tts", tts_style_preset)
        merged_custom_instructions = (custom_instructions or "").strip()
        if style_instruction:
            merged_custom_instructions = (
                f"{merged_custom_instructions}\n\n{style_instruction}" if merged_custom_instructions else style_instruction
            )

        _cleanup_stale_audio_files(temp_dir)

        # Optionally format script for TTS via chat endpoint.
        if format_script and not is_music and final_text.strip():
            from ...instruction_modes import resolve_mode_preset

            instructions = resolve_mode_preset(
                mode_preset=mode_preset,
                custom_instructions=merged_custom_instructions,
                mode_category_hint="tts",
            )
            if not instructions:
                instructions = (
                    "Format this text for natural text-to-speech delivery. "
                    "Add appropriate pauses, emphasis markers, and break long "
                    "sentences for better flow."
                )

            format_payload = {
                "model": "openai-fast",
                "messages": [
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": final_text},
                ],
                "max_tokens": 1000,
                "temperature": 0.5,
            }

            try:
                resp = requests.post(
                    pollinations_cfg.chat_endpoint,
                    json=format_payload,
                    headers=headers if headers else None,
                    timeout=30,
                )
                if resp.ok:
                    data = resp.json()
                    if "choices" in data and data["choices"]:
                        content = data["choices"][0].get("message", {}).get("content", final_text)
                        normalized = _extract_text_content(content).strip()
                        if normalized:
                            final_text = normalized
                        logger.info("GZ_TextToSpeech: Formatted script to %s chars", len(final_text))
            except Exception as exc:  # noqa: BLE001
                logger.warning("GZ_TextToSpeech: Script formatting failed: %s", exc)

        # Build audio URL:
        # gen.pollinations.ai/audio/{text}?model=openai-audio&voice=nova
        if len(final_text) > 3000:
            logger.warning("GZ_TextToSpeech: input text exceeds 3000 chars, truncating to API-safe limit")
        encoded_text = urllib.parse.quote(final_text[:3000], safe="")
        url = f"{pollinations_cfg.audio_endpoint}/{encoded_text}"

        params = {"model": model_name}
        if not is_music:
            params["voice"] = voice

        audio_path = ""
        try:
            request_timeout = max(30, pollinations_cfg.tts_timeout)
            logger.info(
                "Pollinations TTS request started (model=%s, endpoint=%s, timeout=%ss, mode=%s).",
                model_name,
                url,
                request_timeout,
                "speech",
            )
            started_at = time.monotonic()
            response = execute_with_compat_retry(
                send_request=lambda req_params, _req_payload: requests.get(
                    url,
                    params=req_params,
                    headers=headers if headers else None,
                    timeout=request_timeout,
                    stream=True,
                ),
                endpoint=url,
                model_name=model_name,
                logger=logger,
                params=params,
                optional_param_keys={"voice"},
                max_attempts=3,
            )

            with response:

                content_length = response.headers.get("content-length")
                if content_length and content_length.isdigit() and int(content_length) > max_audio_bytes:
                    raise OvertliAPIError(
                        f"TTS audio exceeds max_audio_bytes ({content_length} > {max_audio_bytes})",
                        endpoint=url,
                    )

                # Determine output format from content-type header.
                content_type = response.headers.get("content-type", "")
                suffix = ".mp3"
                if "wav" in content_type:
                    suffix = ".wav"
                elif "ogg" in content_type:
                    suffix = ".ogg"

                # Save audio to temp file with bounded stream writes.
                bytes_written = 0
                with tempfile.NamedTemporaryFile(
                    prefix="overtli_tts_",
                    suffix=suffix,
                    delete=False,
                    dir=temp_dir,
                ) as tmp:
                    for chunk in response.iter_content(chunk_size=8192):
                        if not chunk:
                            continue
                        bytes_written += len(chunk)
                        if bytes_written > max_audio_bytes:
                            raise OvertliAPIError(
                                f"TTS stream exceeded max_audio_bytes ({bytes_written} > {max_audio_bytes})",
                                endpoint=url,
                            )
                        tmp.write(chunk)
                    audio_path = tmp.name

            elapsed = time.monotonic() - started_at
            logger.info(
                "Pollinations TTS request completed in %.2fs (model=%s).",
                elapsed,
                model_name,
            )
            logger.info("GZ_TextToSpeech: Saved audio to %s", audio_path)

            audio_output = _audio_path_to_output(audio_path)
            try:
                os.remove(audio_path)
            except Exception:  # noqa: BLE001
                pass

            return (audio_output, final_text)

        except requests.exceptions.Timeout as exc:
            request_timeout = max(30, pollinations_cfg.tts_timeout)
            timeout_message = build_user_facing_error(
                "Pollinations text-to-speech timed out.",
                what_happened=f"No audio response was received within {request_timeout} seconds.",
                what_we_tried=f"Requested model '{model_name}' from endpoint {url}.",
                next_steps="Try shorter input text, switch model, or increase GZ_POLLINATIONS_TTS_TIMEOUT.",
            )
            logger.error(timeout_message)
            raise OvertliTimeoutError(
                timeout_message,
                timeout_seconds=request_timeout,
                operation="pollinations text-to-speech",
            ) from exc
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            body = exc.response.text[:200] if exc.response is not None else str(exc)
            http_message = build_user_facing_error(
                "Pollinations text-to-speech API request failed.",
                what_happened=f"Provider returned HTTP {status}.",
                what_we_tried=f"Called endpoint {url} with model '{model_name}'.",
                next_steps="Check model availability, API key limits, and payload constraints.",
                details=f"Response excerpt: {body}",
            )
            logger.error(http_message)
            raise OvertliAPIError(
                http_message,
                endpoint=url,
                status_code=status,
            ) from exc
        except OvertliAPIError:
            raise
        except Exception as exc:  # noqa: BLE001
            if audio_path and os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                except Exception:  # noqa: BLE001
                    pass
            logger.exception("Pollinations TTS request failed")
            fallback_message = build_user_facing_error(
                "Pollinations text-to-speech failed.",
                what_happened=f"Unexpected error: {exc}",
                what_we_tried="Executed streaming audio request with compatibility fallback logic.",
                next_steps="Review terminal logs and verify provider/network availability.",
            )
            raise OvertliAPIError(fallback_message, endpoint=url) from exc


