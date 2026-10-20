from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen

from PIL import Image, ImageSequence

from panoptix_app.capture import PlaceholderCapture
from panoptix_app.clips import ClipRecorder
from panoptix_app.hotkeys import HotkeyService
from panoptix_app.recorder import Recorder
from panoptix_app.server import DataContext, create_handler
from panoptix_app.settings import SettingsStore
from panoptix_app.storage import SessionStore
from tests.test_hotkeys import FakeListener


class ChangingCapture:
    def __init__(self, delay=0):
        self.count = 0
        self.delay = delay

    def capture(self, folder, filename):
        time.sleep(self.delay)
        self.count += 1
        path = folder / filename
        Image.new("RGB", (1200, 600), (self.count * 30, 20, 100)).save(path)
        return path


class ClipTests(unittest.TestCase):
    def test_timed_clip_keeps_originals_and_exports_valid_gif_with_timing(self):
        with TemporaryDirectory() as tmp:
            recorder = ClipRecorder(Path(tmp), ChangingCapture())
            result = recorder.start({"clip_duration_seconds": 1, "clip_fps": 5})
            recorder._thread.join(timeout=5)
            self.assertFalse(recorder.status()["active"])
            self.assertIsNone(recorder.status()["error"])
            folder = Path(result["folder"])
            manifest = json.loads((folder / "clip.json").read_text())
            self.assertEqual(len(manifest["frames"]), 5)
            self.assertEqual(manifest["duration_seconds"], 1)
            with Image.open(folder / "frames" / "frame_000000.png") as original:
                self.assertEqual(original.size, (1200, 600))
            with Image.open(folder / "clip.gif") as gif:
                self.assertEqual(gif.n_frames, 5)
                self.assertEqual(gif.size, (960, 480))
                self.assertEqual(gif.info["loop"], 0)
                self.assertEqual(sum(frame.info["duration"] for frame in ImageSequence.Iterator(gif)), 1000)
                gif.seek(4)
                self.assertEqual(gif.convert("RGB").getpixel((0, 0)), (150, 20, 100))

    def test_slow_capture_skips_deadlines_and_gif_keeps_elapsed_timing(self):
        with TemporaryDirectory() as tmp:
            recorder = ClipRecorder(Path(tmp), ChangingCapture(delay=0.21))
            recorder.start({"clip_duration_seconds": 1, "clip_fps": 10})
            recorder._thread.join(timeout=5)
            self.assertIsNone(recorder.status()["error"])
            folder = Path(recorder.status()["folder"])
            manifest = json.loads((folder / "clip.json").read_text())
            self.assertLess(len(manifest["frames"]), 10)
            with Image.open(folder / "clip.gif") as gif:
                self.assertEqual(sum(frame.info["duration"] for frame in ImageSequence.Iterator(gif)), 1000)

    def test_repeat_start_rejected_and_early_stop_keeps_pngs_without_gif(self):
        with TemporaryDirectory() as tmp:
            recorder = ClipRecorder(Path(tmp), PlaceholderCapture())
            recorder.start({"clip_make_gif": False})
            with self.assertRaises(RuntimeError):
                recorder.start({})
            recorder.close()
            self.assertFalse(recorder.status()["active"])
            self.assertIsNone(recorder.status()["error"])
            folder = Path(recorder.status()["folder"])
            self.assertTrue((folder / "clip.json").exists())
            self.assertFalse((folder / "clip.gif").exists())

    def test_capture_and_export_failures_report_error_and_preserve_frames(self):
        for failure in ("capture", "export"):
            with self.subTest(failure=failure), TemporaryDirectory() as tmp:
                capture = ChangingCapture()
                recorder = ClipRecorder(Path(tmp), capture)
                real_capture = capture.capture

                def fail_after_one(folder, filename):
                    if capture.count:
                        raise OSError("Storage disconnected")
                    return real_capture(folder, filename)

                target = patch.object(capture, "capture", side_effect=fail_after_one) if failure == "capture" else patch("panoptix_app.clips.export_gif", side_effect=OSError("GIF failed"))
                with target:
                    recorder.start({"clip_duration_seconds": 1, "clip_fps": 5})
                    recorder._thread.join(timeout=5)
                self.assertFalse(recorder.status()["active"])
                self.assertIn("failed", recorder.status()["error"])
                self.assertTrue((Path(recorder.status()["folder"]) / "frames" / "frame_000000.png").exists())

    def test_hotkey_starts_clip_without_active_evidence_session(self):
        with TemporaryDirectory() as tmp:
            settings = SettingsStore(Path(tmp))
            settings.update({"manual_hotkey_enabled": False, "clip_hotkey_enabled": True})
            recorder = ClipRecorder(Path(tmp), PlaceholderCapture())
            service = HotkeyService(settings, object(), FakeListener, clip_recorder=recorder)
            service.start()
            try:
                service.listener.mapping["<ctrl>+<alt>+r"]()
                self.assertTrue(recorder.status()["active"])
                folder = recorder.status()["folder"]
                service.listener.mapping["<ctrl>+<alt>+r"]()
                self.assertEqual(recorder.status()["folder"], folder)
            finally:
                recorder.close()
                service.stop()

    def test_folder_switch_blocked_during_clip_and_follows_new_root_after_stop(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SessionStore(root)
            clips = ClipRecorder(root, PlaceholderCapture())
            context = DataContext(root, store, Recorder(store), clips=clips)
            clips.start({"clip_make_gif": False})
            with self.assertRaises(ValueError):
                context.switch_root(root / "new")
            clips.close()
            context.switch_root(root / "new")
            result = clips.start({"clip_make_gif": False})
            clips.close()
            self.assertTrue(Path(result["folder"]).is_relative_to(root / "new" / "clips"))

    def test_settings_validate_clip_limits_and_shortcut_collision(self):
        with TemporaryDirectory() as tmp:
            settings = SettingsStore(Path(tmp))
            for payload in ({"clip_fps": 0}, {"clip_fps": 31}, {"clip_duration_seconds": 121},
                            {"clip_hotkey_enabled": True, "clip_hotkey": "<ctrl>+<alt>+p"}):
                with self.subTest(payload=payload), self.assertRaises(ValueError):
                    settings.update(payload)
            updated = settings.update({"clip_duration_seconds": 30, "clip_fps": 15, "clip_make_gif": "false"})
            self.assertEqual(updated["clip_fps"], 15)
            self.assertFalse(SettingsStore(Path(tmp)).load()["clip_make_gif"])

    def test_clip_api_and_status(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SessionStore(root)
            SettingsStore(root).update({"clip_make_gif": False})
            clips = ClipRecorder(root, PlaceholderCapture())
            handler = create_handler(root, store, Recorder(store), clips=clips)
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_address[1]}"

            def request(path, method="GET"):
                req = Request(base + path, data=b"{}" if method == "POST" else None, method=method, headers={"Content-Type": "application/json"})
                with urlopen(req, timeout=5) as response:
                    return json.load(response)
            try:
                request("/api/clips/start", "POST")
                status = request("/api/status")
                self.assertTrue(status["clip"]["active"])
                self.assertFalse(status["active"])
                request("/api/clips/stop", "POST")
                clips.close()
                with patch("panoptix_app.server.open_folder") as opener:
                    request("/api/clips/open-folder", "POST")
                    opener.assert_called_once_with(root / "clips")
            finally:
                clips.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
