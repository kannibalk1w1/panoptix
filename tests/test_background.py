from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image

from panoptix_app.background import BackgroundScheduler, daily_window_is_active
from panoptix_app.frame_diff import images_are_different


class BackgroundTests(unittest.TestCase):
    def test_daily_window_is_active_inside_simple_time_range(self):
        settings = {
            "background_start_time": "09:00",
            "background_end_time": "15:30",
        }

        self.assertTrue(daily_window_is_active(settings, datetime(2026, 6, 1, 10, 15)))
        self.assertFalse(daily_window_is_active(settings, datetime(2026, 6, 1, 8, 59)))
        self.assertFalse(daily_window_is_active(settings, datetime(2026, 6, 1, 15, 31)))

    def test_frame_difference_ignores_identical_images_and_detects_changes(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first.png"
            same = root / "same.png"
            changed = root / "changed.png"
            Image.new("RGB", (80, 60), "black").save(first)
            Image.new("RGB", (80, 60), "black").save(same)
            Image.new("RGB", (80, 60), "white").save(changed)

            self.assertFalse(images_are_different(first, same, threshold=4))
            self.assertTrue(images_are_different(first, changed, threshold=4))

    def test_scheduler_starts_and_stops_background_session_for_window(self):
        class FakeSettings:
            def __init__(self):
                self.settings = {
                    "background_enabled": True,
                    "background_start_time": "09:00",
                    "background_end_time": "15:30",
                    "background_interval_seconds": 5,
                    "background_change_detection": True,
                    "background_change_threshold": 4,
                }

            def load(self):
                return dict(self.settings)

        class FakeRecorder:
            def __init__(self):
                self.active_mode = None
                self.active_session_id = None
                self.started = []
                self.stopped = 0

            def start(self, mode, metadata, settings):
                self.active_mode = mode
                self.active_session_id = "scheduled-test"
                self.started.append((mode, metadata, settings))
                return {"id": self.active_session_id}

            def stop(self, expected_session_id=None):
                self.stopped += 1
                self.active_mode = None
                self.active_session_id = None

        settings = FakeSettings()
        recorder = FakeRecorder()
        scheduler = BackgroundScheduler(recorder, settings)

        scheduler.evaluate(datetime(2026, 6, 1, 10, 0))
        scheduler.evaluate(datetime(2026, 6, 1, 16, 0))

        self.assertEqual(recorder.started[0][0], "background")
        self.assertEqual(recorder.started[0][2]["interval_seconds"], 5)
        self.assertTrue(recorder.started[0][2]["change_detection"])
        self.assertEqual(recorder.stopped, 1)


if __name__ == "__main__":
    unittest.main()
