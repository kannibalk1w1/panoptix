from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panoptix_app.capture import PlaceholderCapture
from panoptix_app.recorder import Recorder
from panoptix_app.server import create_handler
from panoptix_app.settings import SettingsStore
from panoptix_app.storage import SessionStore


class FakeHotkeys:
    error = "keyboard listener unavailable"


class FakeStartup:
    def is_enabled(self):
        return False


class ServerTests(unittest.TestCase):
    def test_start_stop_and_list_sessions(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SessionStore(root)
            recorder = Recorder(store, PlaceholderCapture())
            handler = create_handler(root, store, recorder)
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                started = self.post_json(
                    f"{base_url}/api/record/start",
                    {
                        "mode": "evidence",
                        "metadata": {"cyp": "AB", "activity": "Scratch game"},
                        "settings": {},
                    },
                )
                status = self.get_json(f"{base_url}/api/status")
                stopped = self.post_json(f"{base_url}/api/record/stop", {})
                sessions = self.get_json(f"{base_url}/api/sessions")

                self.assertEqual(started["session"]["mode"], "evidence")
                self.assertTrue(status["active"])
                self.assertEqual(stopped["session"]["id"], started["session"]["id"])
                self.assertEqual(sessions["sessions"][0]["title"], "Scratch game")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_status_includes_background_hotkey_startup_and_export_health(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            SettingsStore(root).update(
                {
                    "background_enabled": True,
                    "background_start_time": "09:00",
                    "background_end_time": "15:30",
                    "manual_hotkey": "<ctrl>+<alt>+m",
                    "manual_hotkey_enabled": True,
                    "launch_on_startup": True,
                }
            )
            store = SessionStore(root)
            recorder = Recorder(store, PlaceholderCapture())
            handler = create_handler(root, store, recorder, FakeHotkeys(), FakeStartup())
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                status = self.get_json(f"{base_url}/api/status")

                self.assertEqual(status["background"]["window"], "09:00-15:30")
                self.assertTrue(status["background"]["enabled"])
                self.assertEqual(status["hotkey"]["shortcut"], "<ctrl>+<alt>+m")
                self.assertEqual(status["hotkey"]["error"], "keyboard listener unavailable")
                self.assertTrue(status["startup"]["requested"])
                self.assertFalse(status["startup"]["installed"])
                self.assertIn("path", status["export_destination"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_data_location_can_be_pointed_at_another_folder(self):
        with (
            TemporaryDirectory() as tmp,
            TemporaryDirectory() as config,
            TemporaryDirectory() as share,
            TemporaryDirectory() as local,
        ):
            root = Path(tmp)
            chosen = str(Path(share) / "network-evidence")
            default_root = Path(local) / "Panoptix" / "data"
            store = SessionStore(root)
            recorder = Recorder(store, PlaceholderCapture())
            handler = create_handler(root, store, recorder)
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                with patch.dict(
                    os.environ,
                    {"PANOPTIX_CONFIG_DIR": config, "LOCALAPPDATA": local},
                    clear=False,
                ):
                    before = self.get_json(f"{base_url}/api/data-location")["data_location"]
                    saved = self.patch_json(f"{base_url}/api/data-location", {"directory": chosen})["data_location"]
                    status = self.get_json(f"{base_url}/api/status")
                    session = self.post_json(
                        f"{base_url}/api/record/start",
                        {"mode": "observation", "metadata": {"cyp": "Test"}},
                    )["session"]
                    self.post_json(f"{base_url}/api/record/stop", {})
                    reset = self.patch_json(f"{base_url}/api/data-location", {"directory": ""})["data_location"]

                self.assertEqual(before["configured_directory"], "")
                self.assertEqual(before["active_path"], str(root))
                self.assertEqual(saved["configured_directory"], chosen)
                self.assertEqual(saved["path"], chosen)
                self.assertTrue(Path(chosen).exists())
                self.assertEqual(status["data_location"]["configured_directory"], chosen)
                self.assertEqual(reset["configured_directory"], "")

                # The new folder is used straight away rather than after a restart.
                self.assertFalse(saved["restart_required"])
                self.assertEqual(saved["active_path"], chosen)
                self.assertTrue((Path(chosen) / "sessions" / session["id"]).exists())
                self.assertFalse((root / "sessions" / session["id"]).exists())
                self.assertEqual(reset["active_path"], str(default_root))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_data_location_rejects_unusable_folder(self):
        with TemporaryDirectory() as tmp, TemporaryDirectory() as config:
            root = Path(tmp)
            blocker = Path(tmp) / "blocked.txt"
            blocker.write_text("blocked", encoding="utf-8")
            store = SessionStore(root)
            recorder = Recorder(store, PlaceholderCapture())
            handler = create_handler(root, store, recorder)
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                with patch.dict(os.environ, {"PANOPTIX_CONFIG_DIR": config}, clear=False):
                    response = self.patch_json(
                        f"{base_url}/api/data-location", {"directory": str(blocker / "evidence")}
                    )
                    current = self.get_json(f"{base_url}/api/data-location")["data_location"]

                self.assertIn("That folder cannot be used", response["error"])
                self.assertEqual(current["configured_directory"], "")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    @staticmethod
    def get_json(url: str) -> dict:
        with urlopen(url, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def post_json(url: str, payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        request = Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def patch_json(url: str, payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        request = Request(url, data=data, method="PATCH", headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=5) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            with error:
                return json.loads(error.read().decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
