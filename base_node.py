"""
OVERTLI STUDIO LLM Suite - Base Node

Shared validation helpers for OVERTLI nodes.
"""

from __future__ import annotations

from .exceptions import OvertliInputError


class GZBaseNode:
    """Common validation helpers for node inputs."""

    @staticmethod
    def require_prompt(prompt: str, input_name: str = "prompt") -> str:
        """Return normalized prompt text or raise if empty."""
        value = (prompt or "").strip()
        if not value:
            raise OvertliInputError("Prompt cannot be empty", input_name=input_name)
        return value

    @staticmethod
    def clamp_timeout(timeout_seconds: int, minimum: int = 1, maximum: int = 1200) -> int:
        """Clamp timeout to a safe range for external calls."""
        if timeout_seconds < minimum:
            return minimum
        if timeout_seconds > maximum:
            return maximum
        return timeout_seconds


__all__ = ["GZBaseNode"]
