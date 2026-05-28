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

    def test_status_includes_elapsed_seconds_and_event_count(self):
        with TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp))
            recorder = Recorder(store, PlaceholderCapture())
            recorder.start("evidence", {"cyp": "AB"}, {})
            recorder.capture_click(120, 240)

            status = recorder.status()
            recorder.stop()

            self.assertTrue(status["active"])
            self.assertGreaterEqual(status["elapsed_seconds"], 0)
            self.assertEqual(status["event_count"], 1)

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

    def test_observation_pause_stops_interval_capture_until_resumed(self):
        with TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp))
            recorder = Recorder(store, PlaceholderCapture())
            session = recorder.start("observation", {}, {"interval_seconds": 0.05})

            time.sleep(0.08)
            recorder.pause()
            count_at_pause = len(store.load_session(session["id"])["events"])
            time.sleep(0.14)
            count_while_paused = len(store.load_session(session["id"])["events"])
            recorder.resume()
            time.sleep(0.08)
            recorder.stop()

            final_count = len(store.load_session(session["id"])["events"])
            self.assertEqual(count_while_paused, count_at_pause)
            self.assertGreater(final_count, count_while_paused)


if __name__ == "__main__":
    unittest.main()
