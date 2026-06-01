from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
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


if __name__ == "__main__":
    unittest.main()
