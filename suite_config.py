"""
OVERTLI STUDIO LLM Suite - Configuration Management

Centralized configuration with environment variable support.
All settings can be overridden via environment variables prefixed with GZ_.
"""

import os
from dataclasses import dataclass, field
from typing import Any, Optional

from .settings_store import resolve_config_value


def _normalize_base_url(url: str, known_suffixes: tuple[str, ...]) -> str:
    """Normalize a service base URL by removing known endpoint suffixes."""
    normalized = (url or "").strip().rstrip("/")
    lower = normalized.lower()
    for suffix in known_suffixes:
        suffix_lower = suffix.lower()
        if lower.endswith(suffix_lower):
            normalized = normalized[: -len(suffix)]
            lower = normalized.lower()
            break
    return normalized.rstrip("/")


@dataclass
class PollinationsConfig:
    """Pollinations.ai API configuration."""
    # Primary API endpoint (OpenAI-compatible)
    api_base_url: str = "https://gen.pollinations.ai"
    # Canonical API endpoint base
    gen_base_url: str = "https://gen.pollinations.ai"
    # Media endpoint bases
    image_base_url: str = "https://gen.pollinations.ai/image"
    video_base_url: str = "https://gen.pollinations.ai/video"
    audio_base_url: str = "https://gen.pollinations.ai/audio"
    # Optional API key for paid tier (higher rate limits)
    api_key: Optional[str] = None
    # Default timeout for text chat/completions (seconds)
    chat_timeout: int = 60
    # Default timeout for image generation (seconds)
    image_timeout: int = 60
    # Video generation is synchronous and slow
    video_timeout: int = 120
    # TTS timeout
    tts_timeout: int = 60
    # Speech-to-text timeout
    stt_timeout: int = 120
    # Text-to-audio generation timeout
    audio_generation_timeout: int = 120

    @property
    def chat_endpoint(self) -> str:
        return f"{self.gen_base_url}/v1/chat/completions"

    @property
    def models_endpoint(self) -> str:
        return f"{self.gen_base_url}/v1/models"

    @property
    def image_endpoint(self) -> str:
        return self.image_base_url.rstrip("/")

    @property
    def video_endpoint(self) -> str:
        return self.video_base_url.rstrip("/")

    @property
    def audio_endpoint(self) -> str:
        return self.audio_base_url.rstrip("/")

    @property
    def audio_models_endpoint(self) -> str:
        return f"{self.audio_base_url.rstrip('/')}/models"

    @property
    def audio_speech_endpoint(self) -> str:
        return f"{self.gen_base_url}/v1/audio/speech"

    @property
    def audio_transcriptions_endpoint(self) -> str:
        return f"{self.gen_base_url}/v1/audio/transcriptions"


@dataclass
class LMStudioConfig:
    """LM Studio local API configuration."""
    host: str = "localhost"
    port: int = 1234
    base_url_override: str = ""
    api_key: Optional[str] = None
    # Constructed base URL
    base_url: str = field(init=False)
    # Auto-unload model after inference
    auto_unload: bool = False
    # Request timeout
    timeout: int = 120

    def __post_init__(self):
        override = (self.base_url_override or "").strip()
        if override:
            self.base_url = _normalize_base_url(
                override,
                (
                    "/v1/chat/completions",
                    "/v1/models",
                    "/api/v1/chat",
                    "/api/v0/models",
                    "/api/v1/models/unload",
                    "/v1",
                ),
            )
        else:
            self.base_url = f"http://{self.host}:{self.port}"

    @property
    def chat_endpoint(self) -> str:
        return f"{self.base_url}/v1/chat/completions"

    @property
    def vision_endpoint(self) -> str:
        return f"{self.base_url}/api/v1/chat"

    @property
    def models_endpoint(self) -> str:
        return f"{self.base_url}/api/v0/models"

    @property
    def unload_endpoint(self) -> str:
        return f"{self.base_url}/api/v1/models/unload"


@dataclass
class CopilotConfig:
    """GitHub Copilot CLI configuration."""
    # Path to copilot CLI executable
    executable: str = "copilot"
    # Default model slug
    default_model: str = "gpt-4.1"
    # Silent mode by default
    silent: bool = True
    # No interactive prompts
    no_ask_user: bool = True
    # Request timeout
    timeout: int = 120


@dataclass
class OpenAICompatibleConfig:
    """OpenAI-compatible provider configuration."""

    base_url: str = "https://api.openai.com/v1"
    api_key: Optional[str] = None
    default_model: str = "gpt-4.1-mini"
    timeout: int = 120
    require_api_key: bool = True

    def __post_init__(self):
        self.base_url = _normalize_base_url(
            self.base_url,
            (
                "/chat/completions",
            ),
        )

    @property
    def chat_endpoint(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"


@dataclass
class SuiteConfig:
    """Master configuration for the OVERTLI STUDIO LLM Suite."""
    pollinations: PollinationsConfig = field(default_factory=PollinationsConfig)
    lm_studio: LMStudioConfig = field(default_factory=LMStudioConfig)
    copilot: CopilotConfig = field(default_factory=CopilotConfig)
    openai_compatible: OpenAICompatibleConfig = field(default_factory=OpenAICompatibleConfig)

    # Global settings
    debug_mode: bool = False
    log_level: str = "INFO"
    temp_dir: Optional[str] = None  # For temporary files (images, etc.)

    def __post_init__(self):
        # Set temp dir to ComfyUI temp if not specified
        if self.temp_dir is None:
            try:
                import folder_paths
                self.temp_dir = folder_paths.get_temp_directory()
            except ImportError:
                import tempfile
                self.temp_dir = tempfile.gettempdir()


def _get_env(key: str, default: Any = None, cast: type = str) -> Any:
    """Get environment variable with type casting."""
    value = os.environ.get(f"GZ_{key}", default)
    if value is None:
        return default
    if cast == bool:
        return str(value).lower() in ("true", "1", "yes", "on")
    if cast == int:
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    return cast(value)


def load_config() -> SuiteConfig:
    """
    Load configuration from environment variables.

    Environment variables (all prefixed with GZ_):
        GZ_POLLINATIONS_API_KEY - Optional Pollinations API key
        GZ_POLLINATIONS_CHAT_TIMEOUT - Chat completion timeout
        GZ_POLLINATIONS_IMAGE_TIMEOUT - Image generation timeout
        GZ_POLLINATIONS_VIDEO_TIMEOUT - Video generation timeout
        GZ_POLLINATIONS_TTS_TIMEOUT - Text-to-speech timeout
        GZ_POLLINATIONS_STT_TIMEOUT - Speech-to-text timeout
        GZ_POLLINATIONS_AUDIO_TIMEOUT - Text-to-audio generation timeout
        GZ_LMSTUDIO_HOST - LM Studio host (default: localhost)
        GZ_LMSTUDIO_PORT - LM Studio port (default: 1234)
        GZ_LMSTUDIO_API_KEY - Optional LM Studio API key
        GZ_LMSTUDIO_AUTO_UNLOAD - Auto-unload after inference
        GZ_COPILOT_EXECUTABLE - Path to copilot CLI
        GZ_COPILOT_MODEL - Default model slug
        GZ_DEBUG - Enable debug mode
        GZ_LOG_LEVEL - Logging level
        GZ_TEMP_DIR - Temporary directory path
    """
    pollinations = PollinationsConfig(
        api_key=resolve_config_value("pollinations_api_key"),
        chat_timeout=_get_env("POLLINATIONS_CHAT_TIMEOUT", 60, int),
        image_timeout=_get_env("POLLINATIONS_IMAGE_TIMEOUT", 60, int),
        video_timeout=_get_env("POLLINATIONS_VIDEO_TIMEOUT", 120, int),
        tts_timeout=_get_env("POLLINATIONS_TTS_TIMEOUT", 60, int),
        stt_timeout=_get_env("POLLINATIONS_STT_TIMEOUT", 120, int),
        audio_generation_timeout=_get_env("POLLINATIONS_AUDIO_TIMEOUT", 120, int),
    )

    lm_studio = LMStudioConfig(
        host=_get_env("LMSTUDIO_HOST", "localhost"),
        port=_get_env("LMSTUDIO_PORT", 1234, int),
        base_url_override=resolve_config_value("lmstudio_base_url"),
        api_key=resolve_config_value("lmstudio_api_key"),
        auto_unload=_get_env("LMSTUDIO_AUTO_UNLOAD", False, bool),
        timeout=_get_env("LMSTUDIO_TIMEOUT", 120, int),
    )

    copilot = CopilotConfig(
        executable=resolve_config_value("copilot_executable", default="copilot"),
        default_model=resolve_config_value("copilot_model", default="gpt-5.3-codex"),
        timeout=_get_env("COPILOT_TIMEOUT", 120, int),
    )

    openai_compatible = OpenAICompatibleConfig(
        base_url=resolve_config_value("openai_compatible_base_url", default="https://api.openai.com/v1"),
        api_key=resolve_config_value("openai_compatible_api_key"),
        default_model=resolve_config_value("openai_compatible_model", default="gpt-4.1-mini"),
        timeout=_get_env("OPENAI_COMPAT_TIMEOUT", 120, int),
        require_api_key=_get_env("OPENAI_COMPAT_REQUIRE_API_KEY", True, bool),
    )

    return SuiteConfig(
        pollinations=pollinations,
        lm_studio=lm_studio,
        copilot=copilot,
        openai_compatible=openai_compatible,
        debug_mode=_get_env("DEBUG", False, bool),
        log_level=_get_env("LOG_LEVEL", "INFO"),
        temp_dir=_get_env("TEMP_DIR"),
    )


# ============================================================================
# SINGLETON CONFIG INSTANCE
# ============================================================================

_config: Optional[SuiteConfig] = None


def get_config() -> SuiteConfig:
    """Get the singleton configuration instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config() -> SuiteConfig:
    """Force reload configuration from environment."""
    global _config
    _config = load_config()
    return _config


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "PollinationsConfig",
    "LMStudioConfig",
    "CopilotConfig",
    "OpenAICompatibleConfig",
    "SuiteConfig",
    "get_config",
    "reload_config",
    "load_config",
]
