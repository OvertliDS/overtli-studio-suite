from __future__ import annotations

import base64
import io
import importlib
import logging
import os
import tempfile
import time
from typing import Any, Optional, Tuple

from ..base_node import GZBaseNode
from ..exceptions import OvertliAPIError, OvertliConfigError, OvertliInputError, OvertliTimeoutError, OvertliVisionError
from ..image_utils import binary_to_comfy_image, comfy_image_to_pil, validate_comfy_image
from ..instruction_modes import resolve_mode_family_preset
from ..output_sanitizer import sanitize_text_output
from ..styles import STYLE_OFF_LABEL, append_style_layers_to_prompt, infer_mode_category, normalize_style_presets
from ..settings_store import resolve_config_value, save_persistent_settings
from ..shared_utils import build_user_facing_error, normalize_string_input, select_image_batch_indices, validate_single_image_source
from ..suite_config import get_config

logger = logging.getLogger(__name__)
requests = importlib.import_module("requests")

_DEFAULT_TEXT_MAX_TOKENS = 750
_VIDEO_TEMP_PREFIX = "overtli_openai_video_"
_VIDEO_TEMP_MAX_AGE_SECONDS = 60 * 60 * 24

def _empty_image() -> Any:
    """Return a tiny blank ComfyUI IMAGE tensor for non-image execution paths."""
    try:
        torch = importlib.import_module("torch")

        return torch.zeros((1, 1, 1, 3), dtype=torch.float32)
    except Exception:
        # Fallback keeps routing stable even if torch is unavailable in editor-only contexts.
        return [[[[0.0, 0.0, 0.0]]]]


def _cleanup_stale_video_temp_files(temp_dir: str, *, max_age_seconds: int = _VIDEO_TEMP_MAX_AGE_SECONDS) -> int:
    """Delete stale Overtli video temp files to avoid long-term temp-dir bloat."""
    now = time.time()
    removed = 0

    try:
        for entry in os.scandir(temp_dir):
            if not entry.is_file():
                continue
            if not entry.name.startswith(_VIDEO_TEMP_PREFIX) or not entry.name.endswith(".mp4"):
                continue

            try:
                age_seconds = now - entry.stat().st_mtime
                if age_seconds < max_age_seconds:
                    continue
                os.remove(entry.path)
                removed += 1
            except FileNotFoundError:
                continue
            except Exception as exc:  # noqa: BLE001
                logger.warning("Unable to remove stale video temp file '%s': %s", entry.path, exc)
    except FileNotFoundError:
        return 0
    except Exception as exc:  # noqa: BLE001
        logger.warning("Unable to scan temp directory '%s' for stale video files: %s", temp_dir, exc)
        return 0

    if removed:
        logger.info("Removed %s stale OpenAI-compatible video temp file(s).", removed)
    return removed



def _get_pil_image_module():
    return importlib.import_module("PIL.Image")


def _extract_text_content(value: Any) -> str:
    if isinstance(value, str):
        return value

    if isinstance(value, list):
        parts = [_extract_text_content(item) for item in value]
        return "\n".join(part for part in parts if part).strip()

    if isinstance(value, dict):
        if "text" in value and isinstance(value["text"], str):
            return value["text"]
        if "content" in value:
            return _extract_text_content(value["content"])

    return ""


def _prepare_image_data_url(image_tensor: Any, max_dimension: int) -> str:
    if not hasattr(image_tensor, "shape"):
        raise OvertliVisionError("Invalid IMAGE tensor input", image_source="tensor")

    validate_comfy_image(image_tensor, name="image")

    pil_image = comfy_image_to_pil(image_tensor)
    width, height = pil_image.size
    pil_image_module = _get_pil_image_module()

    if max(width, height) > max_dimension:
        ratio = max_dimension / float(max(width, height))
        resized = (
            max(1, int(width * ratio)),
            max(1, int(height * ratio)),
        )
        pil_image = pil_image.resize(resized, pil_image_module.Resampling.LANCZOS)

    buffer = io.BytesIO()
    pil_image.save(buffer, format="JPEG", quality=90, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{encoded}"


def _prepare_image_data_urls(
    image_tensor: Any,
    max_dimension: int,
    batch_image_mode: str,
    max_batch_frames: int,
) -> list[str]:
    validate_comfy_image(image_tensor, name="image")

    if len(image_tensor.shape) == 4 and image_tensor.shape[0] > 1:
        indices = select_image_batch_indices(
            batch_size=image_tensor.shape[0],
            batch_image_mode=batch_image_mode,
            max_batch_frames=max_batch_frames,
        )
        return [_prepare_image_data_url(image_tensor[index : index + 1], max_dimension=max_dimension) for index in indices]

    return [_prepare_image_data_url(image_tensor, max_dimension=max_dimension)]


def _prepare_image_data_url_from_path(file_path: str, max_dimension: int) -> str:
    try:
        pil_image_module = _get_pil_image_module()

        with pil_image_module.open(file_path) as source:
            pil_image = source.convert("RGB")

        width, height = pil_image.size
        if max(width, height) > max_dimension:
            ratio = max_dimension / float(max(width, height))
            resized = (
                max(1, int(width * ratio)),
                max(1, int(height * ratio)),
            )
            pil_image = pil_image.resize(resized, pil_image_module.Resampling.LANCZOS)

        buffer = io.BytesIO()
        pil_image.save(buffer, format="JPEG", quality=90, optimize=True)
        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{encoded}"
    except FileNotFoundError as exc:
        raise OvertliVisionError(f"Image file not found: {file_path}", image_source="file_path") from exc
    except Exception as exc:  # noqa: BLE001
        raise OvertliVisionError(f"Failed to process image file: {exc}", image_source="file_path") from exc


class _OpenAICompatibleEngine(GZBaseNode):
    """Internal OpenAI-compatible multimodal engine used by GZ_AdvancedTextEnhancer."""

    @staticmethod
    def _write_stream_to_temp_audio(response: Any, requested_format: str) -> str:
        suffix = f".{requested_format}" if requested_format in {"mp3", "wav", "opus", "aac", "flac", "pcm"} else ".mp3"
        with tempfile.NamedTemporaryFile(prefix="overtli_openai_audio_", suffix=suffix, delete=False) as temp_file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    temp_file.write(chunk)
            return temp_file.name

    def _execute_selected_engine(
        self,
        *,
        selected_engine: str,
        resolved_model: str,
        resolved_base_url: str,
        headers: dict[str, str],
        timeout_seconds: int,
        temperature: float,
        max_tokens: int,
        styled_prompt: str,
        custom_instructions: str,
        media_width: int,
        media_height: int,
        image_data_urls: list[str],
        audio: Optional[Any],
        audio_response_format: str,
        audio_voice: str,
        audio_speed: float,
        stt_response_format: str,
        stt_language: str,
        blank_image: Any,
    ) -> Tuple[str, Any, Any, Any]:
        if selected_engine == "text":
            messages: list[dict[str, Any]] = []
            if custom_instructions.strip():
                messages.append({"role": "system", "content": custom_instructions.strip()})

            if image_data_urls:
                content: list[dict[str, Any]] = [{"type": "text", "text": styled_prompt}]
                for image_data_url in image_data_urls:
                    content.append({"type": "image_url", "image_url": {"url": image_data_url}})
                messages.append({"role": "user", "content": content})
            else:
                messages.append({"role": "user", "content": styled_prompt})

            payload: dict[str, Any] = {
                "model": resolved_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            endpoint = f"{resolved_base_url}/chat/completions"
            response = requests.post(endpoint, json=payload, headers=headers, timeout=timeout_seconds)
            response.raise_for_status()
            data = response.json()
            if "choices" in data and isinstance(data["choices"], list) and data["choices"]:
                content = data["choices"][0].get("message", {}).get("content", "")
                result = _extract_text_content(content)
            else:
                result = _extract_text_content(data.get("content", ""))
            result = sanitize_text_output(result or "", mode_hint="text").strip()
            if not result:
                raise OvertliAPIError("OpenAI-compatible provider returned an empty response", endpoint=endpoint)
            return (result, blank_image, None, None)

        if selected_engine == "image":
            payload = {
                "model": resolved_model,
                "prompt": styled_prompt,
                "size": f"{int(media_width)}x{int(media_height)}",
            }
            endpoint = f"{resolved_base_url}/images/generations"
            response = requests.post(endpoint, json=payload, headers=headers, timeout=timeout_seconds)
            response.raise_for_status()
            data = response.json()
            image_bytes: Optional[bytes] = None
            if isinstance(data, dict) and isinstance(data.get("data"), list) and data["data"]:
                first = data["data"][0]
                if isinstance(first, dict):
                    b64_payload = first.get("b64_json") or first.get("base64")
                    if isinstance(b64_payload, str) and b64_payload.strip():
                        image_bytes = base64.b64decode(b64_payload)
                    elif isinstance(first.get("url"), str) and first.get("url"):
                        image_fetch = requests.get(first["url"], timeout=timeout_seconds)
                        image_fetch.raise_for_status()
                        image_bytes = image_fetch.content

            if not image_bytes:
                raise OvertliAPIError(
                    "OpenAI-compatible image endpoint did not return image data.",
                    endpoint=endpoint,
                )
            return ("Image generated successfully.", binary_to_comfy_image(image_bytes), None, None)

        if selected_engine == "video":
            video_types_module = importlib.import_module("comfy_api.latest._input_impl.video_types")
            video_type = getattr(video_types_module, "VideoFromFile")

            payload = {
                "model": resolved_model,
                "prompt": styled_prompt,
                "width": int(media_width),
                "height": int(media_height),
                "size": f"{int(media_width)}x{int(media_height)}",
            }
            if image_data_urls:
                payload["image"] = image_data_urls[0]

            endpoint_candidates = [
                f"{resolved_base_url}/videos/generations",
                f"{resolved_base_url}/video/generations",
                f"{resolved_base_url}/videos",
            ]

            video_bytes: Optional[bytes] = None
            selected_endpoint = ""
            for endpoint in endpoint_candidates:
                response = requests.post(endpoint, json=payload, headers=headers, timeout=timeout_seconds)

                if response.status_code in {404, 405}:
                    logger.info(
                        "OpenAI-compatible video endpoint unavailable (status=%s): %s",
                        response.status_code,
                        endpoint,
                    )
                    continue

                response.raise_for_status()
                selected_endpoint = endpoint

                content_type = (response.headers.get("content-type") or "").lower()
                if "video" in content_type or "application/octet-stream" in content_type:
                    video_bytes = response.content
                else:
                    data = response.json()
                    video_url = ""
                    b64_payload = ""

                    if isinstance(data, dict):
                        if isinstance(data.get("data"), list) and data["data"]:
                            first = data["data"][0]
                            if isinstance(first, dict):
                                b64_payload = (
                                    first.get("b64_json")
                                    or first.get("base64")
                                    or first.get("video_base64")
                                    or ""
                                )
                                video_url = (
                                    first.get("url")
                                    or first.get("video_url")
                                    or first.get("href")
                                    or ""
                                )

                        if not video_url:
                            video_url = data.get("url") or data.get("video_url") or ""

                    if isinstance(b64_payload, str) and b64_payload.strip():
                        video_bytes = base64.b64decode(b64_payload)
                    elif isinstance(video_url, str) and video_url:
                        video_fetch = requests.get(video_url, timeout=timeout_seconds)
                        video_fetch.raise_for_status()
                        video_bytes = video_fetch.content

                if video_bytes:
                    break

            if not video_bytes:
                raise OvertliAPIError(
                    (
                        "OpenAI-compatible video request did not return usable video data. "
                        "Tried endpoints: " + ", ".join(endpoint_candidates)
                    ),
                    endpoint=selected_endpoint or resolved_base_url,
                )

            temp_dir = tempfile.gettempdir()
            os.makedirs(temp_dir, exist_ok=True)
            _cleanup_stale_video_temp_files(temp_dir)
            with tempfile.NamedTemporaryFile(prefix=_VIDEO_TEMP_PREFIX, suffix=".mp4", delete=False, dir=temp_dir) as tmp:
                tmp.write(video_bytes)
                video_path = tmp.name

            return ("Video generated successfully.", blank_image, video_type(video_path), None)

        if selected_engine in {"text_to_speech", "text_to_music"}:
            endpoint = f"{resolved_base_url}/audio/speech"
            payload = {
                "model": resolved_model,
                "input": styled_prompt,
                "response_format": audio_response_format,
                "speed": max(0.25, min(float(audio_speed), 4.0)),
            }
            if selected_engine == "text_to_speech":
                payload["voice"] = (audio_voice or "nova").strip() or "nova"
            else:
                payload["instrumental"] = True

            with requests.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=timeout_seconds,
                stream=True,
            ) as response:
                response.raise_for_status()
                temp_audio = self._write_stream_to_temp_audio(response, audio_response_format)

            try:
                from .pollinations.text_to_speech import _audio_path_to_output

                audio_output = _audio_path_to_output(temp_audio)
            finally:
                if os.path.exists(temp_audio):
                    os.remove(temp_audio)

            success_text = (
                "Speech generated successfully."
                if selected_engine == "text_to_speech"
                else "Music generated successfully."
            )
            return (success_text, blank_image, None, audio_output)

        if selected_engine == "speech_to_text":
            if audio is None:
                raise OvertliInputError(
                    "AUDIO input is required for speech_to_text engine.",
                    input_name="audio",
                )

            from .pollinations.speech_to_text import _write_audio_input_to_temp_wav

            temp_audio = _write_audio_input_to_temp_wav(audio)
            endpoint = f"{resolved_base_url}/audio/transcriptions"
            data_payload: dict[str, Any] = {
                "model": resolved_model,
                "response_format": stt_response_format,
                "temperature": max(0.0, min(float(temperature), 2.0)),
            }
            lang = (stt_language or "auto").strip().lower()
            if lang and lang != "auto":
                data_payload["language"] = lang
            if styled_prompt.strip():
                data_payload["prompt"] = styled_prompt.strip()

            try:
                with open(temp_audio, "rb") as handle:
                    files = {
                        "file": (
                            os.path.basename(temp_audio),
                            handle,
                            "audio/wav",
                        )
                    }
                    response = requests.post(
                        endpoint,
                        files=files,
                        data=data_payload,
                        headers={"Authorization": headers["Authorization"]} if "Authorization" in headers else None,
                        timeout=timeout_seconds,
                    )
                response.raise_for_status()
            finally:
                if os.path.exists(temp_audio):
                    os.remove(temp_audio)

            content_type = (response.headers.get("content-type") or "").lower()
            if "json" in content_type:
                payload = response.json()
                transcript = payload.get("text") if isinstance(payload, dict) else ""
                if not transcript:
                    transcript = str(payload)
            else:
                transcript = (response.text or "").strip()

            transcript = transcript.strip()
            if not transcript:
                raise OvertliAPIError(
                    "OpenAI-compatible STT returned an empty transcript.",
                    endpoint=endpoint,
                )
            return (transcript, blank_image, None, None)

        logger.error(
            "OpenAI-compatible engine selection invalid: '%s'",
            selected_engine,
        )
        raise OvertliInputError(
            f"Unsupported active_engine value: {selected_engine}",
            input_name="active_engine",
        )

    def execute(
        self,
        active_engine: str,
        mode_preset: str,
        prompt: str,
        model: str,
        image: Optional[Any] = None,
        file_path: str = "",
        audio: Optional[Any] = None,
        custom_instructions: str = "",
        style_preset_1: str = STYLE_OFF_LABEL,
        style_preset_2: str = STYLE_OFF_LABEL,
        style_preset_3: str = STYLE_OFF_LABEL,
        additional_styles: str = "",
        api_base_url: str = "",
        api_key: str = "",
        persist_api_settings: bool = True,
        temperature: float = 0.7,
        max_tokens: int = _DEFAULT_TEXT_MAX_TOKENS,
        timeout_seconds: int = 120,
        require_api_key: bool = True,
        max_image_dimension: int = 1280,
        vision_enabled: bool = True,
        batch_image_mode: str = "all_frames",
        max_batch_frames: int = 0,
        media_width: int = 1024,
        media_height: int = 1024,
        audio_voice: str = "nova",
        audio_speed: float = 1.0,
        audio_response_format: str = "mp3",
        stt_response_format: str = "text",
        stt_language: str = "auto",
    ) -> Tuple[str, Any, Any, Any]:
        cfg = get_config().openai_compatible

        runtime_base_url = normalize_string_input(api_base_url)
        runtime_api_key = normalize_string_input(api_key)
        runtime_model = normalize_string_input(model)
        selected_engine = (active_engine or "text").strip().lower()

        if persist_api_settings:
            updates: dict[str, str] = {}
            if runtime_base_url:
                updates["openai_compatible_base_url"] = runtime_base_url
            if runtime_api_key:
                updates["openai_compatible_api_key"] = runtime_api_key
            if runtime_model:
                updates["openai_compatible_model"] = runtime_model
            if updates:
                save_persistent_settings(updates, source="GZ_AdvancedTextEnhancer")

        resolved_base_url = resolve_config_value(
            "openai_compatible_base_url",
            runtime_base_url,
            default=cfg.base_url,
        ).rstrip("/")

        resolved_api_key = resolve_config_value(
            "openai_compatible_api_key",
            runtime_api_key,
            default=cfg.api_key or "",
        )

        resolved_model = normalize_string_input(
            resolve_config_value(
                "openai_compatible_model",
                runtime_model,
                default=cfg.default_model,
            )
        )

        if not resolved_model:
            raise OvertliConfigError(
                "OpenAI-compatible model is required for this node.",
                config_key="OPENAI_COMPAT_MODEL",
            )

        if require_api_key and not resolved_api_key:
            raise OvertliConfigError(
                "OpenAI-compatible API key is required but not provided",
                config_key="OPENAI_COMPAT_API_KEY",
            )

        timeout_seconds = self.clamp_timeout(timeout_seconds)
        headers = {"Content-Type": "application/json"}
        if resolved_api_key:
            headers["Authorization"] = f"Bearer {resolved_api_key}"

        source_type, source_value = validate_single_image_source(image_tensor=image, file_path=file_path)
        image_data_urls: list[str] = []
        if source_type != "none" and not vision_enabled:
            logger.info("Vision disabled; ignoring image context for OpenAI-compatible request.")
        elif source_type == "file":
            resolved_path = os.path.abspath(str(source_value))
            if not os.path.exists(resolved_path):
                raise OvertliInputError(
                    f"Provided file_path does not exist: {resolved_path}",
                    input_name="file_path",
                )
            image_data_urls = [
                _prepare_image_data_url_from_path(
                    resolved_path,
                    max_dimension=max_image_dimension,
                )
            ]
        elif source_type == "tensor":
            image_data_urls = _prepare_image_data_urls(
                image_tensor=image,
                max_dimension=max_image_dimension,
                batch_image_mode=batch_image_mode,
                max_batch_frames=max_batch_frames,
            )

        mode_category_map = {
            "text": "text",
            "image": "image",
            "video": "video",
            "text_to_speech": "tts",
            "speech_to_text": "speech_to_text",
            "text_to_music": "text_to_audio",
        }
        mode_category = mode_category_map.get(selected_engine, "text")

        # Keep grouped mode-family resolution path active for parity with other providers.
        _ = resolve_mode_family_preset(
            text_mode_enabled=mode_category == "text",
            text_mode=mode_preset,
            image_mode_enabled=mode_category == "image",
            image_mode=mode_preset,
            video_mode_enabled=mode_category == "video",
            video_mode=mode_preset,
            tts_mode_enabled=mode_category == "tts",
            tts_mode=mode_preset,
        )

        style_labels = normalize_style_presets(
            style_preset_1=style_preset_1,
            style_preset_2=style_preset_2,
            style_preset_3=style_preset_3,
        )

        user_prompt = normalize_string_input(prompt)
        if selected_engine == "text" and not user_prompt and image_data_urls:
            user_prompt = "Describe and analyze this image in detail."

        if selected_engine in {"text", "image", "text_to_speech", "text_to_music"}:
            user_prompt = self.require_prompt(user_prompt, input_name="prompt")

        mode_hint = infer_mode_category(mode_preset=mode_preset, fallback=mode_category)
        styled_prompt = append_style_layers_to_prompt(
            raw_prompt=user_prompt,
            style_labels=style_labels,
            mode_category=mode_hint,
            additional_styles=additional_styles,
        )

        blank_image = _empty_image()

        try:
            return self._execute_selected_engine(
                selected_engine=selected_engine,
                resolved_model=resolved_model,
                resolved_base_url=resolved_base_url,
                headers=headers,
                timeout_seconds=timeout_seconds,
                temperature=temperature,
                max_tokens=max_tokens,
                styled_prompt=styled_prompt,
                custom_instructions=custom_instructions,
                media_width=media_width,
                media_height=media_height,
                image_data_urls=image_data_urls,
                audio=audio,
                audio_response_format=audio_response_format,
                audio_voice=audio_voice,
                audio_speed=audio_speed,
                stt_response_format=stt_response_format,
                stt_language=stt_language,
                blank_image=blank_image,
            )

        except requests.exceptions.Timeout as exc:
            timeout_message = build_user_facing_error(
                "OpenAI-compatible request timed out.",
                what_happened=f"No response was received within {timeout_seconds} seconds.",
                what_we_tried=(
                    f"Sent '{selected_engine}' request to {resolved_base_url} with model '{resolved_model}'."
                ),
                next_steps=(
                    "Increase timeout_seconds, reduce payload size, verify provider status, "
                    "or test the same endpoint with curl/Postman."
                ),
            )
            logger.error(timeout_message)
            raise OvertliTimeoutError(
                timeout_message,
                timeout_seconds=timeout_seconds,
                operation=f"openai-compatible {selected_engine}",
            ) from exc
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            body = exc.response.text[:300] if exc.response is not None else str(exc)
            api_error_message = build_user_facing_error(
                "OpenAI-compatible API request failed.",
                what_happened=f"Provider returned HTTP {status}.",
                what_we_tried=(
                    f"Called OpenAI-compatible endpoint for engine '{selected_engine}' with model '{resolved_model}'."
                ),
                next_steps=(
                    "Check API key permissions, model availability, rate limits, and request body format."
                ),
                details=f"Response excerpt: {body}",
            )
            logger.error(api_error_message)
            raise OvertliAPIError(
                api_error_message,
                endpoint=resolved_base_url,
                status_code=status,
            ) from exc
        except OvertliInputError:
            raise
        except OvertliVisionError:
            raise
        except OvertliConfigError:
            raise
        except OvertliAPIError:
            raise
        except Exception as exc:  # noqa: BLE001
            fallback_message = build_user_facing_error(
                "OpenAI-compatible request failed.",
                what_happened=f"Unexpected error: {exc}",
                what_we_tried=f"Provider call attempted via base URL {resolved_base_url}.",
                next_steps="Review terminal logs and verify endpoint compatibility.",
            )
            logger.exception("OpenAI-compatible unexpected error")
            raise OvertliAPIError(fallback_message, endpoint=resolved_base_url) from exc

