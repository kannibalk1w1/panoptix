from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sys
import threading
import unittest
from base64 import b64decode
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panoptix_app.capture import PlaceholderCapture
from panoptix_app.recorder import Recorder
from panoptix_app.server import create_handler
from panoptix_app.storage import SessionStore


PNG_BYTES = b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADggGOSHzRgAAAAABJRU5ErkJggg=="
)


class ApiEventUpdateTests(unittest.TestCase):
    def test_patch_event_updates_single_event(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SessionStore(root)
            session = store.create_session("evidence", {}, {})
            store.add_event(
                session["id"],
                {
                    "type": "click",
                    "timestamp": "2026-05-28T10:00:00",
                    "screenshot": "001.png",
                    "x": 10,
                    "y": 20,
                    "title": "",
                    "staff_note": "",
                    "cyp_quote": "",
                    "tags": [],
                },
            )
            handler = create_handler(root, store, Recorder(store, PlaceholderCapture()))
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                result = self.patch_json(
                    f"{base_url}/api/sessions/{session['id']}/events/1",
                    {"title": "Opened Scratch", "tags": ["UAS evidence"]},
                )

                self.assertEqual(result["event"]["title"], "Opened Scratch")
                self.assertEqual(result["event"]["tags"], ["UAS evidence"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_get_screenshot_serves_png(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SessionStore(root)
            session = store.create_session("evidence", {}, {})
            screenshot_dir = store.screenshot_dir(session["id"])
            (screenshot_dir / "001.png").write_bytes(PNG_BYTES)
            handler = create_handler(root, store, Recorder(store, PlaceholderCapture()))
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                with urlopen(f"{base_url}/api/sessions/{session['id']}/screenshots/001.png", timeout=5) as response:
                    self.assertEqual(response.headers["Content-Type"], "image/png")
                    self.assertEqual(response.read(), PNG_BYTES)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    @staticmethod
    def patch_json(url: str, payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        request = Request(url, data=data, method="PATCH", headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
