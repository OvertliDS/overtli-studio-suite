# ============================================================================
# pollinations/speech_to_text.py
# GZ_SpeechToText - Speech-to-text via Pollinations audio transcription API
# ============================================================================
"""
GZ_SpeechToText: Pollinations Speech-to-Text Node
=================================================
Transcribes local audio files using Pollinations-compatible STT models.

Features:
- Uses /v1/audio/transcriptions (multipart upload)
- Dynamic model list based on catalog endpoint/modality metadata
- Optional language and prompt hints for better transcription quality
- Supports json/text/srt/vtt style outputs
- Accepts either an audio file path or direct ComfyUI AUDIO input
"""

import json
import importlib
import logging
import mimetypes
import os
import tempfile
import time
import wave
from typing import Any, Tuple

requests = importlib.import_module("requests")

from ..audio_style_presets import (
    AUDIO_STYLE_OFF,
    get_audio_style_options,
    resolve_audio_style_hint,
    resolve_audio_style_instruction,
)
from ..exceptions import OvertliAPIError, OvertliInputError, OvertliTimeoutError
from ..settings_store import resolve_config_value, save_persistent_settings
from ..shared_utils import build_user_facing_error
from ..suite_config import get_config
from .model_catalog import fetch_pollinations_audio_models_for_task

logger = logging.getLogger(__name__)


DEFAULT_STT_MODELS = [
    "whisper [stt] [fallback]",
    "whisper-large-v3 [stt] [fallback]",
    "gpt-4o-mini-transcribe [stt] [fallback]",
]

RESPONSE_FORMATS = (
    "json",
    "text",
    "srt",
    "verbose_json",
    "vtt",
)

STT_LANGUAGE_OPTIONS = (
    "auto",
    "en",
    "zh",
    "de",
    "es",
    "ru",
    "ko",
    "fr",
    "ja",
    "pt",
    "tr",
    "pl",
    "ca",
    "nl",
    "ar",
    "sv",
    "it",
    "id",
    "hi",
    "fi",
    "vi",
    "he",
    "uk",
    "el",
    "ms",
    "cs",
    "ro",
    "da",
    "hu",
    "ta",
    "no",
    "th",
    "ur",
    "hr",
    "bg",
    "lt",
    "la",
    "mi",
    "ml",
    "cy",
    "sk",
    "te",
    "fa",
    "lv",
    "bn",
    "sr",
    "az",
    "sl",
    "kn",
    "et",
    "mk",
    "br",
    "eu",
    "is",
    "hy",
    "ne",
    "mn",
    "bs",
    "kk",
    "sq",
    "sw",
    "gl",
    "mr",
    "pa",
    "si",
    "km",
    "sn",
    "yo",
    "so",
    "af",
    "oc",
    "ka",
    "be",
    "tg",
    "sd",
    "gu",
    "am",
    "yi",
    "lo",
    "uz",
    "fo",
    "ht",
    "ps",
    "tk",
    "nn",
    "mt",
    "sa",
    "lb",
    "my",
    "bo",
    "tl",
    "mg",
    "as",
    "tt",
    "haw",
    "ln",
    "ha",
    "ba",
    "jw",
    "su",
    "yue",
)


def _extract_model_name(model_display: str) -> str:
    if not model_display:
        return "whisper"
    return model_display.split(" [", 1)[0].strip()


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


def _resolve_audio_file_path(audio_file_path: str) -> str:
    candidate = (audio_file_path or "").strip().strip('"').strip("'")
    if not candidate:
        return ""

    if os.path.isfile(candidate):
        return os.path.abspath(candidate)

    try:
        import folder_paths

        search_roots = [
            folder_paths.get_input_directory(),
            folder_paths.get_temp_directory(),
            os.getcwd(),
        ]
    except Exception:
        search_roots = [os.getcwd()]

    for root in search_roots:
        if not root:
            continue
        joined = os.path.abspath(os.path.join(root, candidate))
        if os.path.isfile(joined):
            return joined

    return os.path.abspath(candidate)


def _write_audio_input_to_temp_wav(audio_input: Any) -> str:
    """Serialize ComfyUI AUDIO input to a temporary WAV file path."""
    if not isinstance(audio_input, dict):
        raise OvertliInputError("AUDIO input must be a dict containing waveform and sample_rate.", input_name="audio")

    waveform = audio_input.get("waveform")
    sample_rate = audio_input.get("sample_rate")

    if waveform is None:
        raise OvertliInputError("AUDIO input is missing waveform data.", input_name="audio")
    if sample_rate in (None, ""):
        raise OvertliInputError("AUDIO input is missing sample_rate.", input_name="audio")

    try:
        sample_rate_int = int(sample_rate)
    except Exception as exc:  # noqa: BLE001
        raise OvertliInputError("AUDIO sample_rate must be numeric.", input_name="audio") from exc

    if sample_rate_int <= 0:
        raise OvertliInputError("AUDIO sample_rate must be greater than zero.", input_name="audio")

    np = importlib.import_module("numpy")

    try:
        if hasattr(waveform, "detach"):
            waveform_np = waveform.detach().cpu().float().numpy()
        else:
            waveform_np = np.asarray(waveform, dtype=np.float32)
    except Exception as exc:  # noqa: BLE001
        raise OvertliInputError("Unable to read AUDIO waveform tensor.", input_name="audio") from exc

    if waveform_np.size == 0:
        raise OvertliInputError("AUDIO waveform is empty.", input_name="audio")

    if waveform_np.ndim == 3:
        # Comfy audio is typically [batch, channels, samples].
        waveform_np = waveform_np[0]

    if waveform_np.ndim == 1:
        waveform_np = waveform_np[:, np.newaxis]
    elif waveform_np.ndim == 2:
        if waveform_np.shape[0] <= 8 and waveform_np.shape[1] > waveform_np.shape[0]:
            # Likely [channels, samples] -> transpose to [samples, channels].
            waveform_np = waveform_np.T
        elif waveform_np.shape[1] > 8 and waveform_np.shape[0] <= waveform_np.shape[1]:
            # Keep as [samples, channels].
            pass
        elif waveform_np.shape[1] <= 8 and waveform_np.shape[0] > waveform_np.shape[1]:
            # Already [samples, channels].
            pass
        else:
            # Ambiguous shape, use first channel as mono.
            waveform_np = waveform_np[:, :1]
    else:
        raise OvertliInputError(
            f"Unsupported AUDIO waveform rank: {waveform_np.ndim} (expected 1D/2D/3D)",
            input_name="audio",
        )

    waveform_np = np.clip(waveform_np.astype(np.float32), -1.0, 1.0)
    pcm16 = (waveform_np * 32767.0).astype(np.int16)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
        temp_path = temp_file.name

    with wave.open(temp_path, "wb") as wav_handle:
        wav_handle.setnchannels(int(pcm16.shape[1]))
        wav_handle.setsampwidth(2)
        wav_handle.setframerate(sample_rate_int)
        wav_handle.writeframes(pcm16.tobytes())

    return temp_path


class GZ_SpeechToText:
    """Pollinations speech-to-text node for file-path or direct AUDIO inputs."""

    CATEGORY = "OVERTLI STUDIO/Media"
    FUNCTION = "execute"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("transcript",)
    OUTPUT_NODE = False

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        from ..instruction_modes import get_speech_to_text_modes

        model_options = fetch_pollinations_audio_models_for_task("transcription", DEFAULT_STT_MODELS)

        return {
            "required": {
                "model": (
                    model_options,
                    {"default": model_options[0] if model_options else DEFAULT_STT_MODELS[0]},
                ),
                "mode_preset": (list(get_speech_to_text_modes().keys()), {"default": "Off"}),
                "response_format": (RESPONSE_FORMATS, {"default": "text"}),
            },
            "optional": {
                "audio": ("AUDIO",),
                "input_language": (
                    STT_LANGUAGE_OPTIONS,
                    {
                        "default": "auto",
                    },
                ),
                "prompt": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "placeholder": "Optional prompt/context to improve recognition.",
                    },
                ),
                "custom_instructions": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "forceInput": True,
                        "placeholder": "Optional transcript cleanup/format instructions...",
                    },
                ),
                "stt_style_preset": (
                    get_audio_style_options("stt"),
                    {"default": AUDIO_STYLE_OFF},
                ),
                "temperature": (
                    "FLOAT",
                    {
                        "default": 0.5,
                        "min": 0.0,
                        "max": 2.0,
                        "step": 0.05,
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
        model: str,
        mode_preset: str,
        response_format: str = "text",
        audio: Any = None,
        input_language: str = "auto",
        prompt: str = "",
        custom_instructions: str = "",
        stt_style_preset: str = AUDIO_STYLE_OFF,
        temperature: float = 0.5,
        api_key: str = "",
        persist_api_key: bool = False,
    ) -> Tuple[str]:
        config = get_config()
        pollinations_cfg = config.pollinations

        temp_audio_path = ""
        if audio is None:
            raise OvertliInputError(
                "AUDIO input is required for transcription.",
                input_name="audio",
            )

        resolved_audio_path = _write_audio_input_to_temp_wav(audio)
        temp_audio_path = resolved_audio_path

        model_name = _extract_model_name(model)
        if not model_name:
            model_name = "whisper"

        normalized_response_format = (response_format or "text").strip().lower()
        if normalized_response_format not in RESPONSE_FORMATS:
            normalized_response_format = "text"

        runtime_api_key = (api_key or "").strip()
        if runtime_api_key and persist_api_key:
            save_persistent_settings(
                {"pollinations_api_key": runtime_api_key},
                source="GZ_SpeechToText",
            )

        effective_api_key = resolve_config_value(
            "pollinations_api_key",
            runtime_api_key,
            default=(pollinations_cfg.api_key or ""),
        )

        headers: dict[str, str] = {}
        if effective_api_key:
            headers["Authorization"] = f"Bearer {effective_api_key}"
            headers["x-api-key"] = effective_api_key

        data: dict[str, object] = {
            "model": model_name,
            "response_format": normalized_response_format,
            "temperature": max(0.0, min(float(temperature), 2.0)),
        }

        style_hint = (resolve_audio_style_hint("stt", stt_style_preset) or "").strip()
        style_instruction = (resolve_audio_style_instruction("stt", stt_style_preset) or "").strip()

        language_hint = (input_language or "auto").strip().lower()
        if language_hint and language_hint != "auto":
            data["language"] = language_hint
        prompt_text = (prompt or "").strip()
        if prompt_text and style_hint:
            data["prompt"] = f"{prompt_text}\n\nStyle hint: {style_hint}"
        elif prompt_text:
            data["prompt"] = prompt_text
        elif style_hint:
            data["prompt"] = style_hint

        mime_type = mimetypes.guess_type(resolved_audio_path)[0] or "application/octet-stream"
        request_timeout = max(30, pollinations_cfg.stt_timeout)

        try:
            logger.info(
                "Pollinations STT request started (model=%s, endpoint=%s, timeout=%ss, file=%s).",
                model_name,
                pollinations_cfg.audio_transcriptions_endpoint,
                request_timeout,
                os.path.basename(resolved_audio_path),
            )
            started_at = time.monotonic()
            with open(resolved_audio_path, "rb") as handle:
                files = {
                    "file": (
                        os.path.basename(resolved_audio_path),
                        handle,
                        mime_type,
                    )
                }
                response = requests.post(
                    pollinations_cfg.audio_transcriptions_endpoint,
                    files=files,
                    data=data,
                    headers=headers if headers else None,
                    timeout=request_timeout,
                )

            response.raise_for_status()
            elapsed = time.monotonic() - started_at
            logger.info(
                "Pollinations STT request completed in %.2fs (model=%s).",
                elapsed,
                model_name,
            )
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            body = exc.response.text[:400] if exc.response is not None else str(exc)
            http_message = build_user_facing_error(
                "Pollinations STT API request failed.",
                what_happened=f"Provider returned HTTP {status}.",
                what_we_tried=(
                    f"Uploaded audio file to {pollinations_cfg.audio_transcriptions_endpoint} using model '{model_name}'."
                ),
                next_steps="Check file format/size, API key limits, and model availability.",
                details=f"Response excerpt: {body}",
            )
            logger.error(http_message)
            raise OvertliAPIError(
                http_message,
                endpoint=pollinations_cfg.audio_transcriptions_endpoint,
                status_code=status,
            ) from exc
        except requests.exceptions.Timeout as exc:
            timeout_message = build_user_facing_error(
                "Pollinations STT request timed out.",
                what_happened=f"No transcription response was received within {request_timeout} seconds.",
                what_we_tried=(
                    f"Uploaded '{os.path.basename(resolved_audio_path)}' for transcription with model '{model_name}'."
                ),
                next_steps="Try a shorter audio clip or increase GZ_POLLINATIONS_STT_TIMEOUT.",
            )
            logger.error(timeout_message)
            raise OvertliTimeoutError(
                timeout_message,
                timeout_seconds=request_timeout,
                operation="pollinations speech-to-text",
            ) from exc
        except Exception as exc:  # noqa: BLE001
            logger.exception("Pollinations STT request failed")
            fallback_message = build_user_facing_error(
                "Pollinations STT request failed.",
                what_happened=f"Unexpected error: {exc}",
                what_we_tried="Executed multipart upload transcription request.",
                next_steps="Review terminal logs and verify provider/network availability.",
            )
            raise OvertliAPIError(
                fallback_message,
                endpoint=pollinations_cfg.audio_transcriptions_endpoint,
            ) from exc
        finally:
            if temp_audio_path and os.path.isfile(temp_audio_path):
                try:
                    os.remove(temp_audio_path)
                except Exception as cleanup_exc:  # noqa: BLE001
                    logger.warning("Failed to remove temporary STT audio file %s: %s", temp_audio_path, cleanup_exc)

        content_type = (response.headers.get("content-type") or "").lower()
        if "json" in content_type:
            payload = response.json()
            transcript = payload.get("text") if isinstance(payload, dict) else ""
            if not transcript:
                transcript = json.dumps(payload, ensure_ascii=False)
        else:
            transcript = response.text.strip()

        final_transcript = transcript.strip()
        merged_custom_instructions = (custom_instructions or "").strip()
        if style_instruction:
            merged_custom_instructions = (
                f"{merged_custom_instructions}\n\n{style_instruction}" if merged_custom_instructions else style_instruction
            )
        should_refine = bool(merged_custom_instructions) or (mode_preset or "").strip() not in {"", "Off"}
        if should_refine and final_transcript:
            from ..instruction_modes import resolve_mode_preset

            instructions = resolve_mode_preset(
                mode_preset=mode_preset,
                custom_instructions=merged_custom_instructions,
                mode_category_hint="speech_to_text",
            )
            if not instructions:
                instructions = (
                    "Clean and structure this transcript for readability while preserving meaning, names, and facts. "
                    "Do not invent content."
                )

            formatting_payload = {
                "model": "openai-fast",
                "messages": [
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": final_transcript},
                ],
                "max_tokens": 1400,
                "temperature": 0.2,
            }

            try:
                formatting_response = requests.post(
                    pollinations_cfg.chat_endpoint,
                    json=formatting_payload,
                    headers=headers if headers else None,
                    timeout=30,
                )
                if formatting_response.ok:
                    payload = formatting_response.json()
                    if isinstance(payload, dict):
                        choices = payload.get("choices")
                        if isinstance(choices, list) and choices:
                            first_choice = choices[0]
                            if isinstance(first_choice, dict):
                                message = first_choice.get("message")
                                if isinstance(message, dict):
                                    content = message.get("content", final_transcript)
                                else:
                                    content = final_transcript
                                normalized = _extract_text_content(content).strip()
                                if normalized:
                                    final_transcript = normalized
            except Exception as exc:  # noqa: BLE001
                logger.warning("GZ_SpeechToText: transcript post-processing failed: %s", exc)

        return (final_transcript,)
