"""Behavioral regressions for director contracts and provider lifecycle."""
import importlib
import json
from pathlib import Path
import sys
import tempfile
import types
from unittest.mock import Mock, patch

import pytest
import requests

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = "overtli_director_contract_tests"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT)]
sys.modules[PACKAGE] = package
director = importlib.import_module(PACKAGE + ".director")
llm = importlib.import_module(PACKAGE + ".engine.llm_text_enhancer")
catalog = importlib.import_module(PACKAGE + ".engine.pollinations.model_catalog")
migration = importlib.import_module(PACKAGE + ".workflow_migration")
media = importlib.import_module(PACKAGE + ".media_nodes")
settings = importlib.import_module(PACKAGE + ".settings_store")
budgets = importlib.import_module(PACKAGE + ".prompt_budgets")
preflight = importlib.import_module(PACKAGE + ".prompt_preflight")


def test_connections_preserve_blank_password_but_explicitly_clear_key_and_url(tmp_path):
    destination = tmp_path / "settings.json"
    with patch.object(settings, "get_settings_path", return_value=str(destination)), patch.object(settings, "_CACHE_DATA", None), patch.object(settings, "_CACHE_MTIME", None):
        settings.save_persistent_settings({"lmstudio_api_key": "fixture-key", "lmstudio_base_url": "http://fixture:1234"})
        director.save_connections({"lmstudio_api_key": ""})
        assert settings.get_persistent_setting("lmstudio_api_key") == "fixture-key"
        director.save_connections({"lmstudio_base_url": "", "clear_keys": ["lmstudio_api_key"]})
        persisted = json.loads(destination.read_text())
        assert persisted["lmstudio_api_key"] == ""
        assert persisted["lmstudio_base_url"] == ""


def test_provider_configuration_honors_environment_before_persisted_values():
    with patch.dict("os.environ", {"OLLAMA_HOST": "http://environment:11434", "OLLAMA_API_KEY": "environment-key"}), patch.object(settings, "get_persistent_setting", return_value="persisted"):
        assert director._provider_config("Ollama") == ("http://environment:11434", "environment-key")


def response(data):
    result = Mock()
    result.json.return_value = data
    result.raise_for_status.return_value = None
    return result


def test_constants_replace_trailing_block_once_and_preserve_disabled_text():
    original = "subject_definitions:\nKeep dialogue exactly.\n\n[Constant]\nold"
    result = director.append_constant(original, "[Constant]\nnew")
    assert result.count("[Constant]") == 1
    assert result.endswith("[Constant]\nnew")
    assert director.append_constant(result, "new") == result
    assert director.append_constant(original, "new", False) == original


def test_inline_draft_stays_raw_and_final_composes_once():
    state = {"enabled": True, "promptOverrideEnabled": True, "promptOverride": "stale override",
             "guide": "H3 Ref2VA", "constantPrompt": "constant", "customStyle": "style"}
    with patch.object(director, "enhance_prompt", return_value="enhanced authoring") as enhancement:
        draft, final = director.enhancement_draft("original authoring", state)
    enhancement.assert_called_once_with("original authoring", state)
    assert draft == "enhanced authoring"
    assert final.count("enhanced authoring") == final.count("style") == final.count("[Constant]") == 1
    assert "stale override" not in final
    assert director.prepare_prompt(draft, {**state, "enabled": False, "promptOverrideEnabled": False}) == final


def test_inline_draft_rejects_empty_and_over_budget_without_source_change():
    state = {"guide": "H3 Ref2VA", "constantPrompt": "constant"}
    with patch.object(director, "enhance_prompt", return_value=""):
        with pytest.raises(ValueError, match="empty draft"):
            director.enhancement_draft("preserved authoring", state)
    with patch.object(director, "enhance_prompt", return_value="a" * 7000):
        with pytest.raises(ValueError, match="7,000"):
            director.enhancement_draft("preserved authoring", state)


def test_reference_numbering_is_independent_and_invalid_tags_are_errors():
    prompt = "\n".join(x + ": content" for x in director.H3_REF_FIELDS) + "\n[Shot 1] <Picture 2> <Video 1> <Audio 1>"
    checks = director.check_prompt(prompt, "H3 Ref2VA", "<Picture 1> <Picture 2> <Video 1> <Audio 1>")
    assert not checks["errors"]
    assert not checks["warnings"]
    checks = director.check_prompt(prompt + " <Video 2>", "H3 Ref2VA", "<Picture 1> <Picture 2> <Video 1> <Audio 1>")
    assert checks["errors"] == ["Inactive references: <Video 2>"]


def test_h3_base_grammar_and_cut_duration_are_checked():
    prompt = "\n".join(x + ": content" for x in director.H3_BASE_FIELDS) + "\n[Shot 1]\n[Shot 2] At 00:04.000, cut."
    assert not director.check_prompt(prompt, "H3 Base", duration=5)["warnings"]
    assert director.check_prompt(prompt, "H3 Base", duration=3)["warnings"]
    assert director.check_prompt(prompt, "H3 Ref2VA")["warnings"]


def test_lmstudio_unloads_selected_instances_and_preserves_other_models():
    loaded = {"models": [{"key": "selected", "loaded_instances": [{"id": "target-instance"}]}, {"key": "other", "loaded_instances": [{"id": "keep-instance"}]}]}
    remaining = {"models": [loaded["models"][1]]}
    with patch.object(llm.requests, "get", side_effect=[response(loaded), response(remaining)]) as get, patch.object(llm.requests, "post", return_value=response({})) as post:
        llm._unload_model("selected", "http://localhost:1234/api/v1/models/unload", {"Authorization": "Bearer test-key"})
        assert post.call_args.kwargs["json"] == {"instance_id": "target-instance"}
        assert get.call_args.args[0].endswith("/api/v1/models")
        assert post.call_count == 1


def test_lmstudio_does_not_report_success_while_target_is_loaded():
    loaded = {"models": [{"key": "selected", "loaded_instances": [{"id": "target-instance"}]}]}
    with patch.object(llm.requests, "get", return_value=response(loaded)), patch.object(llm.requests, "post", return_value=response({})), patch.object(llm.time, "sleep"):
        with pytest.raises(llm.OvertliModelError, match="still reports"):
            llm._unload_model("selected", "http://localhost:1234/api/v1/models/unload")


def test_ollama_unload_uses_native_empty_generate_and_verifies_ps():
    with patch.object(llm.requests, "post", return_value=response({})) as post, patch.object(llm.requests, "get", return_value=response({"models": [{"name": "other:latest"}]})) as get:
        llm._unload_ollama_model("selected", "http://localhost:11434/v1/chat/completions", {"Authorization": "Bearer test-key"})
        assert post.call_args.args[0] == "http://localhost:11434/api/generate"
        assert post.call_args.kwargs["json"]["keep_alive"] == 0
        assert post.call_args.kwargs["json"]["prompt"] == ""
        assert post.call_args.kwargs["headers"] == {"Authorization": "Bearer test-key"}
        assert get.call_args.args[0].endswith("/api/ps")


def test_pollinations_caches_failures_instead_of_repolling():
    with patch.object(catalog, "_CACHE_TS", 0), patch.object(catalog, "_CACHE_MODELS", []), patch.object(catalog.requests, "get", side_effect=requests.ConnectionError("offline")) as get:
        catalog._fetch_catalog()
        calls = get.call_count
        assert calls > 0
        catalog._fetch_catalog()
        assert get.call_count == calls


def test_studio_schema_never_discovers_models_or_sends_inference():
    with patch.object(director, "discover_models") as discovery, patch.object(director, "enhance_prompt") as enhancement:
        director.OvertliStudioSuite.INPUT_TYPES()
        result = director.OvertliStudioSuite().execute("authored", json.dumps({"constantPrompt": "quality"}))
        assert result[0].endswith("[Constant]\nquality")
        discovery.assert_not_called()
        enhancement.assert_not_called()


def test_model_discovery_caches_errors_and_explicit_refresh_retries():
    with patch.object(director, "_MODEL_CACHE", {}), patch.object(director, "_provider_config", return_value=("http://localhost", "")), patch.object(director.requests, "get", side_effect=requests.ConnectionError()) as get:
        assert director.discover_models("Pollinations")["error"]
        director.discover_models("Pollinations")
        assert get.call_count == 1
        director.discover_models("Pollinations", True)
        assert get.call_count == 2


def test_blank_stored_endpoints_use_local_defaults():
    with patch.object(director, "get_persistent_setting", return_value=""):
        assert director._provider_config("LM Studio")[0] == "http://127.0.0.1:1234"
        assert director._provider_config("Ollama")[0] == "http://127.0.0.1:11434"


def test_lm_native_chat_uses_final_message_and_unloads_in_finally():
    catalog_payload = {"models": [{"key":"model", "max_context_length":32768, "capabilities":{"reasoning":{"allowed_options":["off","on"]}}}]}
    chat = response({"output":[{"type":"reasoning", "content":"private thinking"},{"type":"message", "content":"final prompt"}]})
    with patch.object(director, "_provider_config", return_value=("http://localhost", "")), patch.object(director.requests, "get", return_value=response(catalog_payload)), patch.object(director.requests, "post", return_value=chat) as post, patch.object(llm, "_unload_model") as unload:
        result = director.enhance_prompt("original", {"model":"model", "guide":"FLUX.2 Klein 9B"})
        assert result == "final prompt"
        assert post.call_args.kwargs["json"]["reasoning"] == "off"
        assert post.call_args.kwargs["json"]["store"] is False
        assert post.call_args.kwargs["json"]["context_length"] >= 8192
        unload.assert_called_once()


def test_h3_budget_counts_utf16_and_preserves_oversized_text():
    assert not budgets.prompt_budget("a" * 7000, "H3 Ref2VA")["errors"]
    assert budgets.prompt_budget("a" * 7001, "H3 Ref2VA")["errors"]
    assert budgets.prompt_budget("a" * 6999 + "\U0001f600", "H3 Ref2VA")["utf16_units"] == 7001
    with pytest.raises(ValueError, match="7,000"):
        director.prepare_prompt("a" * 6990, {"constantPrompt":"more than the remaining budget"})


def test_flux_target_is_warning_and_qwen_has_no_character_cap():
    with patch.object(budgets, "_tokenizer", return_value=Mock(encode=Mock(return_value=list(range(513))))):
        flux = budgets.prompt_budget("prompt", "FLUX.2 Klein 9B", "fixture")
        assert not flux["errors"] and flux["warnings"] and flux["tokens"] == 513
        qwen = budgets.prompt_budget("a" * 7001, "Qwen Image 2.1", "fixture")
        assert not qwen["errors"] and not qwen["warnings"]


def test_encoder_position_limit_rejects_before_encoding():
    with pytest.raises(ValueError, match="40,960"):
        budgets.validate_encoder_positions({"qwen3_8b":[[0]*40961]}, "FLUX.2 Klein 9B")


def test_styles_constants_and_library_recipe_round_trip_without_credentials(tmp_path):
    from importlib import import_module
    style_api = import_module(PACKAGE + ".styles")
    label = style_api.get_style_options()[1]
    output = director.prepare_prompt("authored", {"styles":[label,label],"customStyle":"golden lighting","constantPrompt":"quality"})
    assert output.count("Style requirements:") == 1
    assert output.endswith("[Constant]\nquality") and "golden lighting" in output
    path = tmp_path / "library.json"
    with patch.object(director.library,"get_prompt_library_path",return_value=str(path)), patch.object(director.library,"_CACHE_DATA",None), patch.object(director.library,"_CACHE_MTIME",None):
        director.library.upsert_prompt_entry("fixture", "authored", studio={"styles":[label],"constantPrompt":"quality","constantEnabled":False,"api_key":"must-not-save"})
        entry = director.library.get_prompt_entry("fixture")
        assert entry["studio"]["styles"] == [label] and entry["studio"]["constantEnabled"] is False
        assert "must-not-save" not in path.read_text()


def test_preflight_uses_pure_prompt_producers_and_never_loads_models():
    stack = Mock();stack.prompt_plan.return_value = '{"items":[]}'
    class Prefix:
        FUNCTION="apply"
        def apply(self,prompt,prefix,placement): return (prompt+"\ntrigger",)
    graph={"1":{"class_type":"PixaromaText","inputs":{"text":"authored"}},"2":{"class_type":"OvertliStudioSuite","inputs":{"prompt":["1",0],"state":'{"constantPrompt":"quality"}'}},"3":{"class_type":"OvertliH3OptionalLoRAStack","inputs":{"model":["heavy",0],"profile_1":"None"}},"4":{"class_type":"OvertliH3PromptPrefix","inputs":{"prompt":["2",0],"prefix":["3",1],"placement":"Smart prefix"}},"5":{"class_type":"OvertliH3ReferenceConditioning","inputs":{"prompt":["4",0]}}}
    result=preflight.inspect_prompts(graph,{"OvertliStudioSuite":director.OvertliStudioSuite,"OvertliH3OptionalLoRAStack":stack,"OvertliH3PromptPrefix":Prefix})
    assert result["complete"] and result["prompts"][0]["prompt"].endswith("quality\ntrigger")
    stack.prompt_plan.assert_called_once_with(profile_1="None")
    stack.apply.assert_not_called()


def test_preview_and_identical_run_reuse_enhancement_but_edits_invalidate():
    with patch.object(director,"_PROMPT_CACHE",{}),patch.object(director,"enhance_prompt",side_effect=lambda p,s:p+" enhanced") as enhance,patch.object(director,"_provider_config",return_value=("fixture","")):
        state={"enabled":True,"model":"fixture"}
        assert director.prepare_prompt("authored",state)==director.OvertliStudioSuite().execute("authored",state)[0]
        assert enhance.call_count==1
        director.prepare_prompt("edited",state)
        assert enhance.call_count==2


def test_ollama_native_chat_context_and_finally_unload():
    with patch.object(director,"_provider_config",return_value=("http://fixture:11434","")),patch.object(director.requests,"post",return_value=response({"message":{"content":"final"}})) as post,patch.object(llm,"_unload_ollama_model") as unload:
        assert director.enhance_prompt("authored",{"provider":"Ollama","model":"fixture","guide":"FLUX.2 Klein 9B"})=="final"
        assert post.call_args.args[0].endswith("/api/chat")
        assert post.call_args.kwargs["json"]["options"]["num_ctx"]>=8192
        assert post.call_args.kwargs["json"]["options"]["num_predict"]==2048
        unload.assert_called_once()


def test_lm_native_failure_still_unloads():
    catalog_payload = {"models": [{"key":"model", "max_context_length":32768}]}
    with patch.object(director, "_provider_config", return_value=("http://localhost", "")), patch.object(director.requests, "get", return_value=response(catalog_payload)), patch.object(director.requests, "post", side_effect=requests.ConnectionError()), patch.object(llm, "_unload_model") as unload:
        with pytest.raises(requests.ConnectionError):
            director.enhance_prompt("original", {"model":"model", "guide":"FLUX.2 Klein 9B"})
        unload.assert_called_once()


def test_native_model_catalog_preserves_explicit_keys_and_filters_embeddings():
    payload = {"models": [{"type":"llm", "key":"author/model@q5", "display_name":"Model"}, {"type":"embedding", "key":"embed"}]}
    with patch.object(director, "_MODEL_CACHE", {}), patch.object(director, "_provider_config", return_value=("http://localhost", "")), patch.object(director.requests, "get", return_value=response(payload)):
        assert director.discover_models("LM Studio")["models"] == [{"id":"author/model@q5", "label":"Model"}]


def test_migration_preserves_authored_text_and_legacy_loras_and_is_idempotent():
    prompt = {"id":1,"type":"PixaromaText","title":"REFERENCE PROMPT - SIX-SECTION REF2VA","pos":[0,0],"widgets_values":["authored dialogue"],"outputs":[{"name":"text","type":"STRING","links":[1]}]}
    stack = {"id":2,"type":"OvertliH3OptionalLoRAStack","widgets_values":["selected",.75,"None",.25,"None",.1],"inputs":[]}
    workflow = {"nodes":[prompt,stack],"links":[[1,1,0,2,0,"STRING"]]}
    migration.upgrade_director_workflow(workflow)
    assert prompt["widgets_values"] == ["authored dialogue"]
    assert stack["widgets_values"][:6] == ["selected",.75,"None",.25,"None",.1]
    assert len(stack["widgets_values"]) == 10
    before = json.dumps(workflow,sort_keys=True)
    migration.upgrade_director_workflow(workflow)
    assert json.dumps(workflow,sort_keys=True) == before


def test_addtl_staging_preserves_original_and_resolves_name_collision():
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory); (root/"reference.png").write_bytes(b"source")
        destination=root/"OvertliDS/addtl";destination.mkdir(parents=True)
        (destination/"reference.png").write_bytes(b"different")
        receipts=[]
        staged=migration._stage_reference("reference.png",root,receipts)
        assert staged.startswith("OvertliDS/addtl/reference_")
        assert (root/staged).read_bytes()==b"source"
        assert (root/"reference.png").read_bytes()==b"source"
        assert (destination/"reference.png").read_bytes()==b"different"
        assert receipts[0]["sha256"]


def test_addtl_media_schema_lists_nested_files_only():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "ordinary.png").write_bytes(b"ordinary")
        island = root / "OvertliDS/addtl/subfolder"
        island.mkdir(parents=True)
        (island / "reference.png").write_bytes(b"island")
        (island / "reference.mp4").write_bytes(b"video")
        assert media.scoped_media_files(root, {".png"}) == ["OvertliDS/addtl/subfolder/reference.png"]
        assert media.scoped_media_files(root, {".mp4"}) == ["OvertliDS/addtl/subfolder/reference.mp4"]
