"""
OVERTLI STUDIO LLM Suite - Exception Hierarchy

All custom exceptions for the suite. Provides granular error handling
with descriptive messages and optional context data.
"""


class OvertliSuiteError(Exception):
    """Base exception for all OVERTLI STUDIO LLM Suite errors."""
    
    def __init__(self, message: str, context: dict[str, object] | None = None):
        super().__init__(message)
        self.message = message
        self.context = context or {}
    
    def __str__(self):
        if self.context:
            ctx = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} [{ctx}]"
        return self.message


class OvertliAPIError(OvertliSuiteError):
    """Network, authentication, or API transport failures."""
    
    def __init__(
        self,
        message: str,
        endpoint: str | None = None,
        status_code: int | None = None,
        **kwargs,
    ):
        context = kwargs.pop("context", {})
        if endpoint:
            context["endpoint"] = endpoint
        if status_code:
            context["status_code"] = status_code
        super().__init__(message, context)
        self.endpoint = endpoint
        self.status_code = status_code


class OvertliVisionError(OvertliSuiteError):
    """Image processing and vision pipeline failures."""
    
    def __init__(self, message: str, image_source: str | None = None, **kwargs):
        context = kwargs.pop("context", {})
        if image_source:
            context["image_source"] = image_source
        super().__init__(message, context)
        self.image_source = image_source


class OvertliConfigError(OvertliSuiteError):
    """Missing or invalid configuration, API keys, or environment setup."""
    
    def __init__(self, message: str, config_key: str | None = None, **kwargs):
        context = kwargs.pop("context", {})
        if config_key:
            context["config_key"] = config_key
        super().__init__(message, context)
        self.config_key = config_key


class OvertliInputError(OvertliSuiteError):
    """Invalid or conflicting user inputs."""
    
    def __init__(self, message: str, input_name: str | None = None, **kwargs):
        context = kwargs.pop("context", {})
        if input_name:
            context["input_name"] = input_name
        super().__init__(message, context)
        self.input_name = input_name


class OvertliTimeoutError(OvertliSuiteError):
    """Operation timed out (video generation, long API calls)."""
    
    def __init__(
        self,
        message: str,
        timeout_seconds: float | None = None,
        operation: str | None = None,
        **kwargs,
    ):
        context = kwargs.pop("context", {})
        if timeout_seconds:
            context["timeout_seconds"] = timeout_seconds
        if operation:
            context["operation"] = operation
        super().__init__(message, context)
        self.timeout_seconds = timeout_seconds
        self.operation = operation


class OvertliModelError(OvertliSuiteError):
    """Model-related errors (unavailable, incompatible, not loaded)."""
    
    def __init__(self, message: str, model_name: str | None = None, **kwargs):
        context = kwargs.pop("context", {})
        if model_name:
            context["model_name"] = model_name
        super().__init__(message, context)
        self.model_name = model_name


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "OvertliSuiteError",
    "OvertliAPIError",
    "OvertliVisionError",
    "OvertliConfigError",
    "OvertliInputError",
    "OvertliTimeoutError",
    "OvertliModelError",
]
