"""Shared director prompt contract and on-demand provider services.

Credentials live in the existing local settings store, never in workflow JSON.
Model discovery and inference are explicit operations, not schema-time polling.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import time

import requests

from . import prompt_library_store as library
from .settings_store import get_persistent_setting, resolve_config_value, save_persistent_settings
from .prompt_budgets import prompt_budget, validate_prompt_budget

DEFAULT_CONSTANT = "Masterpiece cinematic 8k resolution, photorealistic. Maintaining absolute character consistency and facial structure throughout the shot. Seamless, fluid, and natural human movement, strictly respecting real-world physics, biological anatomy, and natural weight distribution. Perfect anatomy, correct proportions, no morphing, no extra limbs, no warping. Ultra-detailed textures, realistic skin pores, cinematic professional lighting, highly detailed environment."
H3_REF_FIELDS = ("subject_definitions", "summary", "retention_analysis", "detailed_description", "overall_soundscape", "non_diegetic_music")
H3_BASE_FIELDS = ("integrated_multimodal_description", "overall_soundscape", "non_diegetic_music")
PROVIDERS = ("LM Studio", "Ollama", "Codex", "Pollinations", "OpenAI-compatible")
_MODEL_CACHE = {}
_MODEL_LOCK = threading.Lock()
_LIBRARY_LOCK = threading.Lock()
_ADDTL_LIBRARY = None
_PROMPT_CACHE = {}
_PROMPT_LOCK = threading.RLock()


def compose_styles(prompt, state):
    from .styles import get_style_metadata, resolve_style_instruction_stack
    labels = list(dict.fromkeys(str(x) for x in state.get("styles", []) if str(x).strip()))[:7]
    unknown = [x for x in labels if not get_style_metadata(x)]
    if unknown:
        raise ValueError("Unknown style preset: " + ", ".join(unknown))
    stack = resolve_style_instruction_stack(labels, "video" if str(state.get("guide", "H3")).startswith("H3") else "image")
    custom = str(state.get("customStyle") or "").strip()
    block = "\n\n".join(x for x in (stack, custom) if x)
    if not block:
        return str(prompt)
    parts = re.split(r"(?im)^\s*\[Constant\]\s*$", str(prompt), maxsplit=1)
    text = parts[0].rstrip() + "\n\n" + block
    return text + ("\n\n[Constant]\n" + parts[1].strip() if len(parts) > 1 else "")


def prepare_prompt(prompt, state, force_enhance=False):
    if state.get("promptOverrideEnabled", False):
        prompt = str(state.get("promptOverride") or "")
    styled = compose_styles(str(prompt), state)
    if state.get("enabled", False) or force_enhance:
        # A preview and its identical next run share one resolved enhancement.
        # Keys include connection settings; credentials never leave this process.
        identity = json.dumps([styled, state, _provider_config(state.get("provider", "LM Studio"))], sort_keys=True)
        key = hashlib.sha256(identity.encode()).hexdigest()
        with _PROMPT_LOCK:
            cached = _PROMPT_CACHE.get(key)
            if cached and time.monotonic() - cached[0] < 600:
                styled = cached[1]
            else:
                styled = enhance_prompt(styled, state)
                if len(_PROMPT_CACHE) >= 16:
                    _PROMPT_CACHE.pop(next(iter(_PROMPT_CACHE)))
                _PROMPT_CACHE[key] = (time.monotonic(), styled)
    final = append_constant(styled, state.get("constantPrompt", ""), state.get("constantEnabled", True))
    validate_prompt_budget(final, state.get("guide", "H3 Ref2VA"))
    return final


def append_constant(prompt, constant="", enabled=True):
    prompt = str(prompt or "").strip()
    constant = re.sub(r"^\s*\[Constant\]\s*", "", str(constant or ""), flags=re.I).strip()
    # The separate editable constant owns the trailing block; avoid repeated appends.
    if not enabled or not constant:
        return prompt
    prompt = re.split(r"(?im)^\s*\[Constant\]\s*$", prompt, maxsplit=1)[0].rstrip()
    return prompt + ("\n\n" if prompt else "") + "[Constant]\n" + constant


def check_prompt(prompt, guide="H3 Ref2VA", reference_tags="", duration=None):
    prompt = str(prompt or "")
    errors, warnings = [], []
    if not prompt.strip():
        errors.append("Prompt is empty.")
    if guide.startswith("H3"):
        fields = H3_REF_FIELDS if "Ref" in guide else H3_BASE_FIELDS
        found = re.findall(r"(?im)^\s*([a-z_]+)\s*:", prompt)
        core = [x for x in found if x in set(H3_REF_FIELDS + H3_BASE_FIELDS)]
        if core != list(fields):
            warnings.append("Expected exactly these fields in order: " + ", ".join(fields))
        if "[Shot 1]" not in prompt:
            warnings.append("Chronological description should establish [Shot 1].")
        used = set(re.findall(r"<(Picture|Video|Audio)\s+(\d+)>", prompt, re.I))
        allowed = {(k.lower(), int(n)) for k, n in re.findall(r"<(Picture|Video|Audio)\s+(\d+)>", reference_tags, re.I)}
        if reference_tags:
            unknown = [f"<{k.title()} {n}>" for k, n in used if (k.lower(), int(n)) not in allowed]
            if unknown:
                errors.append("Inactive references: " + ", ".join(sorted(unknown)))
        cuts = [int(m)*60 + float(s) for m, s in re.findall(r"At\s+(\d{2}):(\d{2}(?:\.\d+)?)", prompt, re.I)]
        if cuts != sorted(cuts):
            warnings.append("Cut timestamps are not chronological.")
        if duration and any(t >= float(duration) for t in cuts):
            warnings.append("A cut is at or beyond the target duration.")
    elif "Qwen" in guide and re.search(r"(?:image|reference)\s+[2-9]", prompt, re.I) and "REFERENCE" not in prompt.upper():
        warnings.append("Multiple references should have explicit attribute authority and preserve/change roles.")
    budget = prompt_budget(prompt, guide)
    errors.extend(budget["errors"]); warnings.extend(budget["warnings"])
    return {"guide": guide, "errors": errors, "warnings": warnings, "characters": len(prompt), "estimated_tokens": math.ceil(len(prompt)/4), "token_count_kind": "estimate (characters / 4); provider tokenizer may differ", "budget": budget}


def guide_instructions(guide):
    path = Path(__file__).parent / "guides" / ("minimax_h3.md" if guide.startswith("H3") else "image_director.md")
    text = path.read_text(encoding="utf-8")
    text += "\n\nFINAL PROMPT BUDGET: " + ("The Director uses a 7000 UTF-16-unit hosted-compatible H3 budget, including all headers, clip notes, LoRA triggers, styles and constants. Aim under 6000 to leave composition headroom. Preserve meaning and references; do not silently truncate. Local H3's encoder does not itself impose this character cap." if guide.startswith("H3") else "FLUX.2 Klein's reference encoder truncates at 512 tokens including template tokens: target concise prompts under that budget. Local ComfyUI instead pads to 512 and supports longer sequences. Qwen Image 2.1 has no verified character cap; reference-image tokens share its context. These are tokenizer limits, not a fixed character conversion.")
    fields = H3_REF_FIELDS if "Ref" in guide else H3_BASE_FIELDS
    contract = ("Use exactly these fields in order: " + ", ".join(fields)) if guide.startswith("H3") else ("Use concise explicit prose for FLUX, structured attribute-level reference authority for Qwen.")
    return "You are a prompt editor. Return ONLY the improved prompt. Preserve all user intent, dialogue, supplied reference numbering, and the trailing [Constant] block. Do not invent images, media, facts or references. Do not run tools or modify files. Target: " + guide + ". " + contract + "\n\nAUTHORING GUIDE:\n" + text


def _provider_config(provider):
    if provider == "LM Studio":
        return resolve_config_value("lmstudio_base_url", default="http://127.0.0.1:1234").rstrip("/"), resolve_config_value("lmstudio_api_key")
    if provider == "Ollama":
        return resolve_config_value("ollama_base_url", default="http://127.0.0.1:11434").rstrip("/"), resolve_config_value("ollama_api_key")
    if provider == "OpenAI-compatible":
        return resolve_config_value("openai_compatible_base_url", default="https://api.openai.com/v1").rstrip("/"), resolve_config_value("openai_compatible_api_key")
    if provider == "Pollinations":
        return "https://gen.pollinations.ai", resolve_config_value("pollinations_api_key")
    return "", ""


def _headers(key):
    return {"Authorization": "Bearer " + key} if key else {}


def _codex_executable():
    executable = get_persistent_setting("codex_executable", "") or shutil.which("codex")
    if not executable and os.name == "nt":
        bundled = Path(os.environ.get("LOCALAPPDATA", ""))/"Programs/OpenAI/Codex/bin/codex.exe"
        if bundled.is_file():
            executable = str(bundled)
    if not executable:
        raise RuntimeError("Codex CLI is not installed or its executable is not configured.")
    return executable


def _codex_models():
    # Only this task-owned discovery child is terminated. No shared Codex process.
    proc = subprocess.Popen([_codex_executable(), "app-server", "--listen", "stdio://"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    messages = queue.Queue()
    def reader():
        for line in proc.stdout:
            try:
                messages.put(json.loads(line))
            except ValueError:
                continue
    threading.Thread(target=reader, daemon=True).start()
    def send(data):
        proc.stdin.write(json.dumps(data)+"\n")
        proc.stdin.flush()
    def response(rid):
        end = time.monotonic()+20
        while time.monotonic() < end:
            try:
                value = messages.get(timeout=max(.01, end-time.monotonic()))
            except queue.Empty:
                break
            if value.get("id") == rid:
                if value.get("error"):
                    raise RuntimeError("Codex discovery rejected the request: " + str(value["error"].get("message", "RPC error")))
                return value.get("result", {})
        raise RuntimeError("Codex model discovery timed out.")
    try:
        send({"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "overtli-studio", "version": "1.2.0"}}})
        response(1)
        send({"method": "initialized"})
        send({"id": 2, "method": "model/list", "params": {"includeHidden": False}})
        result = response(2)
        return [{"id": x.get("model") or x.get("id"), "label": x.get("displayName") or x.get("model") or x.get("id"), "reasoning": x.get("supportedReasoningEfforts", [])} for x in result.get("data", [])]
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def discover_models(provider, force=False):
    if provider not in PROVIDERS:
        raise ValueError("Unknown provider.")
    base, key = _provider_config(provider)
    cache_key = (provider, base, bool(key))
    # Cache failures too; browser refresh never spins on an unavailable provider.
    with _MODEL_LOCK:
        previous = _MODEL_CACHE.get(cache_key)
        if previous and not force and time.monotonic()-previous[0] < 300:
            return previous[1]
        try:
            if provider == "Codex":
                models = _codex_models()
            else:
                url = (base + "/api/tags") if provider == "Ollama" else (base + "/text/models") if provider == "Pollinations" else (base.removesuffix("/v1") + "/api/v1/models") if provider == "LM Studio" else base + "/models"
                response = requests.get(url, headers=_headers(key), timeout=12)
                response.raise_for_status()
                data = response.json()
                rows = data if isinstance(data, list) else data.get("models", data.get("data", []))
                models = [{"id": x.get("key") or x.get("id") or x.get("name"), "label": x.get("display_name") or x.get("name") or x.get("id") or x.get("key")} for x in rows if isinstance(x, dict) and x.get("type") not in {"embedding", "embeddings"}]
            result = {"models": models, "error": "", "provider": provider}
        except Exception as exc:
            # Avoid response bodies, request URLs with credentials, and raw key values.
            result = {"models": [], "error": f"{provider} discovery failed ({type(exc).__name__}). Check connection, authentication, and the configured endpoint.", "provider": provider}
        _MODEL_CACHE[cache_key] = (time.monotonic(), result)
        return result


def enhance_prompt(prompt, state):
    provider = state.get("provider", "LM Studio")
    model = str(state.get("model") or "").strip()
    if provider not in PROVIDERS or not model:
        raise ValueError("Choose a provider and a detected model before enhancing.")
    instructions = guide_instructions(state.get("guide", "H3 Ref2VA")) + "\n\n" + str(state.get("instructions") or "")
    max_tokens = max(256, min(16384, int(state.get("maxTokens", 2048))))
    context_tokens = max(2048, min(131072, int(state.get("contextTokens", 8192))))
    if provider == "Codex":
        with tempfile.TemporaryDirectory(prefix="overtli-prompt-") as tmp:
            out = Path(tmp)/"response.txt"
            args = [_codex_executable(), "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral", "--sandbox", "read-only", "--skip-git-repo-check", "-C", tmp, "-m", model, "-o", str(out), "-"]
            result = subprocess.run(args, input=instructions+"\n\nUSER PROMPT:\n"+prompt, capture_output=True, text=True, encoding="utf-8", timeout=240, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if result.returncode or not out.is_file():
                raise RuntimeError("Codex enhancement failed. Check CLI authentication and model access.")
            return out.read_text(encoding="utf-8").strip()
    base, key = _provider_config(provider)
    if provider == "LM Studio":
        from .engine.llm_text_enhancer import _unload_model
        native = base.removesuffix("/v1") + "/api/v1"
        headers = {**_headers(key), "Content-Type": "application/json"}
        # Native chat separates final messages from reasoning and supports the
        # model's advertised reasoning switch. Small thinking models otherwise
        # exhaust the entire response budget before producing a prompt.
        try:
            catalog = requests.get(native + "/models", headers=headers, timeout=12)
            catalog.raise_for_status()
            rows = catalog.json().get("models", [])
            selected = next((row for row in rows if row.get("key") == model or any(i.get("id") == model for i in row.get("loaded_instances", []))), {})
            payload = {"model": model, "input": prompt, "system_prompt": instructions, "max_output_tokens": max_tokens, "temperature": .5, "store": False}
            allowed = selected.get("capabilities", {}).get("reasoning", {}).get("allowed_options", [])
            reasoning = state.get("reasoning", "off")
            if reasoning in allowed:
                payload["reasoning"] = reasoning
            needed = max(context_tokens, math.ceil((len(instructions)+len(prompt))/4)+max_tokens+1024)
            limit = int(selected.get("max_context_length") or 32768)
            if needed > limit:
                raise ValueError("Prompt, authoring guide and output budget exceed this model's context capacity. Choose a larger-context model or reduce the prompt/output budget.")
            payload["context_length"] = min(limit, math.ceil(needed/1024)*1024)
            response = requests.post(native + "/chat", headers=headers, json=payload, timeout=240)
            response.raise_for_status()
            result = "\n".join(str(item.get("content") or "") for item in response.json().get("output", []) if item.get("type") == "message").strip()
            if not result:
                raise RuntimeError("LM Studio returned no final prompt. Increase the output token budget or select a non-thinking model.")
            return result
        finally:
            if state.get("autoUnload", True):
                _unload_model(model, native + "/models/unload", headers=headers)
    if provider == "Ollama":
        from .engine.llm_text_enhancer import _unload_ollama_model
        native = base.removesuffix("/v1")
        headers = {**_headers(key), "Content-Type": "application/json"}
        needed = max(context_tokens, math.ceil((len(instructions)+len(prompt))/4)+max_tokens+1024)
        try:
            if needed > 131072:
                raise ValueError("Prompt, guide and response exceed the supported local context budget. Reduce text/output or use a different provider.")
            response = requests.post(native + "/api/chat", headers=headers, json={"model": model, "messages": [{"role": "system", "content": instructions}, {"role": "user", "content": prompt}], "stream": False, "options": {"num_ctx": math.ceil(needed/1024)*1024, "num_predict": max_tokens, "temperature": .5}}, timeout=240)
            response.raise_for_status()
            result = str(response.json().get("message", {}).get("content") or "").strip()
            if not result:
                raise RuntimeError("Ollama returned no final prompt.")
            return result
        finally:
            if state.get("autoUnload", True):
                _unload_ollama_model(model, native + "/v1/chat/completions", headers=headers)
    url = base + "/v1/chat/completions" if provider == "Pollinations" else base + "/chat/completions"
    response = requests.post(url, headers={**_headers(key), "Content-Type": "application/json"}, json={"model": model, "messages": [{"role": "system", "content": instructions}, {"role": "user", "content": prompt}], "temperature": .5, "max_tokens": max_tokens}, timeout=240)
    response.raise_for_status()
    result = response.json()["choices"][0]["message"]["content"]
    if not isinstance(result, str) or not result.strip():
        raise RuntimeError("Provider returned an empty prompt.")
    return result.strip()


class OvertliStudioSuite:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"prompt": ("STRING", {"forceInput": True}), "state": ("STRING", {"default": "{}", "multiline": True})}}
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("prompt", "checks")
    FUNCTION = "execute"
    CATEGORY = "Overtli/Studio"

    def execute(self, prompt, state="{}"):
        state = json.loads(state or "{}") if isinstance(state, str) else dict(state)
        prompt = prepare_prompt(prompt, state)
        return prompt, json.dumps(check_prompt(prompt, state.get("guide", "H3 Ref2VA")), ensure_ascii=False)


def _library(addtl):
    global _ADDTL_LIBRARY
    if not addtl:
        return library
    if _ADDTL_LIBRARY is None:
        import importlib.util
        import sys
        name = __package__ + "._addtl_prompt_library"
        spec = importlib.util.spec_from_file_location(name, Path(__file__).parent/"prompt_library_store.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        module.PROMPT_LIBRARY_FILENAME = "overtli_addtl_prompt_library.json"
        _ADDTL_LIBRARY = module
    return _ADDTL_LIBRARY


def save_connections(body):
    allowed = {k: str(v) for k, v in body.items() if k in {"lmstudio_base_url", "lmstudio_api_key", "ollama_base_url", "ollama_api_key", "openai_compatible_base_url", "openai_compatible_api_key", "pollinations_api_key", "codex_executable"}}
    # Blank password fields preserve stored keys; explicit clear is separate.
    allowed = {k: v for k, v in allowed.items() if v or not k.endswith("api_key")}
    for key in body.get("clear_keys", []):
        if key in {"lmstudio_api_key", "ollama_api_key", "openai_compatible_api_key", "pollinations_api_key"}:
            allowed[key] = ""
    save_persistent_settings(allowed, skip_empty=False, source="Overtli Studio UI")
    _MODEL_CACHE.clear()


def register_routes():
    from aiohttp import web
    from server import PromptServer
    routes = PromptServer.instance.routes

    @routes.get("/overtli/studio/styles")
    async def styles(request):
        from .styles import PROMPT_STYLES
        return web.json_response({"styles": [{"label": x["label"], "category": x.get("main_category", ""), "description": x["description"], "instruction": x["instruction"], "tags": x["tags"]} for x in PROMPT_STYLES]})

    @routes.post("/overtli/studio/preflight")
    async def preflight(request):
        from .prompt_preflight import inspect_prompts
        try:
            body = await request.json()
            result = await asyncio.to_thread(inspect_prompts, body.get("output", {}))
            return web.json_response(result)
        except requests.RequestException:
            return web.json_response({"error": "Prompt provider request failed. Check the selected service, URL, credentials and model; authored text is preserved."}, status=400)
        except (ValueError, RuntimeError) as exc:
            return web.json_response({"error": str(exc)}, status=400)

    @routes.get("/overtli/studio/files")
    async def scoped_files(request):
        import folder_paths
        root = Path(folder_paths.get_input_directory()).resolve()
        addtl = request.query.get("addtl") == "1"
        files = []
        allowed = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v", ".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac"}
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in allowed and path.resolve().is_relative_to(root):
                rel = path.relative_to(root).as_posix()
                island = root / "OvertliDS" / "addtl"
                in_island = path.resolve().is_relative_to(island.resolve())
                if in_island == addtl:
                    files.append(rel)
        return web.json_response({"files": sorted(files, key=str.lower)})

    @routes.get("/overtli/studio/models")
    async def models(request):
        result = await asyncio.to_thread(discover_models, request.query.get("provider", "LM Studio"), request.query.get("refresh") == "1")
        return web.json_response(result)

    @routes.get("/overtli/studio/settings")
    async def settings(request):
        result = {}
        for key in ("lmstudio_base_url", "lmstudio_api_key", "ollama_base_url", "ollama_api_key", "openai_compatible_base_url", "openai_compatible_api_key", "pollinations_api_key", "codex_executable"):
            value = get_persistent_setting(key, "")
            result[key] = bool(value) if key.endswith("api_key") else value
        return web.json_response(result)

    @routes.post("/overtli/studio/settings")
    async def save_settings(request):
        body = await request.json()
        try:
            save_connections(body)
            return web.json_response({"saved": True})
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)

    @routes.post("/overtli/studio/prompt")
    async def prompt_action(request):
        body = await request.json()
        prompt, state = str(body.get("prompt") or ""), body.get("state") or {}
        if len(prompt) > 200000 or not isinstance(state, dict):
            return web.json_response({"error": "Invalid or oversized prompt/state."}, status=400)
        try:
            prompt = await asyncio.to_thread(prepare_prompt, prompt, state, body.get("action") in {"enhance", "test"})
            return web.json_response({"prompt": prompt, "checks": check_prompt(prompt, state.get("guide", "H3 Ref2VA"), str(body.get("reference_tags") or ""), body.get("duration"))})
        except Exception as exc:
            message = str(exc)
            for provider in PROVIDERS:
                secret = _provider_config(provider)[1]
                if secret:
                    message = message.replace(secret, "[redacted]")
            message = re.sub(r"(?i)(bearer\s+)[\w.\-]+", r"\1[redacted]", message)
            return web.json_response({"error": f"Prompt operation failed ({type(exc).__name__}): {message[:800]}"}, status=400 if isinstance(exc, ValueError) else 502)

    @routes.get("/overtli/studio/library")
    async def list_library(request):
        with _LIBRARY_LOCK:
            store = _library(request.query.get("addtl") == "1")
            entries = store.list_prompt_entries(search_query=request.query.get("search", ""), category_filter=request.query.get("category", "All"), sort_mode="most_recent", limit=200)
            return web.json_response({"entries": entries, "categories": store.get_prompt_categories()})

    @routes.post("/overtli/studio/library")
    async def edit_library(request):
        body = await request.json()
        with _LIBRARY_LOCK:
            store = _library(bool(body.get("addtl")))
            try:
                action = body.get("action", "save")
                if action == "load":
                    entry = store.get_prompt_entry(str(body.get("name") or ""), increment_use_count=True)
                    if not entry:
                        return web.json_response({"error": "Prompt no longer exists."}, status=404)
                    return web.json_response({"entry": entry})
                if action == "delete":
                    return web.json_response({"deleted": store.delete_prompt_entry(str(body.get("name") or ""))})
                entry = store.upsert_prompt_entry(name=str(body.get("name") or ""), prompt=str(body.get("prompt") or ""), category=str(body.get("category") or "General"), tags=body.get("tags") or [], notes=str(body.get("notes") or ""), allow_overwrite=bool(body.get("overwrite", False)), studio=body.get("studio"))
                return web.json_response({"entry": entry})
            except ValueError as exc:
                return web.json_response({"error": str(exc)}, status=400)


try:
    register_routes()
except ModuleNotFoundError as exc:
    if exc.name != "server":
        raise
    # Headless authoring/tests use the same prompt contract without a web host.
