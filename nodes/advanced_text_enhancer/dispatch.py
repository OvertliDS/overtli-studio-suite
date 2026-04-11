from __future__ import annotations

import logging
from typing import Any, Callable, Tuple

from ...suite_config import get_config
from ...engine.openai_compatible import _empty_image
from .constants import _PROVIDER_OPTIONS

logger = logging.getLogger(__name__)


def dispatch_provider_route(
    *,
    provider_name: str,
    family: str,
    prompt: str,
    resolved_mode: str,
    text_mode: str,
    image_mode: str,
    video_mode: str,
    tts_mode: str,
    stt_mode: str,
    ttaudio_mode: str,
    pollinations_model: str,
    lm_studio_model: str,
    copilot_model: str,
    openai_model_override: str,
    image: Any,
    audio: Any,
    vision_enabled: bool,
    batch_image_mode: str,
    max_batch_frames: int,
    custom_instructions: str,
    style_preset_1: str,
    style_preset_2: str,
    style_preset_3: str,
    additional_styles: str,
    resolved_tts_style: str,
    resolved_stt_style: str,
    resolved_ttaudio_style: str,
    temperature: float,
    effective_text_max_tokens: int,
    timeout_seconds: int,
    seed: int,
    output_format: str,
    media_width: int,
    media_height: int,
    safe_mode: bool,
    no_logo: bool,
    enhance_media_prompt: bool,
    stt_response_format: str,
    stt_language: str,
    audio_response_format: str,
    audio_voice: str,
    audio_speed: float,
    audio_duration: int,
    audio_instrumental: bool,
    api_key: str,
    api_base_url: str,
    copilot_executable: str,
    persist_provider_settings: bool,
    selected_pollinations_model: Callable[[str, str], str],
    validate_pollinations_model_family: Callable[[str, str], None],
) -> Tuple[str, Any, Any, Any]:
    blank_image = _empty_image()

    if provider_name == "pollinations":
        selected_model = selected_pollinations_model(family, pollinations_model)
        validate_pollinations_model_family(selected_model, family)

        if family == "text":
            from ..pollinations.text_enhancer.node import GZ_TextEnhancer

            response = GZ_TextEnhancer().execute(
                prompt=prompt,
                text_mode_enabled=True,
                text_mode=resolved_mode if resolved_mode != "Off" else "Off",
                image_mode_enabled=False,
                image_mode="Off",
                video_mode_enabled=False,
                video_mode="Off",
                tts_mode_enabled=False,
                tts_mode="Off",
                model=selected_model,
                image=image,
                vision_enabled=vision_enabled,
                batch_image_mode=batch_image_mode,
                max_batch_frames=max_batch_frames,
                custom_instructions=custom_instructions,
                style_preset_1=style_preset_1,
                style_preset_2=style_preset_2,
                style_preset_3=style_preset_3,
                additional_styles=additional_styles,
                temperature=temperature,
                max_tokens=effective_text_max_tokens,
                seed=seed,
                api_key=api_key,
                persist_api_key=persist_provider_settings,
            )[0]
            return (response, blank_image, None, None)

        if family == "image":
            from ..pollinations.image_gen.node import GZ_ImageGen

            image_output = GZ_ImageGen().execute(
                prompt=prompt,
                mode_preset=resolved_mode,
                model=selected_model,
                width=media_width,
                height=media_height,
                image=image,
                custom_instructions=custom_instructions,
                style_preset_1=style_preset_1,
                style_preset_2=style_preset_2,
                style_preset_3=style_preset_3,
                additional_styles=additional_styles,
                enhance_prompt=enhance_media_prompt,
                seed=seed,
                safe_mode=safe_mode,
                no_logo=no_logo,
                api_key=api_key,
                persist_api_key=persist_provider_settings,
            )[0]
            return ("Image generated successfully.", image_output, None, None)

        if family == "video":
            from ..pollinations.video_gen.node import GZ_VideoGen

            video_output = GZ_VideoGen().execute(
                prompt=prompt,
                mode_preset=resolved_mode,
                model=selected_model,
                image=image,
                custom_instructions=custom_instructions,
                style_preset_1=style_preset_1,
                style_preset_2=style_preset_2,
                style_preset_3=style_preset_3,
                additional_styles=additional_styles,
                enhance_prompt=enhance_media_prompt,
                width=media_width,
                height=media_height,
                seed=seed,
                timeout_seconds=timeout_seconds,
                api_key=api_key,
                persist_api_key=persist_provider_settings,
            )[0]
            return ("Video generated successfully.", blank_image, video_output, None)

        if family == "stt":
            from ..pollinations.speech_to_text.node import GZ_SpeechToText

            transcript = GZ_SpeechToText().execute(
                model=selected_model,
                mode_preset=resolved_mode,
                response_format=stt_response_format,
                audio=audio,
                input_language=stt_language,
                prompt=prompt,
                stt_style_preset=resolved_stt_style,
                temperature=0.5,
                api_key=api_key,
                persist_api_key=persist_provider_settings,
            )[0]
            return (transcript, blank_image, None, None)

        if family == "tts":
            from ..pollinations.text_to_speech.node import GZ_TextToSpeech

            audio_output = GZ_TextToSpeech().execute(
                text=prompt,
                mode_preset=resolved_mode,
                model=selected_model,
                voice=audio_voice,
                custom_instructions=custom_instructions,
                tts_style_preset=resolved_tts_style,
                format_script=enhance_media_prompt,
                api_key=api_key,
                persist_api_key=persist_provider_settings,
            )[0]
            return ("TTS audio generated.", blank_image, None, audio_output)

        if family == "ttaudio":
            from ..pollinations.text_to_audio.node import GZ_TextToAudio

            audio_output = GZ_TextToAudio().execute(
                text=prompt,
                mode_preset=resolved_mode,
                model=selected_model,
                response_format=audio_response_format,
                music_style_preset=resolved_ttaudio_style,
                speed=audio_speed,
                duration=audio_duration,
                instrumental=audio_instrumental,
                custom_instructions=custom_instructions,
                api_key=api_key,
                persist_api_key=persist_provider_settings,
            )[0]
            return ("Music generated.", blank_image, None, audio_output)

    if provider_name == "lm_studio":
        from ..llm_text_enhancer.node import GZ_LLMTextEnhancer

        selected_model = (lm_studio_model or "auto [local]").strip()
        response = GZ_LLMTextEnhancer().execute(
            provider="LM Studio",
            prompt=prompt,
            text_mode_enabled=True,
            text_mode=resolved_mode if resolved_mode != "Off" else "Off",
            image_mode_enabled=False,
            image_mode="Off",
            video_mode_enabled=False,
            video_mode="Off",
            tts_mode_enabled=False,
            tts_mode="Off",
            model=selected_model,
            image=image,
            vision_enabled=vision_enabled,
            batch_image_mode=batch_image_mode,
            max_batch_frames=max_batch_frames,
            custom_instructions=custom_instructions,
            style_preset_1=style_preset_1,
            style_preset_2=style_preset_2,
            style_preset_3=style_preset_3,
            additional_styles=additional_styles,
            temperature=temperature,
            max_tokens=effective_text_max_tokens,
            timeout_seconds=timeout_seconds,
            api_base_url=api_base_url,
            api_key=api_key,
            persist_api_key=persist_provider_settings,
        )[0]
        return (response, blank_image, None, None)

    if provider_name == "copilot":
        from ..copilot_agent.node import GZ_CopilotAgent

        selected_model = (copilot_model or get_config().copilot.default_model).strip()
        response = GZ_CopilotAgent().execute(
            prompt=prompt,
            text_mode_enabled=True,
            text_mode=resolved_mode if resolved_mode != "Off" else "Off",
            image_mode_enabled=False,
            image_mode="Off",
            video_mode_enabled=False,
            video_mode="Off",
            tts_mode_enabled=False,
            tts_mode="Off",
            model=selected_model,
            image=image,
            copilot_executable=copilot_executable,
            persist_copilot_executable=persist_provider_settings,
            persist_selected_model=persist_provider_settings,
            custom_instructions=custom_instructions,
            style_preset_1=style_preset_1,
            style_preset_2=style_preset_2,
            style_preset_3=style_preset_3,
            additional_styles=additional_styles,
            vision_enabled=vision_enabled,
            batch_image_mode=batch_image_mode,
            max_batch_frames=max_batch_frames,
            max_output_tokens=effective_text_max_tokens,
            output_format=output_format,
            timeout_seconds=timeout_seconds,
        )[0]
        return (response, blank_image, None, None)

    if provider_name == "openai_compatible":
        from ..openai_compatible_text_enhancer.node import GZ_OpenAICompatibleTextEnhancer

        selected_model = (openai_model_override or get_config().openai_compatible.default_model).strip()
        family_to_engine = {
            "text": "text",
            "image": "image_gen",
            "video": "video_gen",
            "tts": "text_to_speech_gen",
            "stt": "speech_to_text_gen",
            "ttaudio": "text_to_music_gen",
        }
        engine = family_to_engine.get(family, "text")
        response_text, response_image, response_video, response_audio = GZ_OpenAICompatibleTextEnhancer().execute(
            active_engine=engine,
            prompt=prompt,
            model=selected_model,
            text_mode=text_mode,
            image_mode=image_mode,
            video_mode=video_mode,
            tts_mode=tts_mode,
            stt_mode=stt_mode,
            ttaudio_mode=ttaudio_mode,
            image=image,
            audio=audio,
            vision_enabled=vision_enabled,
            batch_image_mode=batch_image_mode,
            max_batch_frames=max_batch_frames,
            custom_instructions=custom_instructions,
            style_preset_1=style_preset_1,
            style_preset_2=style_preset_2,
            style_preset_3=style_preset_3,
            additional_styles=additional_styles,
            api_base_url=api_base_url,
            api_key=api_key,
            persist_api_settings=persist_provider_settings,
            temperature=temperature,
            max_tokens=effective_text_max_tokens,
            timeout_seconds=timeout_seconds,
            media_width=media_width,
            media_height=media_height,
            audio_voice=audio_voice,
            audio_speed=audio_speed,
            audio_response_format=audio_response_format,
            stt_response_format=stt_response_format,
            stt_language=stt_language,
        )
        return (response_text, response_image, response_video, response_audio)

    raise ValueError(f"Unsupported provider '{provider_name}'. Expected one of: {', '.join(_PROVIDER_OPTIONS)}")

