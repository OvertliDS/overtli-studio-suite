import pathlib
import unittest


def _resolve_node_root() -> pathlib.Path:
    # Support both direct repository checkouts and custom_nodes packaging layouts.
    direct_root = pathlib.Path(__file__).resolve().parents[2]
    nested_root = direct_root / "custom_nodes" / "overtli-studio-suite"
    if nested_root.exists():
        return nested_root
    return direct_root


class TestSmokeCompile(unittest.TestCase):
    def test_python_files_compile(self):
        node_root = _resolve_node_root()

        files = [
            node_root / "__init__.py",
            node_root / "shared_utils.py",
            node_root / "suite_config.py",
            node_root / "settings_store.py",
            node_root / "exceptions.py",
            node_root / "image_utils.py",
            node_root / "copilot_agent.py",
            node_root / "lm_studio_vision.py",
            node_root / "advanced_text_enhancer.py",
            node_root / "audio_style_presets.py",
            node_root / "provider_settings.py",
            node_root / "prompt_styles.py",
            node_root / "prompt_library_store.py",
            node_root / "prompt_library_node.py",
            node_root / "style_stack_node.py",
            node_root / "pollinations" / "text_enhancer.py",
            node_root / "pollinations" / "model_catalog.py",
            node_root / "pollinations" / "image_gen.py",
            node_root / "pollinations" / "video_gen.py",
            node_root / "pollinations" / "text_to_speech.py",
            node_root / "pollinations" / "speech_to_text.py",
            node_root / "pollinations" / "text_to_audio.py",
            node_root / "pollinations" / "compat_retry.py",
            node_root / "pollinations" / "media_upload.py",
            node_root / "instruction_modes" / "__init__.py",
            node_root / "instruction_modes" / "text_modes.py",
            node_root / "instruction_modes" / "image_modes.py",
            node_root / "instruction_modes" / "video_modes.py",
            node_root / "instruction_modes" / "tts_modes.py",
            node_root / "instruction_modes" / "system_prompts.py",
        ]

        missing = [str(path) for path in files if not path.exists()]
        self.assertFalse(missing, f"Missing expected files: {missing}")

        for path in files:
            source = path.read_text(encoding="utf-8")
            try:
                compile(source, str(path), "exec")
            except SyntaxError as exc:  # pragma: no cover - assertion path
                self.fail(f"Compile failed for {path}: {exc}")


class TestNodeRegistration(unittest.TestCase):
    def test_main_init_registers_local_nodes(self):
        node_root = _resolve_node_root()
        init_path = node_root / "__init__.py"
        text = init_path.read_text(encoding="utf-8")

        self.assertIn("GZ_CopilotAgent", text)
        self.assertIn("GZ_LMStudioTextEnhancer", text)
        self.assertIn("GZ_AdvancedTextEnhancer", text)
        self.assertIn("GZ_ProviderSettings", text)
        self.assertIn("GZ_PromptLibraryNode", text)
        self.assertIn("GZ_StyleStackNode", text)
        self.assertNotIn("GZ_OpenAICompatibleTextEnhancer", text)
        self.assertNotIn("GZ_EnhancedPreviewText", text)

    def test_main_init_registers_pollinations_audio_nodes(self):
        node_root = _resolve_node_root()
        init_path = node_root / "__init__.py"
        text = init_path.read_text(encoding="utf-8")

        self.assertIn("GZ_TextToSpeech", text)
        self.assertIn("GZ_SpeechToText", text)
        self.assertIn("GZ_TextToAudio", text)


class TestAdvancedModeFamilies(unittest.TestCase):
    def test_advanced_node_exposes_grouped_mode_family_inputs(self):
        node_root = _resolve_node_root()
        advanced_path = node_root / "advanced_text_enhancer.py"
        text = advanced_path.read_text(encoding="utf-8")

        self.assertIn('"text_mode"', text)
        self.assertIn('"image_mode"', text)
        self.assertIn('"video_mode"', text)
        self.assertIn('"tts_mode"', text)
        self.assertIn('"stt_mode"', text)
        self.assertIn('"ttaudio_mode"', text)
        self.assertIn('"active_engine"', text)
        self.assertIn('"pollinations_model"', text)
        self.assertIn('"lm_studio_model"', text)
        self.assertIn('"openai_model_override"', text)
        self.assertIn('"style_preset_1"', text)
        self.assertIn('"style_preset_2"', text)
        self.assertIn('"style_preset_3"', text)
        self.assertIn('"additional_styles"', text)
        self.assertIn('"tts_style_preset"', text)
        self.assertIn('"stt_style_preset"', text)
        self.assertIn('"ttaudio_style_preset"', text)
        self.assertIn('"advanced_audio_style_bundle"', text)
        self.assertIn("Unsupported active_engine", text)
        self.assertIn('RETURN_TYPES = ("STRING", "IMAGE", "VIDEO", "AUDIO")', text)
        self.assertIn('RETURN_NAMES = ("text", "image", "video", "audio")', text)
        self.assertNotIn('"output_kind"', text)
        self.assertIn('"forceInput": True', text)
        self.assertIn('"control_after_generate": True', text)


class TestGroupedModeFamiliesAcrossNodes(unittest.TestCase):
    def test_text_oriented_nodes_expose_grouped_mode_inputs(self):
        node_root = _resolve_node_root()

        grouped_mode_files = [
            node_root / "pollinations" / "text_enhancer.py",
            node_root / "lm_studio_vision.py",
            node_root / "copilot_agent.py",
        ]

        for path in grouped_mode_files:
            text = path.read_text(encoding="utf-8")
            self.assertIn('"text_mode_enabled"', text, msg=f"Missing text mode toggle in {path}")
            self.assertIn('"text_mode"', text, msg=f"Missing text mode picker in {path}")
            self.assertIn('"image_mode_enabled"', text, msg=f"Missing image mode toggle in {path}")
            self.assertIn('"image_mode"', text, msg=f"Missing image mode picker in {path}")
            self.assertIn('"video_mode_enabled"', text, msg=f"Missing video mode toggle in {path}")
            self.assertIn('"video_mode"', text, msg=f"Missing video mode picker in {path}")
            self.assertIn('"tts_mode_enabled"', text, msg=f"Missing tts mode toggle in {path}")
            self.assertIn('"tts_mode"', text, msg=f"Missing tts mode picker in {path}")
            self.assertIn('"style_preset_1"', text, msg=f"Missing style preset 1 picker in {path}")
            self.assertIn('"style_preset_2"', text, msg=f"Missing style preset 2 picker in {path}")
            self.assertIn('"style_preset_3"', text, msg=f"Missing style preset 3 picker in {path}")
            self.assertIn('"additional_styles"', text, msg=f"Missing additional styles input in {path}")
            self.assertIn("resolve_mode_family_preset", text, msg=f"Missing mode-family resolver in {path}")

        advanced_text = (node_root / "advanced_text_enhancer.py").read_text(encoding="utf-8")
        self.assertIn('"active_engine"', advanced_text)
        self.assertIn('"additional_styles"', advanced_text)
        self.assertIn("resolve_mode_family_preset", advanced_text)
        self.assertIn("_OpenAICompatibleEngine", advanced_text)


class TestModeSystemPromptLayering(unittest.TestCase):
    def test_instruction_modes_include_system_prompt_layering(self):
        node_root = _resolve_node_root()
        instruction_init = node_root / "instruction_modes" / "__init__.py"
        text = instruction_init.read_text(encoding="utf-8")

        self.assertIn("MODE_SYSTEM_PROMPTS", text)
        self.assertIn("def get_mode_system_prompt", text)
        self.assertIn("def resolve_mode_preset", text)
        self.assertIn("include_system_prompt", text)
        self.assertIn("text", text)

    def test_copilot_uses_dynamic_mode_category_hint(self):
        node_root = _resolve_node_root()
        copilot_path = node_root / "copilot_agent.py"
        text = copilot_path.read_text(encoding="utf-8")

        self.assertIn("infer_mode_category", text)
        self.assertIn("mode_category=mode_category", text)
        self.assertNotIn('mode_category="universal"', text)


class TestCopilotAgentResilience(unittest.TestCase):
    def test_copilot_node_exposes_auth_controls(self):
        node_root = _resolve_node_root()
        copilot_path = node_root / "copilot_agent.py"
        text = copilot_path.read_text(encoding="utf-8")

        self.assertIn("auth_mode", text)
        self.assertIn("auth_status_only", text)
        self.assertIn("reconnect", text)

    def test_copilot_node_uses_prompt_mode_with_capability_cache(self):
        node_root = _resolve_node_root()
        copilot_path = node_root / "copilot_agent.py"
        text = copilot_path.read_text(encoding="utf-8")

        self.assertIn('"--prompt"', text)
        self.assertNotIn('"chat",', text)
        self.assertIn("COPILOT_GITHUB_TOKEN", text)
        self.assertIn("_get_model_capability", text)

    def test_copilot_long_prompts_use_stdin_transport_instead_of_prompt_file_indirection(self):
        node_root = _resolve_node_root()
        copilot_path = node_root / "copilot_agent.py"
        text = copilot_path.read_text(encoding="utf-8")

        self.assertIn("stdin_text", text)
        self.assertIn("stdin prompt transport", text)
        self.assertNotIn("Read the complete prompt from this local UTF-8 file", text)

    def test_copilot_model_options_prefer_local_cli_discovery(self):
        node_root = _resolve_node_root()
        copilot_path = node_root / "copilot_agent.py"
        text = copilot_path.read_text(encoding="utf-8")

        self.assertIn('_discover_copilot_cli_models()', text)
        self.assertIn('"help", "config"', text)
        self.assertIn("_COPILOT_MODEL_LINE_PATTERN", text)

    def test_copilot_error_classifier_covers_quota_capacity_and_model_failures(self):
        node_root = _resolve_node_root()
        copilot_path = node_root / "copilot_agent.py"
        text = copilot_path.read_text(encoding="utf-8")

        self.assertIn('"rate_limited"', text)
        self.assertIn('"upstream_timeout"', text)
        self.assertIn('"service_busy"', text)
        self.assertIn('"model_unavailable"', text)
        self.assertIn('"from --model flag is not available"', text)
        self.assertIn("_build_copilot_cli_failure", text)

    def test_copilot_auto_allow_all_tools_notice_stays_out_of_model_output(self):
        node_root = _resolve_node_root()
        copilot_path = node_root / "copilot_agent.py"
        text = copilot_path.read_text(encoding="utf-8")

        self.assertIn("auto-enabling it for reliability", text)
        self.assertNotIn(
            '[Copilot Notice] Non-interactive Copilot mode requires --allow-all-tools; it was auto-enabled for reliability.',
            text,
        )


class TestPollinationsAudioAndModelDiscovery(unittest.TestCase):
    def test_speech_to_text_supports_comfy_audio_input(self):
        node_root = _resolve_node_root()
        stt_path = node_root / "pollinations" / "speech_to_text.py"
        text = stt_path.read_text(encoding="utf-8")

        self.assertIn('"audio": ("AUDIO",)', text)
        self.assertIn('RETURN_TYPES = ("STRING",)', text)
        self.assertIn("_write_audio_input_to_temp_wav", text)

    def test_pollinations_media_nodes_return_native_media_outputs(self):
        node_root = _resolve_node_root() / "pollinations"

        tts_text = (node_root / "text_to_speech.py").read_text(encoding="utf-8")
        ttaudio_text = (node_root / "text_to_audio.py").read_text(encoding="utf-8")
        video_text = (node_root / "video_gen.py").read_text(encoding="utf-8")

        self.assertIn('RETURN_TYPES = ("AUDIO"', tts_text)
        self.assertIn('RETURN_TYPES = ("AUDIO",)', ttaudio_text)
        self.assertIn('RETURN_TYPES = ("VIDEO",)', video_text)

    def test_text_enhancer_uses_vision_filtered_catalog_models(self):
        node_root = _resolve_node_root()
        enhancer_path = node_root / "pollinations" / "text_enhancer.py"
        text = enhancer_path.read_text(encoding="utf-8")

        self.assertIn("fetch_pollinations_text_models", text)
        self.assertIn("require_vision=False", text)
        self.assertIn("get_pollinations_model_entry", text)

    def test_model_catalog_exposes_audio_task_buckets(self):
        node_root = _resolve_node_root()
        catalog_path = node_root / "pollinations" / "model_catalog.py"
        text = catalog_path.read_text(encoding="utf-8")

        self.assertIn("generation_speech", text)
        self.assertIn("generation_music", text)
        self.assertIn("fetch_pollinations_text_models", text)
        self.assertIn("fetch_pollinations_advanced_models", text)
        self.assertIn("supports_pollinations_family", text)

    def test_pollinations_image_and_video_nodes_expose_style_picker(self):
        node_root = _resolve_node_root()
        image_path = node_root / "pollinations" / "image_gen.py"
        video_path = node_root / "pollinations" / "video_gen.py"

        image_text = image_path.read_text(encoding="utf-8")
        video_text = video_path.read_text(encoding="utf-8")

        self.assertIn('"style_preset_1"', image_text)
        self.assertIn('"style_preset_2"', image_text)
        self.assertIn('"style_preset_3"', image_text)
        self.assertIn('"additional_styles"', image_text)
        self.assertIn('"style_preset_1"', video_text)
        self.assertIn('"style_preset_2"', video_text)
        self.assertIn('"style_preset_3"', video_text)
        self.assertIn('"additional_styles"', video_text)

    def test_pollinations_image_and_video_nodes_use_standardized_image_socket_name(self):
        node_root = _resolve_node_root()
        image_path = node_root / "pollinations" / "image_gen.py"
        video_path = node_root / "pollinations" / "video_gen.py"

        image_text = image_path.read_text(encoding="utf-8")
        video_text = video_path.read_text(encoding="utf-8")

        self.assertIn('"image": ("IMAGE",)', image_text)
        self.assertIn('"image": ("IMAGE",)', video_text)
        self.assertNotIn('"reference_image": ("IMAGE",)', image_text)
        self.assertNotIn('"init_image": ("IMAGE",)', video_text)

    def test_style_stack_node_exposes_seven_style_slots(self):
        node_root = _resolve_node_root()
        style_stack_path = node_root / "style_stack_node.py"
        text = style_stack_path.read_text(encoding="utf-8")

        self.assertIn('"style_preset_1"', text)
        self.assertIn('"style_preset_7"', text)
        self.assertIn("get_style_stack_default", text)
        self.assertIn('RETURN_NAMES = ("additional_styles",)', text)


class TestPreviewAndPackagePolish(unittest.TestCase):
    def test_standalone_preview_and_openai_nodes_are_not_registered(self):
        node_root = _resolve_node_root()
        init_path = node_root / "__init__.py"
        text = init_path.read_text(encoding="utf-8")

        self.assertNotIn("GZ_EnhancedPreviewText", text)
        self.assertNotIn("GZ_OpenAICompatibleTextEnhancer", text)

    def test_package_version_matches_current_release_line(self):
        node_root = _resolve_node_root()
        init_path = node_root / "__init__.py"
        text = init_path.read_text(encoding="utf-8")

        self.assertIn('__version__ = "0.7.4"', text)

    def test_secret_persistence_defaults_are_session_only(self):
        node_root = _resolve_node_root()

        files = [
            node_root / "advanced_text_enhancer.py",
            node_root / "lm_studio_vision.py",
            node_root / "pollinations" / "text_enhancer.py",
            node_root / "pollinations" / "image_gen.py",
            node_root / "pollinations" / "video_gen.py",
            node_root / "pollinations" / "text_to_speech.py",
            node_root / "pollinations" / "speech_to_text.py",
            node_root / "pollinations" / "text_to_audio.py",
        ]

        for path in files:
            text = path.read_text(encoding="utf-8")
            self.assertIn("persist_", text, msg=f"Expected persistence controls in {path}")

        advanced_path = node_root / "advanced_text_enhancer.py"
        advanced_text = advanced_path.read_text(encoding="utf-8")
        self.assertIn('"persist_provider_settings"', advanced_text)
        self.assertIn("persist_provider_settings: bool = True", advanced_text)
        self.assertIn("persist_api_settings", advanced_text)
        self.assertIn("persist_api_settings: bool = True", advanced_text)

        copilot_path = node_root / "copilot_agent.py"
        copilot_text = copilot_path.read_text(encoding="utf-8")
        self.assertIn("persist_copilot_executable", copilot_text)
        self.assertIn("persist_copilot_executable: bool = True", copilot_text)

    def test_provider_settings_warns_that_saved_secrets_are_local_file_persistence(self):
        node_root = _resolve_node_root()
        provider_settings_path = node_root / "provider_settings.py"
        text = provider_settings_path.read_text(encoding="utf-8")

        self.assertIn("not OS-backed secret-vault storage", text)
        self.assertIn("prefer environment variables when you do not want disk persistence", text)
        self.assertIn("Saved settings to", text)


class TestCentralizedLocalConfigArchitecture(unittest.TestCase):
    def test_settings_store_forces_comfyui_user_directory_and_bootstraps_local_file(self):
        node_root = _resolve_node_root()
        settings_store_path = node_root / "settings_store.py"
        text = settings_store_path.read_text(encoding="utf-8")

        self.assertIn('parents[2] / "user"', text)
        self.assertIn("folder_paths.get_user_directory", text)
        self.assertNotIn('os.path.expanduser("~")', text)
        self.assertIn("ensure_settings_file()", text)
        self.assertIn('resolve_config_value', text)
        self.assertIn('SETTING_SPECS', text)

    def test_sample_local_config_file_exists(self):
        node_root = _resolve_node_root()
        sample_path = node_root / "overtli_studio_settings.sample.json"
        text = sample_path.read_text(encoding="utf-8")

        self.assertIn('"schema_version": 2', text)
        self.assertIn('"pollinations_api_key"', text)
        self.assertIn('"lmstudio_base_url"', text)
        self.assertIn('"openai_compatible_base_url"', text)
        self.assertIn('"openai_compatible_model"', text)
        self.assertIn('"copilot_executable"', text)
        self.assertIn('"copilot_model"', text)

    def test_nodes_resolve_runtime_config_through_central_helper(self):
        node_root = _resolve_node_root()

        files = [
            node_root / "advanced_text_enhancer.py",
            node_root / "lm_studio_vision.py",
            node_root / "copilot_agent.py",
            node_root / "pollinations" / "text_enhancer.py",
            node_root / "pollinations" / "image_gen.py",
            node_root / "pollinations" / "video_gen.py",
            node_root / "pollinations" / "text_to_speech.py",
            node_root / "pollinations" / "speech_to_text.py",
            node_root / "pollinations" / "text_to_audio.py",
        ]

        for path in files:
            text = path.read_text(encoding="utf-8")
            self.assertIn("resolve_config_value", text, msg=f"Expected centralized config resolution in {path}")
            self.assertNotIn("API key persisted", text, msg=f"Expected persistence logging to be centralized in {path}")

    def test_gitignore_covers_local_runtime_config_artifacts(self):
        node_root = _resolve_node_root()
        gitignore_path = node_root / ".gitignore"
        text = gitignore_path.read_text(encoding="utf-8")

        self.assertIn("overtli_studio_settings.json", text)
        self.assertIn("overtli_studio_settings.local.json", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
