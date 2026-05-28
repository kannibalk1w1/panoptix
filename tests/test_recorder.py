from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panoptix_app.capture import PlaceholderCapture
from panoptix_app.recorder import Recorder
from panoptix_app.storage import SessionStore


class RecorderTests(unittest.TestCase):
    def test_evidence_click_records_coordinates(self):
        with TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp))
            recorder = Recorder(store, PlaceholderCapture())
            session = recorder.start("evidence", {"cyp": "AB"}, {})

            event = recorder.capture_click(120, 240)
            recorder.stop()

            loaded = store.load_session(session["id"])
            self.assertEqual(event["type"], "click")
            self.assertEqual(event["x"], 120)
            self.assertEqual(event["y"], 240)
            self.assertEqual(len(loaded["events"]), 1)

    def test_observation_periodic_records_without_coordinates(self):
        with TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp))
            recorder = Recorder(store, PlaceholderCapture())
            session = recorder.start("observation", {"activity": "Roblox studio"}, {})

            event = recorder.capture_periodic()
            recorder.stop()

            loaded = store.load_session(session["id"])
            self.assertEqual(event["type"], "periodic")
            self.assertNotIn("x", event)
            self.assertEqual(loaded["events"][0]["screenshot"], "001.png")

    def test_capture_requires_active_session(self):
        with TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp))
            recorder = Recorder(store, PlaceholderCapture())

            with self.assertRaises(RuntimeError):
                recorder.capture_periodic()

    def test_observation_mode_captures_on_interval_until_stopped(self):
        with TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp))
            recorder = Recorder(store, PlaceholderCapture())
            session = recorder.start("observation", {}, {"interval_seconds": 0.05})

            time.sleep(0.16)
            recorder.stop()

            loaded = store.load_session(session["id"])
            self.assertGreaterEqual(len(loaded["events"]), 2)
            self.assertTrue(all(event["type"] == "periodic" for event in loaded["events"]))


if __name__ == "__main__":
    unittest.main()
