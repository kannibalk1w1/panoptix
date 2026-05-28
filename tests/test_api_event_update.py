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

from PIL import Image

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
                    {"title": "Opened Scratch", "tags": ["UAS evidence"], "selected_for_export": False},
                )

                self.assertEqual(result["event"]["title"], "Opened Scratch")
                self.assertEqual(result["event"]["tags"], ["UAS evidence"])
                self.assertFalse(result["event"]["selected_for_export"])
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

    def test_marker_endpoint_updates_click_marker(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SessionStore(root)
            session = store.create_session("evidence", {}, {})
            screenshot_dir = store.screenshot_dir(session["id"])
            original_dir = screenshot_dir / "originals"
            original_dir.mkdir()
            Image.new("RGB", (80, 80), "white").save(original_dir / "001.png")
            Image.new("RGB", (80, 80), "white").save(screenshot_dir / "001.png")
            store.add_event(
                session["id"],
                {
                    "type": "click",
                    "timestamp": "2026-05-28T10:00:00",
                    "screenshot": "001.png",
                    "original_screenshot": "originals/001.png",
                    "x": 40,
                    "y": 40,
                },
            )
            handler = create_handler(root, store, Recorder(store, PlaceholderCapture()))
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                result = self.post_json(
                    f"{base_url}/api/sessions/{session['id']}/events/1/marker",
                    {"shape": "square", "color": "#0000ff", "size": 20, "stroke": 2},
                )

                self.assertEqual(result["event"]["marker"]["shape"], "square")
                with Image.open(screenshot_dir / "001.png") as image:
                    self.assertNotEqual(image.getpixel((30, 30)), (255, 255, 255))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_delete_event_removes_event(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SessionStore(root)
            session = store.create_session("evidence", {}, {})
            store.add_event(session["id"], {"type": "click", "timestamp": "one", "screenshot": "001.png"})
            handler = create_handler(root, store, Recorder(store, PlaceholderCapture()))
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                request = Request(f"{base_url}/api/sessions/{session['id']}/events/1", method="DELETE")
                with urlopen(request, timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                self.assertEqual(payload["session"]["events"], [])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_delete_session_removes_session_directory(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SessionStore(root)
            session = store.create_session("evidence", {}, {})
            handler = create_handler(root, store, Recorder(store, PlaceholderCapture()))
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                request = Request(f"{base_url}/api/sessions/{session['id']}", method="DELETE")
                with urlopen(request, timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                self.assertTrue(payload["ok"])
                self.assertFalse((root / "sessions" / session["id"]).exists())
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

    @staticmethod
    def post_json(url: str, payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        request = Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
