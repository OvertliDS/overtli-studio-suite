import base64
import importlib
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import types
import unittest
from typing import Any, cast
from types import SimpleNamespace
from unittest import mock


def _resolve_node_root() -> pathlib.Path:
    direct_root = pathlib.Path(__file__).resolve().parents[2]
    nested_root = direct_root / "custom_nodes" / "overtli-studio-suite"
    if nested_root.exists():
        return nested_root
    return direct_root


ROOT = _resolve_node_root()
PACKAGE_ALIAS = "overtli_suite_behavior"

try:
    TORCH = importlib.import_module("torch")
except ModuleNotFoundError as exc:
    raise unittest.SkipTest("torch is not installed; skipping behavior tests outside ComfyUI runtime") from exc


_FOLDER_PATHS = types.ModuleType("folder_paths")
_FOLDER_PATHS_ANY = cast(Any, _FOLDER_PATHS)
_FOLDER_PATHS_ANY._user_directory = tempfile.gettempdir()
_FOLDER_PATHS_ANY._temp_directory = tempfile.gettempdir()
_FOLDER_PATHS_ANY._input_directory = tempfile.gettempdir()
_FOLDER_PATHS_ANY.base_path = tempfile.gettempdir()
_FOLDER_PATHS_ANY.get_user_directory = lambda: _FOLDER_PATHS_ANY._user_directory
_FOLDER_PATHS_ANY.get_temp_directory = lambda: _FOLDER_PATHS_ANY._temp_directory
_FOLDER_PATHS_ANY.get_input_directory = lambda: _FOLDER_PATHS_ANY._input_directory
sys.modules["folder_paths"] = _FOLDER_PATHS


def _install_media_stubs() -> None:
    comfy_extras = types.ModuleType("comfy_extras")
    nodes_audio = types.ModuleType("comfy_extras.nodes_audio")

    def _load_audio_file(_path: str):
        return TORCH.zeros(1600, dtype=TORCH.float32), 16000

    cast(Any, nodes_audio).load = _load_audio_file
    sys.modules["comfy_extras"] = comfy_extras
    sys.modules["comfy_extras.nodes_audio"] = nodes_audio

    comfy_api = types.ModuleType("comfy_api")
    latest = types.ModuleType("comfy_api.latest")
    input_impl = types.ModuleType("comfy_api.latest._input_impl")
    video_types = types.ModuleType("comfy_api.latest._input_impl.video_types")

    class VideoFromFile:
        def __init__(self, path: str):
            self.path = path

    cast(Any, video_types).VideoFromFile = VideoFromFile
    sys.modules["comfy_api"] = comfy_api
    sys.modules["comfy_api.latest"] = latest
    sys.modules["comfy_api.latest._input_impl"] = input_impl
    sys.modules["comfy_api.latest._input_impl.video_types"] = video_types


_install_media_stubs()


def _load_suite_package():
    if PACKAGE_ALIAS in sys.modules:
        return sys.modules[PACKAGE_ALIAS]

    spec = importlib.util.spec_from_file_location(
        PACKAGE_ALIAS,
        ROOT / "__init__.py",
        submodule_search_locations=[str(ROOT)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load package spec for {PACKAGE_ALIAS} from {ROOT}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE_ALIAS] = module
    spec.loader.exec_module(module)
    return module


SUITE = _load_suite_package()
REQUESTS = importlib.import_module("requests")

base_node = importlib.import_module(f"{PACKAGE_ALIAS}.base_node")
exceptions = importlib.import_module(f"{PACKAGE_ALIAS}.exceptions")
settings_store = importlib.import_module(f"{PACKAGE_ALIAS}.settings_store")
provider_settings = importlib.import_module(f"{PACKAGE_ALIAS}.nodes.provider_settings.node")
prompt_library_store = importlib.import_module(f"{PACKAGE_ALIAS}.prompt_library_store")
prompt_library_node = importlib.import_module(f"{PACKAGE_ALIAS}.nodes.prompt_library.node")
prompt_styles = importlib.import_module(f"{PACKAGE_ALIAS}.styles")
style_stack_node = importlib.import_module(f"{PACKAGE_ALIAS}.nodes.style_stack.node")
advanced_text_enhancer = importlib.import_module(f"{PACKAGE_ALIAS}.nodes.advanced_text_enhancer.node")
openai_compatible_text_enhancer = importlib.import_module(
    f"{PACKAGE_ALIAS}.nodes.openai_compatible_text_enhancer.node"
)
openai_compatible_engine = importlib.import_module(f"{PACKAGE_ALIAS}.engine.openai_compatible")
output_sanitizer = importlib.import_module(f"{PACKAGE_ALIAS}.output_sanitizer")
lm_studio_vision = importlib.import_module(f"{PACKAGE_ALIAS}.nodes.llm_text_enhancer.node")
lm_studio_engine = importlib.import_module(f"{PACKAGE_ALIAS}.engine.llm_text_enhancer")
copilot_agent = importlib.import_module(f"{PACKAGE_ALIAS}.nodes.copilot_agent.node")
pollinations_text = importlib.import_module(f"{PACKAGE_ALIAS}.engine.pollinations.text_enhancer")
pollinations_image = importlib.import_module(f"{PACKAGE_ALIAS}.engine.pollinations.image_gen")
pollinations_video = importlib.import_module(f"{PACKAGE_ALIAS}.engine.pollinations.video_gen")
pollinations_tts = importlib.import_module(f"{PACKAGE_ALIAS}.engine.pollinations.text_to_speech")
pollinations_stt = importlib.import_module(f"{PACKAGE_ALIAS}.engine.pollinations.speech_to_text")
pollinations_ttaudio = importlib.import_module(f"{PACKAGE_ALIAS}.engine.pollinations.text_to_audio")


PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7+2bkAAAAASUVORK5CYII="
)


def _set_stub_paths(directory: str) -> None:
    _FOLDER_PATHS_ANY._user_directory = directory
    _FOLDER_PATHS_ANY._temp_directory = directory
    _FOLDER_PATHS_ANY._input_directory = directory
    _FOLDER_PATHS_ANY.base_path = directory


def _reset_runtime_state() -> None:
    cast(Any, settings_store)._CACHE_DATA = None
    cast(Any, settings_store)._CACHE_MTIME = -1.0
    cast(Any, prompt_library_store)._CACHE_DATA = None
    cast(Any, prompt_library_store)._CACHE_MTIME = -1.0
    cast(Any, lm_studio_vision)._CACHED_MODELS = None
    cast(Any, copilot_agent)._COPILOT_MODEL_OPTIONS_CACHE = (0.0, [])
    cast(Any, copilot_agent)._SESSION_MODEL_CAPABILITIES.clear()


def _clear_env() -> None:
    for env_name in {
        "GZ_POLLINATIONS_API_KEY",
        "POLLINATIONS_API_KEY",
        "GZ_LMSTUDIO_BASE_URL",
        "LMSTUDIO_BASE_URL",
        "GZ_LMSTUDIO_API_KEY",
        "LMSTUDIO_API_KEY",
        "GZ_OPENAI_COMPAT_API_KEY",
        "OPENAI_API_KEY",
        "GZ_OPENAI_COMPAT_BASE_URL",
        "OPENAI_BASE_URL",
        "GZ_OPENAI_COMPAT_MODEL",
        "OPENAI_COMPAT_MODEL",
        "GZ_COPILOT_EXECUTABLE",
        "COPILOT_EXECUTABLE",
        "GZ_COPILOT_MODEL",
        "COPILOT_MODEL",
        "COPILOT_GITHUB_TOKEN",
        "GH_TOKEN",
        "GITHUB_TOKEN",
    }:
        os.environ.pop(env_name, None)


def _make_config(temp_dir: str):
    pollinations_cfg = SimpleNamespace(
        api_key="",
        chat_timeout=60,
        image_timeout=60,
        video_timeout=120,
        tts_timeout=60,
        stt_timeout=120,
        audio_generation_timeout=120,
        chat_endpoint="https://pollinations.test/v1/chat/completions",
        image_endpoint="https://pollinations.test/image",
        video_endpoint="https://pollinations.test/video",
        audio_endpoint="https://pollinations.test/audio",
        audio_speech_endpoint="https://pollinations.test/v1/audio/speech",
        audio_transcriptions_endpoint="https://pollinations.test/v1/audio/transcriptions",
    )
    lmstudio_cfg = SimpleNamespace(
        base_url="http://localhost:1234",
        api_key="",
        timeout=120,
        models_endpoint="http://localhost:1234/v1/models",
        chat_endpoint="http://localhost:1234/v1/chat/completions",
        unload_endpoint="http://localhost:1234/api/v1/models/unload",
    )
    copilot_cfg = SimpleNamespace(
        executable="copilot",
        default_model="gpt-4.1",
        timeout=120,
        silent=True,
        no_ask_user=True,
    )
    openai_cfg = SimpleNamespace(
        base_url="https://openai-compatible.test/v1",
        api_key="",
        default_model="gpt-4.1-mini",
        timeout=120,
        require_api_key=True,
    )
    return SimpleNamespace(
        temp_dir=temp_dir,
        pollinations=pollinations_cfg,
        lm_studio=lmstudio_cfg,
        copilot=copilot_cfg,
        openai_compatible=openai_cfg,
    )


def _make_image_tensor(batch: int = 1):
    return TORCH.zeros((batch, 2, 2, 3), dtype=TORCH.float32)


def _write_png(path: pathlib.Path) -> pathlib.Path:
    path.write_bytes(PNG_BYTES)
    return path


class FakeResponse:
    def __init__(self, *, json_data=None, text: str = "", headers=None, content: bytes = b"", status_code: int = 200):
        self._json_data = json_data
        self.text = text or (json.dumps(json_data) if json_data is not None else "")
        self.headers = headers or {}
        self.status_code = status_code
        self.ok = status_code < 400
        self._content = content
        self.content = content

    def json(self):
        if self._json_data is None:
            raise ValueError("No JSON payload configured")
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise REQUESTS.exceptions.HTTPError(response=self)

    def iter_content(self, chunk_size: int = 8192):
        if not self._content:
            return iter(())
        for offset in range(0, len(self._content), chunk_size):
            yield self._content[offset : offset + chunk_size]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class BehaviorTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir_obj = tempfile.TemporaryDirectory(prefix="overtli_nodes_")
        self.temp_dir = self.temp_dir_obj.name
        _set_stub_paths(self.temp_dir)
        _clear_env()
        _reset_runtime_state()
        self.config = _make_config(self.temp_dir)

    def tearDown(self):
        _clear_env()
        _reset_runtime_state()
        self.temp_dir_obj.cleanup()


class TestPersistenceAndPromptLibrary(BehaviorTestCase):
    def test_base_node_helpers_and_settings_precedence_survive_restart(self):
        self.assertEqual(base_node.GZBaseNode.require_prompt("  hello  "), "hello")
        self.assertEqual(base_node.GZBaseNode.clamp_timeout(0), 1)
        self.assertEqual(base_node.GZBaseNode.clamp_timeout(5000), 1200)
        with self.assertRaises(exceptions.OvertliInputError):
            base_node.GZBaseNode.require_prompt("   ")

        settings_store.save_persistent_settings(
            {
                "copilot_executable": "copilot.cmd",
                "copilot_model": "persisted-model",
            },
            source="behavior-test",
        )

        self.assertEqual(settings_store.resolve_config_value("copilot_model"), "persisted-model")
        with mock.patch.dict(os.environ, {"GZ_COPILOT_MODEL": "env-model"}, clear=False):
            self.assertEqual(settings_store.resolve_config_value("copilot_model"), "env-model")

        reloaded_store = importlib.reload(settings_store)
        persisted = reloaded_store.load_persistent_settings(force_reload=True)
        self.assertEqual(persisted["copilot_executable"], "copilot.cmd")
        self.assertEqual(persisted["copilot_model"], "persisted-model")

    def test_provider_settings_preview_and_apply_save_restart_safe_values(self):
        node = provider_settings.GZ_ProviderSettings()

        preview = node.execute(
            apply_settings=False,
            pollinations_api_key="sk-test-12345678",
            lmstudio_base_url="http://localhost:1234",
            openai_compatible_model="gpt-4.1-mini",
        )
        preview_text = preview["result"][0]
        self.assertIn("Preview only", preview_text)
        self.assertNotIn("sk-test-12345678", preview_text)
        self.assertEqual(settings_store.load_persistent_settings(force_reload=True)["lmstudio_base_url"], "")

        applied = node.execute(
            apply_settings=True,
            pollinations_api_key="sk-test-12345678",
            lmstudio_base_url="http://localhost:1234",
            openai_compatible_api_key="oa-key-abcdef12",
            openai_compatible_base_url="https://api.example.test/v1",
            openai_compatible_model="gpt-4.1-mini",
            copilot_executable="copilot.cmd",
            copilot_model="gpt-4.1",
        )
        applied_text = applied["result"][0]
        self.assertIn("Saved settings to", applied_text)

        persisted = settings_store.load_persistent_settings(force_reload=True)
        self.assertEqual(persisted["lmstudio_base_url"], "http://localhost:1234")
        self.assertEqual(persisted["openai_compatible_model"], "gpt-4.1-mini")
        self.assertEqual(persisted["copilot_executable"], "copilot.cmd")
        self.assertEqual(persisted["copilot_model"], "gpt-4.1")

        reloaded_store = importlib.reload(settings_store)
        self.assertEqual(
            reloaded_store.load_persistent_settings(force_reload=True)["openai_compatible_base_url"],
            "https://api.example.test/v1",
        )

    def test_prompt_library_store_crud_import_usage_and_delete(self):
        alpha = prompt_library_store.upsert_prompt_entry(
            name="Alpha Prompt",
            prompt="First prompt body",
            category="Utilities",
            tags="alpha,beta",
            notes="Initial note",
        )
        self.assertEqual(alpha["name"], "Alpha Prompt")

        used = prompt_library_store.get_prompt_entry("Alpha Prompt", increment_use_count=True)
        self.assertIsNotNone(used)
        self.assertEqual(used["uses"], 1)

        renamed = prompt_library_store.rename_prompt_entry("Alpha Prompt", "Beta Prompt")
        self.assertEqual(renamed["name"], "Beta Prompt")

        listing = prompt_library_store.list_prompt_entries(search_query="beta", sort_mode="most_used")
        self.assertEqual([entry["name"] for entry in listing], ["Beta Prompt"])

        export_payload = prompt_library_store.export_prompt_library_json(pretty=True)
        self.assertIn("Beta Prompt", export_payload)

        incoming_payload = json.dumps(
            {
                "schema_version": 1,
                "entries": [
                    {
                        "name": "Beta Prompt",
                        "category": "Utilities",
                        "prompt": "Updated prompt body",
                        "tags": ["updated"],
                        "notes": "Updated note",
                        "created_at": "2026-01-01T00:00:00+00:00",
                        "updated_at": "2026-01-01T00:00:00+00:00",
                        "uses": 5,
                    },
                    {
                        "name": "Gamma Prompt",
                        "category": "General",
                        "prompt": "Gamma body",
                        "tags": [],
                        "notes": "",
                        "created_at": "2026-01-01T00:00:00+00:00",
                        "updated_at": "2026-01-01T00:00:00+00:00",
                        "uses": 0,
                    },
                ],
            }
        )
        import_result = prompt_library_store.import_prompt_library_json(incoming_payload, merge=True, overwrite_existing=True)
        self.assertEqual(import_result, {"imported": 1, "updated": 1, "skipped": 0})

        updated = prompt_library_store.get_prompt_entry("Beta Prompt")
        self.assertEqual(updated["prompt"], "Updated prompt body")
        self.assertTrue(prompt_library_store.delete_prompt_entry("Gamma Prompt"))
        self.assertIsNone(prompt_library_store.get_prompt_entry("Gamma Prompt"))

    def test_prompt_library_node_save_load_view_delete_and_refresh(self):
        node = prompt_library_node.GZ_PromptLibraryNode()

        saved = node.execute(
            action="save_prompt",
            prompt_text="Use this reusable prompt.",
            prompt_name="Library Prompt",
            category="Workflow",
            tags_csv="workflow,reuse",
            notes="Saved from behavior suite",
            show_library_snapshot=False,
        )
        self.assertEqual(saved["result"][0], "Use this reusable prompt.")
        self.assertIn("Saved prompt 'Library Prompt'", saved["ui"]["text"][0])

        loaded = node.execute(
            action="load_prompt",
            prompt_text="",
            saved_prompt="Library Prompt",
            increment_use_on_load=True,
            show_library_snapshot=False,
        )
        self.assertEqual(loaded["result"][0], "Use this reusable prompt.")
        self.assertIn("Loaded prompt 'Library Prompt'", loaded["ui"]["text"][0])

        viewed = node.execute(
            action="view_library",
            prompt_text="",
            sort_mode="most_used",
            category_filter="All",
            search_query="Library",
            show_library_snapshot=True,
        )
        self.assertIn("Library Prompt", viewed["result"][0])

        deleted = node.execute(
            action="delete_prompt",
            prompt_text="",
            saved_prompt="Library Prompt",
            show_library_snapshot=True,
        )
        self.assertIn("Deleted prompt 'Library Prompt'.", deleted["ui"]["text"][0])
        self.assertNotIn("Library Prompt", deleted["result"][0])

        refreshed = node.execute(
            action="refresh_cache",
            prompt_text="",
            show_library_snapshot=True,
        )
        self.assertIn("Prompt library cache refreshed.", refreshed["ui"]["text"][0])

    def test_style_stack_node_returns_combined_style_guidance(self):
        node = style_stack_node.GZ_StyleStackNode()
        available_styles = [label for label in prompt_styles.get_style_options() if label != prompt_styles.STYLE_OFF_LABEL]
        self.assertTrue(available_styles, "Expected at least one enabled style option")

        result = node.execute(
            available_styles[0],
            prompt_styles.STYLE_OFF_LABEL,
            prompt_styles.STYLE_OFF_LABEL,
            prompt_styles.STYLE_OFF_LABEL,
            prompt_styles.STYLE_OFF_LABEL,
            prompt_styles.STYLE_OFF_LABEL,
            prompt_styles.STYLE_OFF_LABEL,
        )[0]
        self.assertTrue(result.strip())


class TestRoutingAndProviderNodes(BehaviorTestCase):
    def test_advanced_router_input_types_expose_mode_toggles_and_image_off_option(self):
        input_types = advanced_text_enhancer.GZ_AdvancedTextEnhancer.INPUT_TYPES()
        provider_options = list(input_types["required"]["provider"][0])
        optional = input_types["optional"]

        self.assertIn("copilot", provider_options)
        self.assertNotIn("copilot-cli", provider_options)

        for toggle_key in (
            "text_mode_enabled",
            "image_mode_enabled",
            "video_mode_enabled",
            "tts_mode_enabled",
            "stt_mode_enabled",
            "ttaudio_mode_enabled",
        ):
            self.assertIn(toggle_key, optional)
            self.assertFalse(optional[toggle_key][1]["default"])

        image_mode_options = list(optional["image_mode"][0])
        self.assertIn("Off", image_mode_options)
        self.assertIn("copilot_model", optional)
        self.assertEqual(optional["api_base_url"][1]["default"], "")

    def test_advanced_router_dispatches_pollinations_local_copilot_and_openai_paths(self):
        router = advanced_text_enhancer.GZ_AdvancedTextEnhancer()
        captured_copilot_kwargs = {}
        captured_lmstudio_kwargs = {}

        def _capture_copilot_execute(**kwargs):
            captured_copilot_kwargs.update(kwargs)
            return ("copilot-text",)

        def _capture_lmstudio_execute(**kwargs):
            captured_lmstudio_kwargs.update(kwargs)
            return ("local-text",)

        with mock.patch.object(advanced_text_enhancer, "get_config", return_value=self.config), \
            mock.patch.object(pollinations_text.GZ_TextEnhancer, "execute", return_value=("pollinations-text",)), \
            mock.patch.object(lm_studio_vision.GZ_LLMTextEnhancer, "execute", side_effect=_capture_lmstudio_execute), \
            mock.patch.object(copilot_agent.GZ_CopilotAgent, "execute", side_effect=_capture_copilot_execute), \
            mock.patch.object(openai_compatible_text_enhancer.GZ_OpenAICompatibleTextEnhancer, "execute", return_value=("openai-text", "img", None, "aud")):

            pollinations_result = router.execute(
                provider="pollinations",
                active_engine="text",
                prompt="hello",
                pollinations_model="openai [text] [vision] [free]",
            )
            self.assertEqual(pollinations_result[0], "pollinations-text")

            local_result = router.execute(
                provider="lm_studio",
                active_engine="text",
                prompt="hello",
                api_base_url="http://lmstudio-override.local:1234",
            )
            self.assertEqual(local_result[0], "local-text")
            self.assertEqual(captured_lmstudio_kwargs.get("api_base_url"), "http://lmstudio-override.local:1234")

            copilot_result = router.execute(
                provider="copilot",
                active_engine="text",
                prompt="hello",
                copilot_executable="copilot.cmd",
                copilot_model="gpt-5-mini",
            )
            self.assertEqual(copilot_result[0], "copilot-text")
            self.assertEqual(captured_copilot_kwargs.get("model"), "gpt-5-mini")

            copilot_cli_result = router.execute(
                provider="copilot-cli",
                active_engine="text",
                prompt="hello",
                copilot_executable="copilot.cmd",
            )
            self.assertEqual(copilot_cli_result[0], "copilot-text")

            openai_result = router.execute(
                provider="openai_compatible",
                active_engine="text",
                prompt="hello",
                api_base_url="https://openai-compatible.test/v1",
                api_key="api-key",
            )
            self.assertEqual(openai_result, ("openai-text", "img", None, "aud"))

    def test_advanced_router_forwards_image_context_to_pollinations_text_enhancer(self):
        router = advanced_text_enhancer.GZ_AdvancedTextEnhancer()
        captured_kwargs = {}
        connected_image = _make_image_tensor()

        def _capture_execute(**kwargs):
            captured_kwargs.update(kwargs)
            return ("pollinations-text",)

        with mock.patch.object(advanced_text_enhancer, "get_config", return_value=self.config), \
            mock.patch.object(pollinations_text.GZ_TextEnhancer, "execute", side_effect=_capture_execute):

            result = router.execute(
                provider="pollinations",
                active_engine="text",
                prompt="",
                image=connected_image,
                pollinations_model="openai [text] [vision] [free]",
                vision_enabled=True,
            )

        self.assertEqual(result[0], "pollinations-text")
        self.assertIs(captured_kwargs.get("image"), connected_image)
        self.assertEqual(captured_kwargs.get("prompt"), "")
        self.assertTrue(captured_kwargs.get("vision_enabled"))

    def test_advanced_router_mode_toggle_forces_off_mode(self):
        router = advanced_text_enhancer.GZ_AdvancedTextEnhancer()
        captured_kwargs = {}

        def _capture_execute(**kwargs):
            captured_kwargs.update(kwargs)
            return ("pollinations-text",)

        with mock.patch.object(advanced_text_enhancer, "get_config", return_value=self.config), \
            mock.patch.object(pollinations_text.GZ_TextEnhancer, "execute", side_effect=_capture_execute):

            result = router.execute(
                provider="pollinations",
                active_engine="text",
                prompt="hello",
                text_mode_enabled=False,
                text_mode="📝 Enhance",
                pollinations_model="openai [text] [vision] [free]",
            )

        self.assertEqual(result[0], "pollinations-text")
        self.assertEqual(captured_kwargs.get("text_mode"), "Off")

    def test_advanced_router_rejects_provider_engine_mismatch_with_supported_list(self):
        router = advanced_text_enhancer.GZ_AdvancedTextEnhancer()

        with mock.patch.object(advanced_text_enhancer, "get_config", return_value=self.config):
            with self.assertRaises(exceptions.OvertliInputError) as copilot_ctx:
                router.execute(
                    provider="copilot",
                    active_engine="image",
                    prompt="hello",
                )

            with self.assertRaises(exceptions.OvertliInputError) as lmstudio_video_ctx:
                router.execute(
                    provider="lm_studio",
                    active_engine="video",
                    prompt="hello",
                )

        self.assertIn("Supported engines for provider 'copilot'", str(copilot_ctx.exception))
        self.assertIn("Supported engines for provider 'lm_studio'", str(lmstudio_video_ctx.exception))

    def test_openai_compatible_node_maps_engine_labels_to_internal_engine(self):
        node = openai_compatible_text_enhancer.GZ_OpenAICompatibleTextEnhancer()
        captured = {}
        selected_image_mode = list(openai_compatible_text_enhancer.IMAGE_MODE_NAMES)[0]

        def _capture_execute(*args, **kwargs):
            captured.update(kwargs)
            return ("ok", "img", None, "aud")

        with mock.patch.object(advanced_text_enhancer._OpenAICompatibleEngine, "execute", side_effect=_capture_execute):
            result = node.execute(
                active_engine="image_gen",
                prompt="draw a nebula",
                model="gpt-image-test",
                image_mode=selected_image_mode,
            )

        self.assertEqual(result, ("ok", "img", None, "aud"))
        self.assertEqual(captured["active_engine"], "image")
        self.assertEqual(captured["mode_preset"], selected_image_mode)

    def test_openai_compatible_node_rejects_invalid_engine_label(self):
        node = openai_compatible_text_enhancer.GZ_OpenAICompatibleTextEnhancer()

        with self.assertRaises(exceptions.OvertliInputError):
            node.execute(
                active_engine="invalid_engine",
                prompt="hello",
                model="gpt-test",
            )

    def test_lm_studio_node_handles_text_then_vision_and_persists_runtime_api_key(self):
        node = lm_studio_vision.GZ_LLMTextEnhancer()
        captured_payloads = []

        def _capture_post(url, json=None, headers=None, timeout=None):
            captured_payloads.append((url, json, headers, timeout))
            return FakeResponse(json_data={"choices": [{"message": {"content": "local response"}}]})

        with mock.patch.object(lm_studio_vision, "get_config", return_value=self.config), \
            mock.patch.object(lm_studio_vision, "_check_lmstudio_connection", return_value=(True, "Connected")), \
            mock.patch.object(lm_studio_vision, "requests") as requests_mock, \
            mock.patch.object(lm_studio_vision, "save_persistent_settings") as save_mock, \
            mock.patch.object(lm_studio_vision, "_cleanup_runtime_memory") as cleanup_mock, \
            mock.patch.object(lm_studio_vision, "_unload_model") as unload_mock:

            requests_mock.post.side_effect = _capture_post

            text_result = node.execute(
                provider="LM Studio",
                prompt="Explain this.",
                text_mode_enabled=True,
                text_mode="Off",
                image_mode_enabled=False,
                image_mode="Off",
                video_mode_enabled=False,
                video_mode="Off",
                tts_mode_enabled=False,
                tts_mode="Off",
                model="gpt-4.1 [local]",
                api_key="lm-key",
                persist_api_key=True,
                unload_lm_studio=True,
                unload_ollama=False,
            )
            self.assertEqual(text_result, ("local response",))
            self.assertEqual(captured_payloads[0][1]["messages"][-1]["content"], "Explain this.")

            with mock.patch.object(
                lm_studio_vision,
                "_prepare_image_data_urls",
                return_value=["data:image/png;base64,abcd"],
            ):
                vision_result = node.execute(
                    provider="LM Studio",
                    prompt="Describe the image.",
                    text_mode_enabled=True,
                    text_mode="Off",
                    image_mode_enabled=False,
                    image_mode="Off",
                    video_mode_enabled=False,
                    video_mode="Off",
                    tts_mode_enabled=False,
                    tts_mode="Off",
                    model="gpt-4.1 [local]",
                    image=_make_image_tensor(),
                    api_key="lm-key",
                    persist_api_key=True,
                    unload_lm_studio=True,
                    unload_ollama=False,
                )
            self.assertEqual(vision_result, ("local response",))
            multimodal_content = captured_payloads[-1][1]["messages"][-1]["content"]
            self.assertEqual(multimodal_content[0]["text"], "Describe the image.")
            self.assertEqual(multimodal_content[1]["image_url"]["url"], "data:image/png;base64,abcd")
            save_mock.assert_called()
            unload_mock.assert_called()
            cleanup_mock.assert_called()

    def test_lm_studio_node_openai_provider_uses_openai_compatible_saved_settings(self):
        node = lm_studio_vision.GZ_LLMTextEnhancer()
        captured = {}
        resolved_keys = []

        def _capture_post(url, json=None, headers=None, timeout=None):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            captured["timeout"] = timeout
            return FakeResponse(json_data={"choices": [{"message": {"content": "local response"}}]})

        def _resolve_config_value(key, runtime_value="", default=""):
            resolved_keys.append(key)
            mapping = {
                "openai_compatible_base_url": "https://saved-openai.test/v1",
                "openai_compatible_api_key": "saved-openai-key",
                "lmstudio_base_url": "http://saved-lmstudio.test:1234",
                "lmstudio_api_key": "saved-lmstudio-key",
            }
            return runtime_value or mapping.get(key, default)

        with mock.patch.object(lm_studio_vision, "get_config", return_value=self.config), \
            mock.patch.object(lm_studio_vision, "_check_lmstudio_connection", return_value=(True, "Connected")), \
            mock.patch.object(lm_studio_engine, "resolve_config_value", side_effect=_resolve_config_value), \
            mock.patch.object(lm_studio_vision, "requests") as requests_mock, \
            mock.patch.object(lm_studio_vision, "_cleanup_runtime_memory"):

            requests_mock.post.side_effect = _capture_post

            result = node.execute(
                provider="OpenAI-Compatible",
                prompt="Explain this.",
                text_mode_enabled=True,
                text_mode="Off",
                image_mode_enabled=False,
                image_mode="Off",
                video_mode_enabled=False,
                video_mode="Off",
                tts_mode_enabled=False,
                tts_mode="Off",
                model="gpt-4.1 [local]",
                api_base_url="",
                api_key="",
                persist_api_key=False,
                unload_lm_studio=False,
                unload_ollama=False,
            )

        self.assertEqual(result, ("local response",))
        self.assertIn("openai_compatible_base_url", resolved_keys)
        self.assertIn("openai_compatible_api_key", resolved_keys)
        self.assertNotIn("lmstudio_base_url", resolved_keys)
        self.assertNotIn("lmstudio_api_key", resolved_keys)
        self.assertEqual(captured.get("url"), "https://saved-openai.test/v1/chat/completions")
        self.assertEqual(captured.get("headers", {}).get("Authorization"), "Bearer saved-openai-key")

    def test_copilot_agent_attaches_images_and_persists_hidden_settings(self):
        node = copilot_agent.GZ_CopilotAgent()
        spaced_dir = pathlib.Path(self.temp_dir) / "vision space"
        spaced_dir.mkdir(parents=True, exist_ok=True)
        image_path = _write_png(spaced_dir / "vision image.png")
        captured_calls = []

        def _fake_run(*, executable_path, temp_dir, args, timeout_seconds, max_output_chars, stdin_text=""):
            captured_calls.append(
                {
                    "executable_path": executable_path,
                    "temp_dir": temp_dir,
                    "args": list(args),
                    "timeout_seconds": timeout_seconds,
                    "max_output_chars": max_output_chars,
                    "stdin_text": stdin_text,
                }
            )
            return 0, "copilot output", ""

        with mock.patch.object(copilot_agent, "get_config", return_value=self.config), \
            mock.patch.object(copilot_agent, "_resolve_copilot_executable", return_value="copilot.cmd"), \
            mock.patch.object(copilot_agent, "_run_copilot_command", side_effect=_fake_run), \
            mock.patch.object(copilot_agent, "_validate_image_file_context", return_value=(True, "")), \
            mock.patch.object(copilot_agent, "_get_model_capability", return_value=(True, "heuristic")), \
            mock.patch.object(copilot_agent, "save_persistent_settings") as save_mock:

            result = node.execute(
                prompt="Analyze this attachment.",
                text_mode_enabled=True,
                text_mode="Off",
                image_mode_enabled=False,
                image_mode="Off",
                video_mode_enabled=False,
                video_mode="Off",
                tts_mode_enabled=False,
                tts_mode="Off",
                model="gpt-4.1",
                file_path=str(image_path),
                copilot_executable="copilot.cmd",
                persist_copilot_executable=True,
                persist_selected_model=True,
                vision_enabled=True,
                allow_all_tools=False,
                allow_all_paths=False,
            )

        self.assertEqual(result, ("copilot output",))
        self.assertGreaterEqual(save_mock.call_count, 2)
        args = captured_calls[0]["args"]
        self.assertIn("--allow-all-tools", args)
        self.assertIn("--add-dir", args)
        self.assertIn(str(spaced_dir), args)
        self.assertIn("--prompt", args)
        prompt_arg = args[args.index("--prompt") + 1]
        safe_path = str(image_path).replace("\\", "/")
        self.assertIn(f'@"{safe_path}"', prompt_arg)
        self.assertEqual(captured_calls[0]["stdin_text"], "")

    def test_copilot_cached_runtime_vision_retry_keeps_image_context_active(self):
        node = copilot_agent.GZ_CopilotAgent()
        image_path = _write_png(pathlib.Path(self.temp_dir) / "vision-retry.png")
        captured_prompt = {}

        def _fake_run(*, executable_path, temp_dir, args, timeout_seconds, max_output_chars, stdin_text=""):
            if "--prompt" in args:
                captured_prompt["prompt"] = args[args.index("--prompt") + 1]
            captured_prompt["stdin_text"] = stdin_text
            return 0, "success after retry notice", ""

        with mock.patch.object(copilot_agent, "get_config", return_value=self.config), \
            mock.patch.object(copilot_agent, "_resolve_copilot_executable", return_value="copilot.cmd"), \
            mock.patch.object(copilot_agent, "_run_copilot_command", side_effect=_fake_run), \
            mock.patch.object(copilot_agent, "_validate_image_file_context", return_value=(True, "")), \
            mock.patch.object(copilot_agent, "_get_model_capability", return_value=(False, "runtime")):

            result = node.execute(
                prompt="Use the attachment.",
                text_mode_enabled=True,
                text_mode="Off",
                image_mode_enabled=False,
                image_mode="Off",
                video_mode_enabled=False,
                video_mode="Off",
                tts_mode_enabled=False,
                tts_mode="Off",
                model="gpt-4.1",
                file_path=str(image_path),
                vision_enabled=True,
                retry_cached_vision_models=True,
            )

        self.assertEqual(result, ("success after retry notice",))
        self.assertNotIn("[Copilot Notice]", result[0])
        safe_path = str(image_path).replace("\\", "/")
        expected_attachment = f'@"{safe_path}"' if " " in safe_path else f"@{safe_path}"
        self.assertIn(expected_attachment, captured_prompt["prompt"])
        self.assertEqual(captured_prompt["stdin_text"], "")

    def test_copilot_empty_prompt_with_attachment_injects_analysis_request(self):
        node = copilot_agent.GZ_CopilotAgent()
        image_path = _write_png(pathlib.Path(self.temp_dir) / "empty-prompt.png")
        captured_prompt = {}

        def _fake_run(*, executable_path, temp_dir, args, timeout_seconds, max_output_chars, stdin_text=""):
            if "--prompt" in args:
                captured_prompt["prompt"] = args[args.index("--prompt") + 1]
            captured_prompt["stdin_text"] = stdin_text
            return 0, "copilot output", ""

        with mock.patch.object(copilot_agent, "get_config", return_value=self.config), \
            mock.patch.object(copilot_agent, "_resolve_copilot_executable", return_value="copilot.cmd"), \
            mock.patch.object(copilot_agent, "_run_copilot_command", side_effect=_fake_run), \
            mock.patch.object(copilot_agent, "_validate_image_file_context", return_value=(True, "")), \
            mock.patch.object(copilot_agent, "_get_model_capability", return_value=(True, "heuristic")):

            result = node.execute(
                prompt="",
                text_mode_enabled=False,
                text_mode="Off",
                image_mode_enabled=False,
                image_mode="Off",
                video_mode_enabled=False,
                video_mode="Off",
                tts_mode_enabled=False,
                tts_mode="Off",
                model="gpt-4.1",
                file_path=str(image_path),
                vision_enabled=True,
            )

        self.assertEqual(result, ("copilot output",))
        self.assertIn(
            "Analyze the attached image files and describe what is visible in clear detail.",
            captured_prompt["prompt"],
        )

    def test_copilot_switches_to_vision_model_before_dispatch_for_heuristic_text_only_model(self):
        node = copilot_agent.GZ_CopilotAgent()
        image_path = _write_png(pathlib.Path(self.temp_dir) / "vision-fallback.png")
        seen_models = []

        def _fake_run(*, executable_path, temp_dir, args, timeout_seconds, max_output_chars, stdin_text=""):
            model_name = args[args.index("--model") + 1]
            seen_models.append(model_name)
            return 0, "The image shows a small UI layout with form fields.", ""

        def _capability_for(model_name: str):
            if model_name == "gpt-4.1":
                return (False, "heuristic")
            if model_name == "gpt-4o":
                return (True, "heuristic")
            return (False, "heuristic")

        with mock.patch.object(copilot_agent, "get_config", return_value=self.config), \
            mock.patch.object(copilot_agent, "_resolve_copilot_executable", return_value="copilot.cmd"), \
            mock.patch.object(copilot_agent, "_run_copilot_command", side_effect=_fake_run), \
            mock.patch.object(copilot_agent, "_validate_image_file_context", return_value=(True, "")), \
            mock.patch.object(copilot_agent, "_discover_copilot_cli_models", return_value=["gpt-4o"]), \
            mock.patch.object(copilot_agent, "_get_model_capability", side_effect=_capability_for), \
            mock.patch.object(copilot_agent, "_set_model_capability"):

            result = node.execute(
                prompt="Describe this image.",
                text_mode_enabled=False,
                text_mode="Off",
                image_mode_enabled=False,
                image_mode="Off",
                video_mode_enabled=False,
                video_mode="Off",
                tts_mode_enabled=False,
                tts_mode="Off",
                model="gpt-4.1",
                file_path=str(image_path),
                vision_enabled=True,
            )

        self.assertEqual(seen_models, ["gpt-4o"])
        self.assertNotIn("Automatically switched to vision-capable model 'gpt-4o'", result[0])
        self.assertNotIn("[Copilot Notice]", result[0])
        self.assertIn("The image shows a small UI layout with form fields.", result[0])

    def test_copilot_model_unavailable_retry_notice_not_in_response(self):
        node = copilot_agent.GZ_CopilotAgent()
        image_path = _write_png(pathlib.Path(self.temp_dir) / "model-unavailable-retry.png")
        run_count = {"value": 0}

        def _fake_run(*, executable_path, temp_dir, args, timeout_seconds, max_output_chars, stdin_text=""):
            run_count["value"] += 1
            if run_count["value"] == 1:
                return 1, "", "from --model flag is not available"
            return 0, "Vision response from fallback model.", ""

        with mock.patch.object(copilot_agent, "get_config", return_value=self.config), \
            mock.patch.object(copilot_agent, "_resolve_copilot_executable", return_value="copilot.cmd"), \
            mock.patch.object(copilot_agent, "_run_copilot_command", side_effect=_fake_run), \
            mock.patch.object(copilot_agent, "_validate_image_file_context", return_value=(True, "")), \
            mock.patch.object(copilot_agent, "_get_model_capability", return_value=(True, "runtime")), \
            mock.patch.object(copilot_agent, "_select_vision_retry_model", return_value="gpt-5-mini"):

            result = node.execute(
                prompt="Describe this image.",
                text_mode_enabled=False,
                text_mode="Off",
                image_mode_enabled=False,
                image_mode="Off",
                video_mode_enabled=False,
                video_mode="Off",
                tts_mode_enabled=False,
                tts_mode="Off",
                model="gpt-4o",
                file_path=str(image_path),
                vision_enabled=True,
            )

        self.assertEqual(run_count["value"], 2)
        self.assertEqual(result, ("Vision response from fallback model.",))
        self.assertNotIn("[Copilot Notice]", result[0])
        self.assertNotIn("was unavailable for this account", result[0])

    def test_copilot_timeout_retry_notice_not_in_response(self):
        node = copilot_agent.GZ_CopilotAgent()
        call_counter = {"value": 0}

        def _fake_run(*, executable_path, temp_dir, args, timeout_seconds, max_output_chars, stdin_text=""):
            call_counter["value"] += 1
            if call_counter["value"] == 1:
                raise subprocess.TimeoutExpired(args, timeout_seconds)
            return 0, "Recovered after timeout retry.", ""

        with mock.patch.object(copilot_agent, "get_config", return_value=self.config), \
            mock.patch.object(copilot_agent, "_resolve_copilot_executable", return_value="copilot.cmd"), \
            mock.patch.object(copilot_agent, "_run_copilot_command", side_effect=_fake_run):

            result = node.execute(
                prompt="Summarize this request.",
                text_mode_enabled=True,
                text_mode="Off",
                image_mode_enabled=False,
                image_mode="Off",
                video_mode_enabled=False,
                video_mode="Off",
                tts_mode_enabled=False,
                tts_mode="Off",
                model="gpt-5-mini",
            )

        self.assertEqual(call_counter["value"], 2)
        self.assertEqual(result, ("Recovered after timeout retry.",))
        self.assertNotIn("[Copilot Notice]", result[0])
        self.assertNotIn("Automatically retrying once with timeout", result[0])

    def test_copilot_model_capability_cache_is_session_only(self):
        copilot_agent._SESSION_MODEL_CAPABILITIES.clear()

        with mock.patch.object(copilot_agent, "_save_prefs") as save_mock:
            supports, source = copilot_agent._get_model_capability("gpt-4.1")
            self.assertFalse(supports)
            self.assertEqual(source, "heuristic")

            copilot_agent._set_model_capability("gpt-5-mini", True, "runtime")
            cached_supports, cached_source = copilot_agent._get_model_capability("gpt-5-mini")
            self.assertTrue(cached_supports)
            self.assertEqual(cached_source, "runtime")

        save_mock.assert_not_called()

    def test_copilot_pre_dispatch_reroutes_when_selected_model_not_listed(self):
        node = copilot_agent.GZ_CopilotAgent()
        seen_models = []

        def _fake_run(*, executable_path, temp_dir, args, timeout_seconds, max_output_chars, stdin_text=""):
            seen_models.append(args[args.index("--model") + 1])
            return 0, "Response from available model.", ""

        with mock.patch.object(copilot_agent, "get_config", return_value=self.config), \
            mock.patch.object(copilot_agent, "_resolve_copilot_executable", return_value="copilot.cmd"), \
            mock.patch.object(copilot_agent, "_run_copilot_command", side_effect=_fake_run), \
            mock.patch.object(copilot_agent, "_discover_copilot_cli_models", return_value=["gpt-5-mini"]):

            result = node.execute(
                prompt="Summarize this request.",
                text_mode_enabled=True,
                text_mode="Off",
                image_mode_enabled=False,
                image_mode="Off",
                video_mode_enabled=False,
                video_mode="Off",
                tts_mode_enabled=False,
                tts_mode="Off",
                model="gpt-4o",
            )

        self.assertEqual(seen_models, ["gpt-5-mini"])
        self.assertEqual(result, ("Response from available model.",))

    def test_copilot_strips_instruction_echo_lead_paragraph_from_response(self):
        node = copilot_agent.GZ_CopilotAgent()
        image_path = _write_png(pathlib.Path(self.temp_dir) / "instruction-echo-strip.png")
        lead = (
            "I'll open the reference image to study all visible details, then craft a single, "
            "dense descriptive paragraph (180-320 words) focused on subject, environment, lighting, "
            "and composition, written as a generation-ready prompt."
        )
        body = (
            "Wide-angle coastal city sunset seen from the shoreline, with the camera at low eye level "
            "where gentle waves lap against wet sand and mirror warm sky gradients across reflective water."
        )

        def _fake_run(*, executable_path, temp_dir, args, timeout_seconds, max_output_chars, stdin_text=""):
            return 0, f"{lead}\n\n{body}", ""

        with mock.patch.object(copilot_agent, "get_config", return_value=self.config), \
            mock.patch.object(copilot_agent, "_resolve_copilot_executable", return_value="copilot.cmd"), \
            mock.patch.object(copilot_agent, "_run_copilot_command", side_effect=_fake_run), \
            mock.patch.object(copilot_agent, "_validate_image_file_context", return_value=(True, "")), \
            mock.patch.object(copilot_agent, "_get_model_capability", return_value=(True, "runtime")):

            result = node.execute(
                prompt="Describe this image for generation.",
                text_mode_enabled=True,
                text_mode="Off",
                image_mode_enabled=False,
                image_mode="Off",
                video_mode_enabled=False,
                video_mode="Off",
                tts_mode_enabled=False,
                tts_mode="Off",
                model="gpt-5-mini",
                file_path=str(image_path),
                vision_enabled=True,
            )

        self.assertEqual(result, (body,))
        self.assertNotIn("I'll open the reference image", result[0])

    def test_shared_output_sanitizer_skips_stt_transcript_mode(self):
        transcript = (
            "00:00 Speaker 1: Welcome everyone.\n"
            "00:05 Speaker 2: Thanks for joining.\n"
            "00:09 Speaker 1: Let's begin."
        )

        sanitized = output_sanitizer.sanitize_text_output(transcript, mode_hint="speech_to_text")
        self.assertEqual(sanitized, transcript)

    def test_lm_studio_text_uses_shared_output_sanitizer(self):
        node = lm_studio_vision.GZ_LLMTextEnhancer()

        with mock.patch.object(lm_studio_vision, "get_config", return_value=self.config), \
            mock.patch.object(lm_studio_vision, "_check_lmstudio_connection", return_value=(True, "Connected")), \
            mock.patch.object(
                lm_studio_engine,
                "sanitize_text_output",
                return_value="sanitized-lmstudio-output",
            ) as sanitize_mock, \
            mock.patch.object(lm_studio_vision, "requests") as requests_mock:

            requests_mock.post.return_value = FakeResponse(
                json_data={"choices": [{"message": {"content": "raw-model-output"}}]}
            )

            result = node.execute(
                provider="LM Studio",
                prompt="Summarize this request.",
                text_mode_enabled=True,
                text_mode="Off",
                image_mode_enabled=False,
                image_mode="Off",
                video_mode_enabled=False,
                video_mode="Off",
                tts_mode_enabled=False,
                tts_mode="Off",
                model="gpt-4.1 [local]",
                unload_lm_studio=False,
                unload_ollama=False,
            )

        self.assertEqual(result, ("sanitized-lmstudio-output",))
        sanitize_mock.assert_called_once()

    def test_pollinations_text_uses_shared_output_sanitizer(self):
        node = pollinations_text.GZ_TextEnhancer()

        with mock.patch.object(pollinations_text, "get_config", return_value=self.config), \
            mock.patch.object(
                pollinations_text,
                "sanitize_text_output",
                return_value="sanitized-pollinations-output",
            ) as sanitize_mock, \
            mock.patch.object(
                pollinations_text,
                "execute_with_compat_retry",
                return_value=FakeResponse(json_data={"choices": [{"message": {"content": "raw"}}]}),
            ):

            result = node.execute(
                prompt="Enhance this text.",
                text_mode_enabled=True,
                text_mode="Off",
                image_mode_enabled=False,
                image_mode="Off",
                video_mode_enabled=False,
                video_mode="Off",
                tts_mode_enabled=False,
                tts_mode="Off",
                model="openai [text] [vision] [free]",
            )

        self.assertEqual(result, ("sanitized-pollinations-output",))
        sanitize_mock.assert_called_once()

    def test_openai_compatible_text_uses_shared_output_sanitizer(self):
        node = openai_compatible_text_enhancer.GZ_OpenAICompatibleTextEnhancer()

        with mock.patch.object(openai_compatible_engine, "get_config", return_value=self.config), \
            mock.patch.object(
                openai_compatible_engine,
                "sanitize_text_output",
                return_value="sanitized-openai-compatible-output",
            ) as sanitize_mock, \
            mock.patch.object(openai_compatible_engine, "requests") as requests_mock:

            requests_mock.post.return_value = FakeResponse(
                json_data={"choices": [{"message": {"content": "raw-compatible-output"}}]}
            )

            result = node.execute(
                active_engine="text",
                prompt="Write a concise answer.",
                model="gpt-4.1-mini",
                require_api_key=False,
            )

        self.assertEqual(result[0], "sanitized-openai-compatible-output")
        sanitize_mock.assert_called_once()

    def test_run_copilot_command_creates_temp_dir_and_cleans_temp_logs(self):
        missing_temp_dir = pathlib.Path(self.temp_dir) / "missing" / "copilot-temp"
        self.assertFalse(missing_temp_dir.exists())

        with mock.patch.object(
            copilot_agent,
            "_prepare_copilot_command",
            return_value=([sys.executable, "-c", ""], None),
        ):
            code, stdout_text, stderr_text = copilot_agent._run_copilot_command(
                executable_path="copilot.cmd",
                temp_dir=str(missing_temp_dir),
                args=[],
                timeout_seconds=5,
                max_output_chars=1024,
            )

        self.assertEqual(code, 0)
        self.assertIsInstance(stdout_text, str)
        self.assertEqual(stderr_text, "")
        self.assertTrue(missing_temp_dir.exists())
        self.assertEqual(list(missing_temp_dir.glob("overtli_copilot_stdout_*.log")), [])
        self.assertEqual(list(missing_temp_dir.glob("overtli_copilot_stderr_*.log")), [])

    def test_copilot_errors_when_no_vision_fallback_model_is_available(self):
        node = copilot_agent.GZ_CopilotAgent()
        image_path = _write_png(pathlib.Path(self.temp_dir) / "vision-no-fallback.png")

        with mock.patch.object(copilot_agent, "get_config", return_value=self.config), \
            mock.patch.object(copilot_agent, "_resolve_copilot_executable", return_value="copilot.cmd"), \
            mock.patch.object(copilot_agent, "_validate_image_file_context", return_value=(True, "")), \
            mock.patch.object(copilot_agent, "_discover_copilot_cli_models", return_value=[]), \
            mock.patch.object(copilot_agent, "_build_model_options", return_value=["gpt-4.1"]), \
            mock.patch.object(copilot_agent, "_get_model_capability", return_value=(False, "heuristic")):

            with self.assertRaises(exceptions.OvertliModelError) as ctx:
                node.execute(
                    prompt="Describe this image.",
                    text_mode_enabled=False,
                    text_mode="Off",
                    image_mode_enabled=False,
                    image_mode="Off",
                    video_mode_enabled=False,
                    video_mode="Off",
                    tts_mode_enabled=False,
                    tts_mode="Off",
                    model="gpt-4.1",
                    file_path=str(image_path),
                    vision_enabled=True,
                )

        self.assertIn("does not support image analysis", str(ctx.exception).lower())

    def test_copilot_errors_when_retry_cached_vision_models_is_disabled(self):
        node = copilot_agent.GZ_CopilotAgent()
        image_path = _write_png(pathlib.Path(self.temp_dir) / "vision-retry-disabled.png")

        with mock.patch.object(copilot_agent, "get_config", return_value=self.config), \
            mock.patch.object(copilot_agent, "_resolve_copilot_executable", return_value="copilot.cmd"), \
            mock.patch.object(copilot_agent, "_validate_image_file_context", return_value=(True, "")), \
            mock.patch.object(copilot_agent, "_get_model_capability", return_value=(False, "heuristic")):

            with self.assertRaises(exceptions.OvertliModelError) as ctx:
                node.execute(
                    prompt="Describe this image.",
                    text_mode_enabled=False,
                    text_mode="Off",
                    image_mode_enabled=False,
                    image_mode="Off",
                    video_mode_enabled=False,
                    video_mode="Off",
                    tts_mode_enabled=False,
                    tts_mode="Off",
                    model="gpt-4.1",
                    file_path=str(image_path),
                    vision_enabled=True,
                    retry_cached_vision_models=False,
                )

        self.assertIn("does not support image analysis", str(ctx.exception).lower())


class TestPollinationsNodeBehaviors(BehaviorTestCase):
    def test_text_enhancer_supports_image_context_and_persistent_api_key(self):
        node = pollinations_text.GZ_TextEnhancer()
        captured = {}

        def _fake_retry(**kwargs):
            captured["payload"] = kwargs["payload"]
            return FakeResponse(json_data={"choices": [{"message": {"content": "vision answer"}}]})

        with mock.patch.object(pollinations_text, "get_config", return_value=self.config), \
            mock.patch.object(
                pollinations_text,
                "get_pollinations_model_entry",
                return_value={"vision": True, "input_modalities": ["text", "image"]},
            ), \
            mock.patch.object(pollinations_text, "execute_with_compat_retry", side_effect=_fake_retry), \
            mock.patch.object(pollinations_text, "comfy_image_to_base64", return_value="data:image/png;base64,abcd"), \
            mock.patch.object(pollinations_text, "save_persistent_settings") as save_mock:

            result = node.execute(
                prompt="Explain what you see.",
                text_mode_enabled=True,
                text_mode="Off",
                image_mode_enabled=False,
                image_mode="Off",
                video_mode_enabled=False,
                video_mode="Off",
                tts_mode_enabled=False,
                tts_mode="Off",
                model="openai [vision]",
                image=_make_image_tensor(),
                api_key="pollinations-key",
                persist_api_key=True,
            )

        self.assertEqual(result, ("vision answer",))
        content = captured["payload"]["messages"][-1]["content"]
        self.assertEqual(content[0]["text"], "Explain what you see.")
        self.assertEqual(content[1]["image_url"]["url"], "data:image/png;base64,abcd")
        save_mock.assert_called_once()

    def test_image_gen_validates_img2img_and_returns_comfy_image(self):
        node = pollinations_image.GZ_ImageGen()

        with self.assertRaises(exceptions.OvertliInputError):
            node.execute(
                prompt="Generate",
                mode_preset="Off",
                model="flux [image-gen] [free]",
                width=512,
                height=512,
                image=_make_image_tensor(),
            )

        with mock.patch.object(pollinations_image, "get_config", return_value=self.config), \
            mock.patch.object(
                pollinations_image,
                "execute_with_compat_retry",
                return_value=FakeResponse(headers={"content-type": "image/png"}, content=PNG_BYTES),
            ), \
            mock.patch.object(pollinations_image, "binary_to_comfy_image", return_value=_make_image_tensor()), \
            mock.patch.object(pollinations_image, "save_persistent_settings") as save_mock:

            result = node.execute(
                prompt="Generate",
                mode_preset="Off",
                model="gptimage [image-gen] [img2img]",
                width=512,
                height=512,
                image=None,
                api_key="img-key",
                persist_api_key=True,
            )

        self.assertTrue(hasattr(result[0], "shape"))
        save_mock.assert_called_once()

    def test_video_gen_returns_video_wrapper(self):
        node = pollinations_video.GZ_VideoGen()
        stale_temp = pathlib.Path(tempfile.gettempdir()) / "overtli_pollinations_video_stale.mp4"
        stale_temp.write_bytes(b"stale-bytes")
        old_epoch = pollinations_video.time.time() - (pollinations_video._VIDEO_TEMP_MAX_AGE_SECONDS + 3600)
        os.utime(stale_temp, (old_epoch, old_epoch))

        with mock.patch.object(pollinations_video, "get_config", return_value=self.config), \
            mock.patch.object(
                pollinations_video,
                "execute_with_compat_retry",
                return_value=FakeResponse(headers={"content-type": "video/mp4"}, content=b"fake-video-bytes"),
            ):

            result = node.execute(
                prompt="Animate this.",
                mode_preset="Off",
                model="wan-fast [video-gen]",
                width=512,
                height=512,
            )

        self.assertTrue(hasattr(result[0], "path"))
        self.assertTrue(os.path.exists(result[0].path))
        self.assertFalse(stale_temp.exists())
        os.remove(result[0].path)

    def test_text_to_speech_formats_script_and_returns_audio_output(self):
        node = pollinations_tts.GZ_TextToSpeech()

        with mock.patch.object(pollinations_tts, "get_config", return_value=self.config), \
            mock.patch.object(
                pollinations_tts,
                "execute_with_compat_retry",
                return_value=FakeResponse(headers={"content-type": "audio/mpeg"}, content=b"mp3-data"),
            ), \
            mock.patch.object(
                pollinations_tts.requests,
                "post",
                return_value=FakeResponse(json_data={"choices": [{"message": {"content": "Formatted script"}}]}),
            ), \
            mock.patch.object(pollinations_tts, "save_persistent_settings") as save_mock:

            audio_output, script_text = node.execute(
                text="Original script",
                mode_preset="Off",
                model="openai-audio [speech]",
                voice="nova",
                format_script=True,
                api_key="tts-key",
                persist_api_key=True,
            )

        self.assertEqual(script_text, "Formatted script")
        self.assertIn("waveform", audio_output)
        self.assertEqual(audio_output["sample_rate"], 16000)
        save_mock.assert_called_once()

    def test_speech_to_text_accepts_audio_dict_and_refines_transcript(self):
        node = pollinations_stt.GZ_SpeechToText()
        audio_input = {
            "waveform": TORCH.zeros((1, 1, 800), dtype=TORCH.float32),
            "sample_rate": 16000,
        }

        with mock.patch.object(pollinations_stt, "get_config", return_value=self.config), \
            mock.patch.object(
                pollinations_stt.requests,
                "post",
                side_effect=[
                    FakeResponse(text="raw transcript", headers={"content-type": "text/plain"}),
                    FakeResponse(json_data={"choices": [{"message": {"content": "refined transcript"}}]}),
                ],
            ), \
            mock.patch.object(pollinations_stt, "save_persistent_settings") as save_mock:

            result = node.execute(
                model="whisper [stt]",
                mode_preset="📝 Enhance",
                response_format="text",
                audio=audio_input,
                custom_instructions="Clean it up.",
                api_key="stt-key",
                persist_api_key=True,
            )

        self.assertEqual(result, ("refined transcript",))
        save_mock.assert_called_once()

    def test_text_to_audio_forces_music_model_and_returns_audio(self):
        node = pollinations_ttaudio.GZ_TextToAudio()

        with mock.patch.object(pollinations_ttaudio, "get_config", return_value=self.config), \
            mock.patch.object(
                pollinations_ttaudio,
                "execute_with_compat_retry",
                return_value=FakeResponse(headers={"content-type": "audio/mpeg"}, content=b"music-bytes"),
            ), \
            mock.patch.object(pollinations_ttaudio, "save_persistent_settings") as save_mock:

            result = node.execute(
                text="Create a short cinematic cue.",
                mode_preset="Off",
                model="openai-audio [speech]",
                api_key="music-key",
                persist_api_key=True,
            )

        self.assertIn("waveform", result[0])
        self.assertEqual(result[0]["sample_rate"], 16000)
        save_mock.assert_called_once()
