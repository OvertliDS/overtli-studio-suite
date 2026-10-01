"""Focused source-scope and exact-frame tests for the standalone review wall."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "video_tools.py"


class _Routes:
    @staticmethod
    def post(_path):
        return lambda function: function


_MEDIA_ROOTS = {"input": None, "output": None, "temp": None}
folder_paths_stub = types.ModuleType("folder_paths")
folder_paths_stub.get_input_directory = lambda: str(_MEDIA_ROOTS["input"])
folder_paths_stub.get_output_directory = lambda: str(_MEDIA_ROOTS["output"])
folder_paths_stub.get_temp_directory = lambda: str(_MEDIA_ROOTS["temp"])
server_stub = types.ModuleType("server")
server_stub.PromptServer = types.SimpleNamespace(instance=types.SimpleNamespace(routes=_Routes()))
sys.modules.setdefault("folder_paths", folder_paths_stub)
sys.modules.setdefault("server", server_stub)

spec = importlib.util.spec_from_file_location("overtli_video_tools_test_target", SOURCE)
video_tools = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = video_tools
spec.loader.exec_module(video_tools)


class VideoToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="overtli-video-tools-test-")
        base = Path(self.temp.name)
        for key in _MEDIA_ROOTS:
            _MEDIA_ROOTS[key] = base / key
            _MEDIA_ROOTS[key].mkdir()
        video_tools._EXTERNAL_SCOPES.clear()
        video_tools._FRAME_INFO_CACHE.clear()

    def tearDown(self):
        self.temp.cleanup()

    def test_addtl_and_normal_media_scope_are_based_on_resolved_roots(self):
        normal = _MEDIA_ROOTS["temp"] / "ordinary.mp4"
        addtl = _MEDIA_ROOTS["temp"] / "OvertliDS" / "addtl" / "review.mp4"
        normal.parent.mkdir(parents=True, exist_ok=True)
        addtl.parent.mkdir(parents=True, exist_ok=True)
        normal.write_bytes(b"normal")
        addtl.write_bytes(b"addtl")
        self.assertEqual(video_tools._managed_media_scope(normal), "normal")
        self.assertEqual(video_tools._managed_media_scope(addtl), "addtl")
        self.assertEqual(video_tools._validated_media_scope({"type": "temp"}, addtl, "addtl"), "addtl")
        with self.assertRaisesRegex(ValueError, "cannot be opened"):
            video_tools._validated_media_scope({"type": "temp"}, addtl, "normal")

    def test_media_paths_reject_parent_traversal_outside_the_registered_root(self):
        outside = Path(self.temp.name) / "outside.mp4"
        outside.write_bytes(b"video")
        with self.assertRaisesRegex(ValueError, "outside its registered root"):
            video_tools.media_path({"type": "input", "subfolder": "..", "filename": outside.name})
        with self.assertRaisesRegex(ValueError, "outside its registered root"):
            video_tools.media_path({"type": "input", "subfolder": "", "filename": str(outside)})

    def test_external_scope_requires_execution_registration_or_matching_sidecar(self):
        external = Path(self.temp.name) / "outside.mp4"
        external.write_bytes(b"saved-video")
        entry = {"type": "external", "token": "legacy-token", "_overtli_scope": "addtl"}
        with self.assertRaisesRegex(ValueError, "no verified Normal/Addtl scope"):
            video_tools._validated_media_scope(entry, external, "addtl")

        identity = video_tools.register_external_scope("saved-token", external, "addtl")
        self.assertEqual(identity, video_tools._media_identity(external))
        self.assertEqual(video_tools._sidecar_scope(external), "addtl")
        video_tools._EXTERNAL_SCOPES.clear()
        self.assertEqual(video_tools._validated_media_scope({**entry, "token": "saved-token"}, external, "addtl"), "addtl")

        external.write_bytes(b"new-video-content")
        with self.assertRaisesRegex(ValueError, "no verified Normal/Addtl scope"):
            video_tools._validated_media_scope({**entry, "token": "saved-token"}, external, "addtl")

    def test_registered_external_scope_cannot_override_a_managed_island(self):
        managed = _MEDIA_ROOTS["input"] / "OvertliDS" / "addtl" / "source.mp4"
        managed.parent.mkdir(parents=True)
        managed.write_bytes(b"video")
        with self.assertRaisesRegex(ValueError, "different Normal/Addtl island"):
            video_tools.register_external_scope("token", managed, "normal")

    def test_executed_scope_requires_unambiguous_save_workflow_evidence(self):
        workflow = {"workflow": {"nodes": [
            {"id": "10", "type": "OvertliStudioSuite", "properties": {"overtliAddtl": True}},
            {"id": "20", "type": "OvertliDirectorSaveVideo", "properties": {}},
        ]}}
        self.assertEqual(video_tools._executed_workflow_scope(workflow, "20"), "addtl")
        workflow["workflow"]["extra"] = {"overtliAddtl": False}
        self.assertEqual(video_tools._executed_workflow_scope(workflow, "20"), "normal")
        workflow["workflow"].pop("extra")
        workflow["workflow"]["nodes"].append({
            "id": "11", "type": "OvertliStudioSuite", "properties": {"overtliAddtl": False},
        })
        self.assertIsNone(video_tools._executed_workflow_scope(workflow, "20"), "mixed Director modes stay unscoped")
        self.assertIsNone(video_tools._workflow_scope({
            "left": {"overtliAddtl": True}, "right": {"overtliAddtl": False},
        }))

    def test_frame_indices_and_work_limits_reject_unbounded_requests(self):
        self.assertEqual(video_tools._frame_indices([0, 3, 2], 4), [0, 2, 3])
        for indices in ([], list(range(33)), [True], [0, 0], [-1], [4]):
            with self.subTest(indices=indices), self.assertRaises(ValueError):
                video_tools._frame_indices(indices, 4)
        with self.assertRaisesRegex(ValueError, "pixel extraction budget"):
            asyncio.run(video_tools._decode_frames(Path("unused"), list(range(17)), {
                "width": 4000, "height": 4000,
            }))

    def test_frame_output_directories_keep_their_scope_and_reject_escape_symlinks(self):
        normal, normal_subfolder = video_tools._input_frames_directory("normal")
        addtl, addtl_subfolder = video_tools._input_frames_directory("addtl")
        self.assertEqual(normal_subfolder, "OvertliDS/references/frames")
        self.assertEqual(addtl_subfolder, "OvertliDS/addtl/frames")
        self.assertTrue(normal.is_relative_to(_MEDIA_ROOTS["input"].resolve()))
        self.assertTrue(addtl.is_relative_to(_MEDIA_ROOTS["input"].resolve()))

        link = _MEDIA_ROOTS["input"] / "OvertliDS" / "addtl"
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        shutil.rmtree(link)
        try:
            link.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("This Windows account does not permit temporary directory symlinks.")
        with self.assertRaisesRegex(ValueError, "escapes"):
            video_tools._input_frames_directory("addtl")

    def test_ffprobe_metadata_and_png_extraction_preserve_source_order_and_pts(self):
        ffmpeg = shutil.which("ffmpeg")
        ffprobe = shutil.which("ffprobe")
        if not ffmpeg or not ffprobe:
            self.skipTest("The configured media runtime has no ffmpeg/ffprobe executable.")
        source = Path(self.temp.name) / "source.mkv"
        subprocess.run([
            ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
            "testsrc=size=32x24:rate=4:duration=1", "-vf", "setpts=PTS+3/TB",
            "-fps_mode", "passthrough", "-c:v", "ffv1", "-an", str(source),
        ], check=True, timeout=30)

        async def inspect_and_extract():
            info = await video_tools._inspect_video(source)
            temporary, frames = await video_tools._decode_frames(source, [0, 2, 3], info)
            try:
                return info, [(index, timestamp, path.read_bytes()[:8]) for index, timestamp, path in frames]
            finally:
                temporary.cleanup()

        info, frames = asyncio.run(inspect_and_extract())
        self.assertEqual((info["width"], info["height"]), (32, 24))
        self.assertEqual(info["frame_count"], 4)
        self.assertAlmostEqual(info["avg_fps"], 4.0)
        self.assertEqual([row[0] for row in frames], [0, 2, 3])
        self.assertEqual([row[2] for row in frames], [b"\x89PNG\r\n\x1a\n"] * 3)
        self.assertGreater(frames[0][1], 2.9, "reported time retains the non-zero source PTS")
        self.assertAlmostEqual(frames[1][1] - frames[0][1], 0.5, places=3)

    def test_decoder_process_timeout_is_bounded(self):
        with self.assertRaisesRegex(RuntimeError, "time limit"):
            asyncio.run(video_tools._run_frame_process(
                [sys.executable, "-c", "import time; time.sleep(2)"], 0.05,
            ))


if __name__ == "__main__":
    unittest.main(verbosity=2)
