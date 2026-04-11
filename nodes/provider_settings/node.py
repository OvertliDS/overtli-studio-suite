# ============================================================================
# provider_settings.py
# GZ_ProviderSettings - Persistent settings helper node
# ============================================================================
"""
GZ_ProviderSettings
===================
Utility node to persist provider defaults (API keys, URLs, models, executables)
in one place. Values are stored in user/overtli_studio_settings.json.
This is explicit local persistence, not OS-backed secret-vault storage.
"""

from __future__ import annotations

from typing import Any, Dict

from ...settings_store import format_setting_updates, get_settings_path, save_persistent_settings


class GZ_ProviderSettings:
    """Persist shared provider settings for OVERTLI STUDIO nodes."""

    CATEGORY = "OVERTLI STUDIO/System"
    FUNCTION = "execute"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("settings_status",)
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "apply_settings": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "label_on": "Apply",
                        "label_off": "Preview",
                    },
                ),
            },
            "optional": {
                "pollinations_api_key": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "placeholder": "Pollinations API key",
                    },
                ),
                "lmstudio_base_url": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "placeholder": "LM Studio base URL (e.g. http://localhost:1234)",
                    },
                ),
                "lmstudio_api_key": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "placeholder": "Optional LM Studio API key",
                    },
                ),
                "openai_compatible_api_key": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "placeholder": "OpenAI-compatible API key",
                    },
                ),
                "openai_compatible_base_url": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "placeholder": "OpenAI-compatible base URL",
                    },
                ),
                "openai_compatible_model": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "placeholder": "OpenAI-compatible default model",
                    },
                ),
                "copilot_executable": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "placeholder": "Copilot executable (copilot, copilot.cmd, path)",
                    },
                ),
                "copilot_model": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "placeholder": "Copilot default model",
                    },
                ),
            },
        }

    def execute(
        self,
        apply_settings: bool,
        pollinations_api_key: str = "",
        lmstudio_base_url: str = "",
        lmstudio_api_key: str = "",
        openai_compatible_api_key: str = "",
        openai_compatible_base_url: str = "",
        openai_compatible_model: str = "",
        copilot_executable: str = "",
        copilot_model: str = "",
    ) -> Any:
        updates: Dict[str, Any] = {
            "pollinations_api_key": pollinations_api_key,
            "lmstudio_base_url": lmstudio_base_url,
            "lmstudio_api_key": lmstudio_api_key,
            "openai_compatible_api_key": openai_compatible_api_key,
            "openai_compatible_base_url": openai_compatible_base_url,
            "openai_compatible_model": openai_compatible_model,
            "copilot_executable": copilot_executable,
            "copilot_model": copilot_model,
        }

        preview_text = format_setting_updates(updates)
        secret_keys_present = any("key" in key and value for key, value in updates.items())

        if not preview_text:
            message = "No settings provided. Nothing to update."
            return {"ui": {"text": [message]}, "result": (message,)}

        destination = get_settings_path()
        persistence_notice = ""
        if secret_keys_present:
            persistence_notice = (
                " Secret values are stored locally in overtli_studio_settings.json; "
                "prefer environment variables when you do not want disk persistence."
            )

        if apply_settings:
            save_persistent_settings(updates, source="GZ_ProviderSettings")
            message = f"Saved settings to {destination}: {preview_text}{persistence_notice}"
            return {"ui": {"text": [message]}, "result": (message,)}

        message = f"Preview only (not saved to {destination}): {preview_text}{persistence_notice}"
        return {"ui": {"text": [message]}, "result": (message,)}
