from pathlib import Path
from tempfile import TemporaryDirectory
import json
import http.client
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.parse import urlparse
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image

from panoptix_app.capture import PlaceholderCapture
from panoptix_app.recorder import Recorder
from panoptix_app.redaction import redact_event_screenshot, restore_original_screenshot
from panoptix_app.server import create_handler
from panoptix_app.storage import SessionStore


class RedactionTests(unittest.TestCase):
    def test_redact_event_screenshot_blacks_rectangle_and_keeps_backup(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SessionStore(root)
            session = store.create_session("evidence", {}, {})
            screenshot_dir = store.screenshot_dir(session["id"])
            image_path = screenshot_dir / "001.png"
            Image.new("RGB", (10, 10), "white").save(image_path)
            store.add_event(session["id"], {"type": "click", "timestamp": "now", "screenshot": "001.png"})

            result = redact_event_screenshot(root, session["id"], 1, {"x": 2, "y": 2, "width": 4, "height": 4})

            with Image.open(image_path) as image:
                self.assertEqual(image.getpixel((3, 3)), (0, 0, 0))
                self.assertEqual(image.getpixel((0, 0)), (255, 255, 255))
            self.assertTrue((screenshot_dir / "originals" / "001.png").exists())
            self.assertEqual(result["event"]["redactions"][0]["type"], "black_box")

    def test_redact_top_bar_endpoint_updates_event(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SessionStore(root)
            session = store.create_session("evidence", {}, {})
            screenshot_dir = store.screenshot_dir(session["id"])
            Image.new("RGB", (100, 100), "white").save(screenshot_dir / "001.png")
            store.add_event(session["id"], {"type": "click", "timestamp": "now", "screenshot": "001.png"})
            handler = create_handler(root, store, Recorder(store, PlaceholderCapture()))
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                payload = self.post_json(
                    f"{base_url}/api/sessions/{session['id']}/events/1/redact",
                    {"preset": "top_strip"},
                )
                self.assertEqual(payload["event"]["redactions"][0]["preset"], "top_strip")
                with Image.open(screenshot_dir / "001.png") as image:
                    self.assertEqual(image.getpixel((10, 10)), (0, 0, 0))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_restore_original_screenshot_removes_redactions(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SessionStore(root)
            session = store.create_session("evidence", {}, {})
            screenshot_dir = store.screenshot_dir(session["id"])
            image_path = screenshot_dir / "001.png"
            Image.new("RGB", (20, 20), "white").save(image_path)
            store.add_event(session["id"], {"type": "click", "timestamp": "now", "screenshot": "001.png"})
            redact_event_screenshot(root, session["id"], 1, {"x": 0, "y": 0, "width": 20, "height": 20})

            result = restore_original_screenshot(root, session["id"], 1)

            with Image.open(image_path) as image:
                self.assertEqual(image.getpixel((10, 10)), (255, 255, 255))
            self.assertEqual(result["event"].get("redactions"), [])

    @staticmethod
    def post_json(url: str, payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        parsed = urlparse(url)
        connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=5)
        connection.request(
            "POST",
            parsed.path,
            body=data,
            headers={"Content-Type": "application/json", "Content-Length": str(len(data))},
        )
        response = connection.getresponse()
        try:
            return json.loads(response.read().decode("utf-8"))
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
