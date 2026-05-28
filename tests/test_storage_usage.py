from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panoptix_app.capture import PlaceholderCapture
from panoptix_app.recorder import Recorder
from panoptix_app.server import create_handler
from panoptix_app.storage import SessionStore
from panoptix_app.storage_usage import get_storage_usage


class StorageUsageTests(unittest.TestCase):
    def test_storage_usage_counts_data_bytes_and_session_count(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SessionStore(root)
            session = store.create_session("evidence", {}, {})
            screenshot_dir = store.screenshot_dir(session["id"])
            (screenshot_dir / "001.png").write_bytes(b"12345")

            usage = get_storage_usage(root, warning_mb=1)

            self.assertEqual(usage["session_count"], 1)
            self.assertGreaterEqual(usage["total_bytes"], 5)
            self.assertFalse(usage["warning"])

    def test_storage_api_returns_warning_flag(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SessionStore(root)
            session = store.create_session("evidence", {}, {})
            store.screenshot_dir(session["id"]).joinpath("001.png").write_bytes(b"x" * 2048)
            handler = create_handler(root, store, Recorder(store, PlaceholderCapture()))
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                with urlopen(f"{base_url}/api/storage", timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                self.assertEqual(payload["storage"]["session_count"], 1)
                self.assertIn("total_mb", payload["storage"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
