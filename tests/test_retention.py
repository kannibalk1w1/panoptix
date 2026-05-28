from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime, timedelta
import json
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panoptix_app.capture import PlaceholderCapture
from panoptix_app.recorder import Recorder
from panoptix_app.retention import cleanup_old_sessions
from panoptix_app.server import create_handler
from panoptix_app.storage import SessionStore


class RetentionTests(unittest.TestCase):
    def test_cleanup_old_sessions_deletes_only_sessions_older_than_cutoff(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SessionStore(root)
            old_session = store.create_session("evidence", {"activity": "Old"}, {})
            recent_session = store.create_session("evidence", {"activity": "Recent"}, {})
            self.set_started(store, old_session["id"], datetime.now() - timedelta(days=45))
            self.set_started(store, recent_session["id"], datetime.now() - timedelta(days=5))

            result = cleanup_old_sessions(store, retention_days=30)

            self.assertEqual(result["deleted"], [old_session["id"]])
            self.assertFalse((root / "sessions" / old_session["id"]).exists())
            self.assertTrue((root / "sessions" / recent_session["id"]).exists())

    def test_retention_api_deletes_old_sessions_using_saved_setting(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SessionStore(root)
            old_session = store.create_session("evidence", {"activity": "Old"}, {})
            self.set_started(store, old_session["id"], datetime.now() - timedelta(days=45))
            (root / "settings.json").write_text(json.dumps({"retention_days": 30}), encoding="utf-8")
            handler = create_handler(root, store, Recorder(store, PlaceholderCapture()))
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                request = Request(f"{base_url}/api/retention/cleanup", data=b"{}", method="POST")
                with urlopen(request, timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))

                self.assertEqual(payload["deleted"], [old_session["id"]])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    @staticmethod
    def set_started(store: SessionStore, session_id: str, started: datetime) -> None:
        session = store.load_session(session_id)
        session["started"] = started.replace(microsecond=0).isoformat()
        store.update_session(session_id, {"metadata": session["metadata"], "settings": session["settings"], "events": session["events"]})
        path = store.sessions_dir / session_id / "session.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["started"] = session["started"]
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
