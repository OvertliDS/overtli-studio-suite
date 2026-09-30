"""Director save metadata and browser-compatible comparison proxies."""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import shutil

import folder_paths
from aiohttp import web
from server import PromptServer


def _saver():
    # Keep the original node class/JS ID so all Pixaroma player, settings and
    # graphToPrompt hooks continue to work. Find the original Python class.
    for module in tuple(sys.modules.values()):
        cls = getattr(module, "__dict__", {}).get("PixaromaSaveVideo")
        if cls is not None and cls is not OvertliDirectorSaveVideo:
            return cls
    raise RuntimeError("ComfyUI-Pixaroma Save Video is required for Director Save Video.")


def _module():
    return sys.modules[_saver().__module__]


def media_path(entry):
    kind = entry.get("type", "output")
    if kind == "external":
        path = _module().resolve_serve_token(entry.get("token"))
        if not path:
            raise ValueError("External media token expired; run/save the source again.")
        return Path(path)
    roots = {"input": folder_paths.get_input_directory(), "output": folder_paths.get_output_directory(), "temp": folder_paths.get_temp_directory()}
    if kind not in roots:
        raise ValueError("Unsupported media location.")
    root = Path(roots[kind]).resolve()
    target = (root/str(entry.get("subfolder") or "")/str(entry.get("filename") or "")).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise ValueError("Media file is missing or outside its registered root.")
    return target


class OvertliDirectorSaveVideo:
    @classmethod
    def INPUT_TYPES(cls):
        schema = copy.deepcopy(_saver().INPUT_TYPES())
        schema["optional"].update({"prompt_text": ("STRING", {"forceInput": True}), "lora_plan": ("STRING", {"forceInput": True}), "director_state": ("STRING", {"forceInput": True})})
        return schema
    RETURN_TYPES = ()
    FUNCTION = "save"
    OUTPUT_NODE = True
    CATEGORY = "Overtli/Studio"

    def save(self, video_frames, fps, audio=None, name=None, force_preview=False, SaveVideoState="", prompt=None, extra_pnginfo=None, unique_id=None, prompt_text="", lora_plan="", director_state=""):
        state = json.loads(SaveVideoState or "{}")
        # A missing state must behave as a durable final saver. Explicit Preview
        # remains available for selected clips and intentionally transient runs.
        state.setdefault("saveOnRun", True)
        result = _saver()().save(video_frames=video_frames, fps=fps, audio=audio, name=name, force_preview=force_preview, SaveVideoState=json.dumps(state), prompt=prompt, extra_pnginfo=extra_pnginfo, unique_id=unique_id)
        def parse(value):
            try:
                return json.loads(value) if value else {}
            except ValueError:
                return {"text": str(value)}
        metadata = {"prompt": str(prompt_text), "loras": parse(lora_plan), "director": parse(director_state)}
        if not (prompt_text or lora_plan or director_state):
            return result
        for entry in result.get("ui", {}).get("pixaroma_save_video", []):
            entry["_overtli_metadata"] = metadata
            target = media_path(entry)
            if "addtl" in {p.lower() for p in target.parts} and entry.get("_pixaroma_preview"):
                preview = entry["_pixaroma_preview"]
                source = media_path(preview)
                directory = Path(folder_paths.get_temp_directory())/"OvertliDS/addtl/previews"
                directory.mkdir(parents=True, exist_ok=True)
                destination = directory/source.name
                shutil.move(str(source), str(destination))
                preview["subfolder"] = "OvertliDS/addtl/previews"
            # Explicit prompt/LoRA metadata works for every container and never
            # includes Studio credentials or full provider request headers.
            sidecar = Path(str(target) + ".overtli.json")
            sidecar.write_text(json.dumps({**metadata, "media": entry.get("_pixaroma_status", {})}, ensure_ascii=False, indent=2), encoding="utf-8")
        return result


@PromptServer.instance.routes.post("/overtli/studio/video-proxy")
async def video_proxy(request):
    try:
        body = await request.json()
        path = media_path(body)
        if path.suffix.lower() not in {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v"}:
            raise ValueError("Choose a supported video container.")
        # Use Pixaroma's existing bounded H.264 proxy implementation. It keeps
        # the editing master intact and handles uploaded ProRes/H.265 too.
        module = _module()
        finder = getattr(module, "_ffmpeg_path", None)
        if callable(finder):
            ffmpeg = finder()
        else:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        signature = hashlib.sha256((str(path)+str(path.stat().st_mtime_ns)+str(path.stat().st_size)).encode()).hexdigest()
        cached = _PROXIES.get(signature)
        if cached:
            try:
                media_path(cached)
                return web.json_response({"preview": cached})
            except ValueError:
                _PROXIES.pop(signature, None)
        preview = await asyncio.to_thread(module._create_browser_preview_proxy, ffmpeg, str(path))
        if not preview:
            raise RuntimeError("Browser proxy encoding failed.")
        if "addtl" in {p.lower() for p in path.parts}:
            source = media_path(preview)
            directory = Path(folder_paths.get_temp_directory())/"OvertliDS/addtl/previews"
            directory.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(directory/source.name))
            preview["subfolder"] = "OvertliDS/addtl/previews"
        if len(_PROXIES) >= 64:
            _PROXIES.pop(next(iter(_PROXIES)))
        _PROXIES[signature] = preview
        return web.json_response({"preview": preview})
    except (ValueError, OSError, RuntimeError) as exc:
        return web.json_response({"error": str(exc)}, status=400)


_PROXIES = {}
