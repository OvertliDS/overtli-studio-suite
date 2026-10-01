"""Director save metadata and browser-compatible comparison proxies."""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import math
import os
from collections import OrderedDict
from fractions import Fraction
from pathlib import Path
import re
import sys
import shutil
import tempfile
import uuid

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


_VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v"})
_FRAME_MAX_COUNT = 32
_FRAME_MAX_PIXELS = 8_500_000
_FRAME_MAX_WORK_PIXELS = 136_000_000
_FRAME_PROCESS_TIMEOUT = 45
_FRAME_PROCESS_SLOTS = asyncio.Semaphore(2)
_FRAME_INFO_CACHE = OrderedDict()
_FRAME_INFO_CACHE_CAP = 64
_EXTERNAL_SCOPES = OrderedDict()
_EXTERNAL_SCOPES_CAP = 256


class _MediaScopeMismatch(ValueError):
    pass


def _media_identity(path):
    stat = path.stat()
    raw = f"{path.resolve()}\0{stat.st_size}\0{stat.st_mtime_ns}".encode("utf-8", "surrogatepass")
    return hashlib.sha256(raw).hexdigest()


def _workflow_scope(value):
    """Return explicit workflow Addtl state without treating missing data as Normal."""
    pending = [value]
    visited = 0
    flags = set()
    while pending and visited < 100_000:
        current = pending.pop()
        visited += 1
        if isinstance(current, dict):
            for key in ("overtliAddtl", "overtli_addtl"):
                flag = current.get(key)
                if type(flag) is bool:
                    flags.add(flag)
            pending.extend(current.values())
        elif isinstance(current, (list, tuple)):
            pending.extend(current)
    if flags == {True}:
        return "addtl"
    if flags == {False}:
        return "normal"
    return None


def _executed_workflow_scope(extra_pnginfo, unique_id):
    """Resolve scope from the save node, workflow metadata or its Director."""
    if not isinstance(extra_pnginfo, dict):
        return None
    workflow = extra_pnginfo.get("workflow")
    if not isinstance(workflow, dict):
        return None
    nodes = workflow.get("nodes")
    if not isinstance(nodes, list):
        nodes = []
    executed_node = next((node for node in nodes if isinstance(node, dict) and str(node.get("id")) == str(unique_id)), None)
    if executed_node:
        scope = _workflow_scope(executed_node.get("properties"))
        if scope:
            return scope
    scope = _workflow_scope(workflow.get("extra"))
    if scope:
        return scope
    director_scopes = set()
    for node in nodes:
        if not isinstance(node, dict):
            continue
        name = str(node.get("type") or node.get("comfyClass") or node.get("class_type") or "")
        if name not in {"OvertliStudioSuite", "OvertliH3ReferenceDirectorUI", "OvertliImageDirectorUI"}:
            continue
        node_scope = _workflow_scope(node.get("properties"))
        if node_scope:
            director_scopes.add(node_scope)
    return next(iter(director_scopes)) if len(director_scopes) == 1 else None


def _managed_media_scope(path):
    """Classify a real media path relative to ComfyUI's registered media roots."""
    path = Path(path).resolve()
    roots = (
        folder_paths.get_input_directory(),
        folder_paths.get_output_directory(),
        folder_paths.get_temp_directory(),
    )
    for value in roots:
        root = Path(value).resolve()
        if path.is_relative_to((root / "OvertliDS" / "addtl").resolve()):
            return "addtl"
        if path.is_relative_to(root):
            return "normal"
    return None


def _sidecar_scope(path):
    """Read only scope records bound to the current bytes at this exact path."""
    sidecar = Path(str(path) + ".overtli.json")
    try:
        if sidecar.stat().st_size > 64 * 1024:
            return None
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return None
    if not isinstance(data, dict) or data.get("media_identity") != _media_identity(path):
        return None
    scope = data.get("overtli_scope")
    return scope if scope in {"normal", "addtl"} else None


def _verified_media_scope(entry, path):
    scope = _managed_media_scope(path)
    if scope is None and entry.get("type") == "external":
        token = str(entry.get("token") or "")
        registered = _EXTERNAL_SCOPES.get(token)
        identity = _media_identity(path)
        if registered and registered.get("media_identity") == identity:
            scope = registered.get("scope")
        if scope is None:
            scope = _sidecar_scope(path)
        if scope is None:
            return None
    return scope


def _validated_media_scope(entry, path, expected_scope):
    if expected_scope not in {"normal", "addtl"}:
        raise ValueError("Choose a Normal or Addtl review wall before inspecting frames.")
    scope = _verified_media_scope(entry, path)
    if scope is None:
        if entry.get("type") == "external":
            raise ValueError(
                "This external save has no verified Normal/Addtl scope. Upload it into the selected "
                "Normal or Addtl input island before frame inspection or extraction."
            )
        raise ValueError("Frame review is limited to registered ComfyUI media roots.")
    if scope != expected_scope:
        selected = "Addtl" if expected_scope == "addtl" else "Normal"
        actual = "Addtl" if scope == "addtl" else "Normal"
        raise _MediaScopeMismatch(f"This {actual} video cannot be opened from the {selected} review wall.")
    return scope


def register_external_scope(token, path, scope):
    """Register a saved external file using scope from its executed workflow.

    Callers must derive ``scope`` from the executed save workflow or connected
    Director state. The path and current size/mtime identity bind that evidence
    to the exact file; UI-provided ``_overtli_scope`` values are never consulted.
    The matching sidecar keeps the registration usable after a restart.
    """
    if scope not in {"normal", "addtl"}:
        raise ValueError("External save scope must come from an executed Normal/Addtl workflow.")
    target = Path(path).resolve(strict=True)
    if not target.is_file():
        raise ValueError("External save scope can only be registered for an existing file.")
    managed_scope = _managed_media_scope(target)
    if managed_scope is not None and managed_scope != scope:
        raise ValueError("The registered media path belongs to a different Normal/Addtl island.")
    identity = _media_identity(target)
    _remember_external_scope(token, identity, scope)
    sidecar = Path(str(target) + ".overtli.json")
    try:
        existing = json.loads(sidecar.read_text(encoding="utf-8")) if sidecar.is_file() else {}
    except (OSError, ValueError, UnicodeError):
        existing = {}
    if not isinstance(existing, dict):
        existing = {}
    existing.update({
        "media_identity": identity,
        "overtli_scope": scope,
        "scope_provenance": "Executed ComfyUI save workflow",
    })
    sidecar.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    return identity


def _remember_external_scope(token, identity, scope):
    token = str(token or "")
    if token:
        _EXTERNAL_SCOPES[token] = {"scope": scope, "media_identity": identity}
        _EXTERNAL_SCOPES.move_to_end(token)
        while len(_EXTERNAL_SCOPES) > _EXTERNAL_SCOPES_CAP:
            _EXTERNAL_SCOPES.popitem(last=False)


def _ffmpeg_tools():
    ffmpeg = shutil.which("ffmpeg")
    try:
        module = _module()
    except RuntimeError:
        module = None
    finder = getattr(module, "_ffmpeg_path", None) if module else None
    if callable(finder):
        ffmpeg = finder()
    if not ffmpeg:
        try:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception as exc:
            raise RuntimeError("FFmpeg is unavailable in this ComfyUI runtime.") from exc
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        candidate = Path(ffmpeg).with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
        if candidate.is_file():
            ffprobe = str(candidate)
    if not ffprobe:
        raise RuntimeError("FFprobe is unavailable; install no tools here and configure the existing media runtime.")
    return str(ffmpeg), str(ffprobe)


async def _read_bounded(reader, limit, keep_tail=False):
    chunks = bytearray()
    overflow = False
    while True:
        chunk = await reader.read(64 * 1024)
        if not chunk:
            break
        if keep_tail:
            chunks.extend(chunk)
            if len(chunks) > limit:
                del chunks[:len(chunks) - limit]
                overflow = True
        elif len(chunks) < limit:
            remaining = limit - len(chunks)
            chunks.extend(chunk[:remaining])
            overflow = overflow or len(chunk) > remaining
        else:
            overflow = True
    return bytes(chunks), overflow


async def _run_frame_process(args, timeout, *, stdout_limit=1_048_576, stderr_limit=262_144):
    async with _FRAME_PROCESS_SLOTS:
        proc = await asyncio.create_subprocess_exec(
            *map(str, args),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=65_536,
        )
        stdout_task = asyncio.create_task(_read_bounded(proc.stdout, stdout_limit))
        stderr_task = asyncio.create_task(_read_bounded(proc.stderr, stderr_limit, keep_tail=True))
        try:
            await asyncio.wait_for(proc.wait(), timeout=timeout)
            (stdout, stdout_overflow), (stderr, _) = await asyncio.gather(stdout_task, stderr_task)
        except asyncio.TimeoutError as exc:
            if proc.returncode is None:
                proc.kill()
            await proc.wait()
            await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
            raise RuntimeError(f"Media inspection exceeded its {timeout}-second time limit.") from exc
        except asyncio.CancelledError:
            if proc.returncode is None:
                proc.kill()
            await proc.wait()
            await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
            raise
        detail = stderr.decode("utf-8", "replace").strip()
        if stdout_overflow:
            raise RuntimeError("FFprobe returned oversized metadata; the source was not loaded.")
        if proc.returncode != 0:
            raise RuntimeError(detail[-1200:] or "The installed media decoder rejected this video.")
        return stdout, stderr


def _rate(value):
    try:
        rate = float(Fraction(str(value)))
        return rate if rate > 0 else None
    except (ValueError, ZeroDivisionError, TypeError):
        return None


def _timestamp(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


async def _inspect_video(path):
    identity = _media_identity(path)
    cached = _FRAME_INFO_CACHE.get(identity)
    if cached:
        _FRAME_INFO_CACHE.move_to_end(identity)
        return dict(cached)
    _, ffprobe = _ffmpeg_tools()
    args = [
        ffprobe, "-v", "error", "-count_frames", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,avg_frame_rate,r_frame_rate,nb_frames,nb_read_frames,duration,time_base,start_time:format=duration",
        "-of", "json", str(path),
    ]
    stdout, _ = await _run_frame_process(args, _FRAME_PROCESS_TIMEOUT)
    try:
        payload = json.loads(stdout)
        stream = payload["streams"][0]
        width = int(stream["width"])
        height = int(stream["height"])
        frames = int(stream.get("nb_read_frames") or stream.get("nb_frames") or 0)
    except (ValueError, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("FFprobe could not determine the source frame count and raster.") from exc
    if width <= 0 or height <= 0 or frames <= 0:
        raise ValueError("The selected source has no decodable video frames.")
    if width * height > _FRAME_MAX_PIXELS:
        raise ValueError(f"Frame extraction is limited to {_FRAME_MAX_PIXELS:,} pixels per frame.")
    avg_fps = _rate(stream.get("avg_frame_rate"))
    nominal_fps = _rate(stream.get("r_frame_rate"))
    start_time = _timestamp(stream.get("start_time"))
    duration = _rate(stream.get("duration"))
    if duration is None:
        container_duration = _rate(payload.get("format", {}).get("duration"))
        duration = max(0.0, container_duration - start_time) if container_duration is not None and start_time is not None and start_time > 0 else container_duration
    result = {
        "width": width,
        "height": height,
        "raster": {"width": width, "height": height},
        "frame_count": frames,
        "avg_fps": avg_fps,
        "nominal_fps": nominal_fps,
        "avg_frame_rate": stream.get("avg_frame_rate"),
        "r_frame_rate": stream.get("r_frame_rate"),
        "duration": duration,
        "start_time": start_time,
        "frame_index_mode": "decoded source frame order",
    }
    _FRAME_INFO_CACHE[identity] = dict(result)
    _FRAME_INFO_CACHE.move_to_end(identity)
    while len(_FRAME_INFO_CACHE) > _FRAME_INFO_CACHE_CAP:
        _FRAME_INFO_CACHE.popitem(last=False)
    return result


def _frame_indices(values, frame_count):
    if not isinstance(values, list) or not values or len(values) > _FRAME_MAX_COUNT:
        raise ValueError(f"Request between 1 and {_FRAME_MAX_COUNT} frames at a time.")
    if any(type(value) is not int for value in values):
        raise ValueError("Frame indices must be whole numbers.")
    indices = sorted(set(values))
    if len(indices) != len(values):
        raise ValueError("Frame indices must be unique.")
    if any(value < 0 or value >= frame_count for value in indices):
        raise ValueError(f"Frame indices must be between 0 and {frame_count - 1}.")
    return indices


async def _decode_frames(path, indices, info):
    work = info["width"] * info["height"] * len(indices)
    if work > _FRAME_MAX_WORK_PIXELS:
        raise ValueError(f"This request exceeds the {_FRAME_MAX_WORK_PIXELS:,}-pixel extraction budget; use a shorter range.")
    ffmpeg, _ = _ffmpeg_tools()
    filters = "+".join(f"eq(n\\,{index})" for index in indices)
    # Keep input presentation timestamps intact. setpts would silently turn a
    # non-zero source start time into zero and misreport VFR source times.
    filtergraph = f"select={filters},showinfo"
    temp = tempfile.TemporaryDirectory(prefix="overtli_review_frames_")
    try:
        temp_dir = temp.name
        output_pattern = str(Path(temp_dir) / "frame-%06d.png")
        args = [
            ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "info", "-copyts", "-i", str(path),
            "-map", "0:v:0", "-an", "-sn", "-dn", "-vf", filtergraph,
            "-fps_mode", "passthrough", "-frames:v", str(len(indices)), "-compression_level", "1",
            "-start_number", "0",
            output_pattern,
        ]
        _, stderr = await _run_frame_process(args, _FRAME_PROCESS_TIMEOUT, stdout_limit=1024)
        text = stderr.decode("utf-8", "replace")
        timestamps = [float(x) for x in re.findall(r"pts_time:([+-]?(?:\d+(?:\.\d*)?|\.\d+))", text)]
        files = [Path(temp_dir) / f"frame-{i:06d}.png" for i in range(len(indices))]
        if len(timestamps) != len(indices) or not all(item.is_file() and item.stat().st_size > 0 for item in files):
            raise RuntimeError("FFmpeg did not return every requested source frame with its presentation timestamp.")
        return temp, [(index, timestamps[i], files[i]) for i, index in enumerate(indices)]
    except BaseException:
        temp.cleanup()
        raise


def _input_frames_directory(scope):
    root = Path(folder_paths.get_input_directory()).resolve()
    subfolder = "OvertliDS/addtl/frames" if scope == "addtl" else "OvertliDS/references/frames"
    directory = (root / Path(subfolder)).resolve()
    if not directory.is_relative_to(root):
        raise ValueError("Frame destination is outside the registered input directory.")
    directory.mkdir(parents=True, exist_ok=True)
    return directory, subfolder


def _save_frame_file(directory, source_name, frame_index, source):
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(source_name).stem)[:32].strip("_") or "video"
    while True:
        filename = f"{stem}_frame_{frame_index:06d}_{uuid.uuid4().hex[:12]}.png"
        destination = directory / filename
        try:
            fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            continue
        try:
            with os.fdopen(fd, "wb") as out:
                with source.open("rb") as inp:
                    shutil.copyfileobj(inp, out, length=1024 * 1024)
        except BaseException:
            try:
                destination.unlink()
            except OSError:
                pass
            raise
        return filename


def _frame_record(index, timestamp, filename, subfolder, info):
    return {
        "filename": filename,
        "subfolder": subfolder,
        "type": "input",
        "frame_index": index,
        "timestamp": timestamp,
        "raster": {"width": info["width"], "height": info["height"]},
    }


def _move_proxy_to_scope(preview, scope):
    if scope not in {"normal", "addtl"}:
        return preview
    source = media_path(preview)
    source_scope = _managed_media_scope(source)
    if source_scope == scope:
        return preview
    if source_scope is None:
        raise ValueError("The browser proxy was written outside a registered ComfyUI media root.")
    temp_root = Path(folder_paths.get_temp_directory()).resolve()
    subfolder = "OvertliDS/addtl/previews" if scope == "addtl" else "OvertliDS/references/previews"
    directory = (temp_root / Path(subfolder)).resolve()
    if not directory.is_relative_to(temp_root):
        raise ValueError("The scoped playback proxy destination escapes the registered temp directory.")
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"review_proxy_{uuid.uuid4().hex}{source.suffix.lower()}"
    shutil.move(str(source), str(destination))
    return {**preview, "filename": destination.name, "subfolder": subfolder, "type": "temp"}


async def _source_request(body):
    if not isinstance(body, dict) or not isinstance(body.get("entry"), dict):
        raise ValueError("Choose a video source first.")
    entry = body["entry"]
    path = media_path(entry)
    if path.suffix.lower() not in _VIDEO_EXTENSIONS:
        raise ValueError("Choose a supported video container: MP4, MOV, WebM, MKV, AVI or M4V.")
    scope = _validated_media_scope(entry, path, body.get("scope"))
    info = await _inspect_video(path)
    return entry, path, scope, info


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
        scope_hint = _workflow_scope(parse(director_state)) or _executed_workflow_scope(extra_pnginfo, unique_id)
        for entry in result.get("ui", {}).get("pixaroma_save_video", []):
            target = media_path(entry)
            scope = _managed_media_scope(target) or scope_hint
            identity = _media_identity(target)
            if scope in {"normal", "addtl"}:
                entry["_overtli_scope"] = scope
            has_metadata = bool(prompt_text or lora_plan or director_state)
            if has_metadata:
                entry["_overtli_metadata"] = metadata
            if scope == "addtl" and entry.get("_pixaroma_preview"):
                entry["_pixaroma_preview"] = _move_proxy_to_scope(entry["_pixaroma_preview"], scope)
            # Explicit prompt/LoRA metadata works for every container and never
            # includes Studio credentials or full provider request headers.
            if has_metadata or (entry.get("type") == "external" and scope in {"normal", "addtl"}):
                sidecar = Path(str(target) + ".overtli.json")
                sidecar_data = {**metadata, "media": entry.get("_pixaroma_status", {}), "media_identity": identity}
                if scope in {"normal", "addtl"}:
                    sidecar_data["overtli_scope"] = scope
                    sidecar_data["scope_provenance"] = "OvertliDirectorSaveVideo execution"
                sidecar.write_text(json.dumps(sidecar_data, ensure_ascii=False, indent=2), encoding="utf-8")
                if entry.get("type") == "external" and scope in {"normal", "addtl"}:
                    token = str(entry.get("token") or "")
                    _remember_external_scope(token, identity, scope)
        return result


@PromptServer.instance.routes.post("/overtli/studio/video-proxy")
async def video_proxy(request):
    try:
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError("Choose a video source first.")
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
        scope = _verified_media_scope(body if isinstance(body, dict) else {}, path)
        signature = hashlib.sha256((str(path.resolve())+str(path.stat().st_mtime_ns)+str(path.stat().st_size)+str(scope)).encode()).hexdigest()
        cached = _PROXIES.get(signature)
        if cached:
            try:
                media_path(cached)
                return web.json_response({"preview": cached, "playback_only": True, "source_scope": scope})
            except ValueError:
                _PROXIES.pop(signature, None)
        preview = await asyncio.to_thread(module._create_browser_preview_proxy, ffmpeg, str(path))
        if not preview:
            raise RuntimeError("Browser proxy encoding failed.")
        preview = _move_proxy_to_scope(preview, scope)
        if len(_PROXIES) >= 64:
            _PROXIES.pop(next(iter(_PROXIES)))
        _PROXIES[signature] = preview
        return web.json_response({"preview": preview, "playback_only": True, "source_scope": scope})
    except (ValueError, OSError, RuntimeError) as exc:
        return web.json_response({"error": str(exc)}, status=400)


_PROXIES = {}


@PromptServer.instance.routes.post("/overtli/studio/video-scope")
async def video_scope(request):
    try:
        body = await request.json()
        if not isinstance(body, dict) or not isinstance(body.get("entry"), dict):
            raise ValueError("Choose a video source first.")
        entry = body["entry"]
        path = media_path(entry)
        if path.suffix.lower() not in _VIDEO_EXTENSIONS:
            raise ValueError("Choose a supported video container before frame review.")
        scope = _validated_media_scope(entry, path, body.get("scope"))
        return web.json_response({"scope": scope})
    except _MediaScopeMismatch as exc:
        return web.json_response({"error": str(exc)}, status=403)
    except (ValueError, OSError, RuntimeError) as exc:
        return web.json_response({"error": str(exc)}, status=400)


@PromptServer.instance.routes.post("/overtli/studio/video-inspect")
async def video_inspect(request):
    try:
        body = await request.json()
        entry, path, scope, info = await _source_request(body)
        return web.json_response({"scope": scope, "source": {"filename": entry["filename"], "subfolder": entry.get("subfolder", ""), "type": entry.get("type", "output")}, **info})
    except (ValueError, OSError, RuntimeError) as exc:
        return web.json_response({"error": str(exc)}, status=400)


@PromptServer.instance.routes.post("/overtli/studio/video-frame")
async def video_frame(request):
    temp = None
    try:
        body = await request.json()
        entry, path, scope, info = await _source_request(body)
        index = body.get("frame_index")
        if type(index) is not int:
            raise ValueError("Frame index must be a whole number.")
        indices = _frame_indices([index], info["frame_count"])
        temp, decoded = await _decode_frames(path, indices, info)
        selected, timestamp, image_path = decoded[0]
        response = web.Response(
            body=image_path.read_bytes(),
            content_type="image/png",
            headers={
                "Cache-Control": "no-store",
                "X-Overtli-Frame-Index": str(selected),
                "X-Overtli-Frame-Timestamp": f"{timestamp:.9f}",
                "X-Overtli-Frame-Width": str(info["width"]),
                "X-Overtli-Frame-Height": str(info["height"]),
                "X-Overtli-Frame-Scope": scope,
            },
        )
        return response
    except (ValueError, OSError, RuntimeError) as exc:
        return web.json_response({"error": str(exc)}, status=400)
    finally:
        if temp is not None:
            temp.cleanup()


@PromptServer.instance.routes.post("/overtli/studio/video-frames/extract")
async def video_frames_extract(request):
    temp = None
    created = []
    try:
        body = await request.json()
        entry, path, scope, info = await _source_request(body)
        indices = _frame_indices(body.get("frame_indices"), info["frame_count"])
        temp, decoded = await _decode_frames(path, indices, info)
        directory, subfolder = _input_frames_directory(scope)
        records = []
        for index, timestamp, image_path in decoded:
            filename = _save_frame_file(directory, path.name, index, image_path)
            created.append(directory / filename)
            records.append(_frame_record(index, timestamp, filename, subfolder, info))
        return web.json_response({"scope": scope, "frames": records})
    except (ValueError, OSError, RuntimeError) as exc:
        for path in created:
            try:
                path.unlink()
            except OSError:
                pass
        return web.json_response({"error": str(exc)}, status=400)
    finally:
        if temp is not None:
            temp.cleanup()
