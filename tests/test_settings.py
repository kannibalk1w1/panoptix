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


class SettingsTests(unittest.TestCase):
    def test_settings_store_returns_defaults_and_persists_updates(self):
        with TemporaryDirectory() as tmp:
            store = SettingsStore(Path(tmp))

            defaults = store.load()
            updated = store.update({"observation_interval_seconds": 120, "retention_days": 14})
            reloaded = SettingsStore(Path(tmp)).load()

            self.assertEqual(defaults["observation_interval_seconds"], 60)
            self.assertEqual(defaults["marker_shape"], "circle")
            self.assertEqual(defaults["marker_color"], "#ef233c")
            self.assertEqual(updated["observation_interval_seconds"], 120)
            self.assertEqual(reloaded["retention_days"], 14)
            self.assertEqual(reloaded["storage_warning_mb"], 500)

    def test_settings_api_get_and_patch(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SessionStore(root)
            handler = create_handler(root, store, Recorder(store, PlaceholderCapture()))
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                original = self.get_json(f"{base_url}/api/settings")
                updated = self.patch_json(
                    f"{base_url}/api/settings",
                    {
                        "observation_interval_seconds": 90,
                        "retention_days": 30,
                        "marker_shape": "crosshair",
                        "marker_size": 44,
                        "marker_stroke": 5,
                    },
                )

                self.assertEqual(original["settings"]["observation_interval_seconds"], 60)
                self.assertEqual(updated["settings"]["observation_interval_seconds"], 90)
                self.assertEqual(updated["settings"]["retention_days"], 30)
                self.assertEqual(updated["settings"]["marker_shape"], "crosshair")
                self.assertEqual(updated["settings"]["marker_size"], 44)
                self.assertEqual(updated["settings"]["marker_stroke"], 5)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    @staticmethod
    def get_json(url: str) -> dict:
        with urlopen(url, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def patch_json(url: str, payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        request = Request(url, data=data, method="PATCH", headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
