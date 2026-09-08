from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panoptix_app.capture import ScreenCapture, to_image_coordinates
from panoptix_app.recorder import Recorder
from panoptix_app.storage import SessionStore


class NoopHook:
    def __init__(self, callback):
        self.callback = callback

    def start(self):
        return None

    def stop(self):
        return None


class FakeShot:
    def __init__(self, size, rgb):
        self.size = size
        self.rgb = rgb


class FakeMSS:
    """Two monitors: the primary, and one sitting to the left of it."""

    monitors = [
        {"left": -1920, "top": 0, "width": 3840, "height": 1080},
        {"left": 0, "top": 0, "width": 1920, "height": 1080},
        {"left": -1920, "top": 0, "width": 1920, "height": 1080},
    ]

    def __init__(self):
        self.grabbed = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def grab(self, monitor):
        self.grabbed = monitor
        size = (monitor["width"], monitor["height"])
        return FakeShot(size, b"\x20\x27\x33" * (size[0] * size[1]))


class MultiMonitorCaptureTests(unittest.TestCase):
    def capture_with_fake_screen(self, output_dir, marker=None):
        fake = FakeMSS()
        module = type(sys)("mss")
        module.mss = lambda: fake
        capture = ScreenCapture()
        with patch.dict(sys.modules, {"mss": module}):
            path = capture.capture(Path(output_dir), "001.png", marker)
        return capture, fake, path

    def test_capture_spans_every_monitor(self):
        with TemporaryDirectory() as tmp:
            capture, fake, path = self.capture_with_fake_screen(tmp)

            from PIL import Image

            with Image.open(path) as image:
                self.assertEqual(image.size, (3840, 1080))
            # monitors[0] is the whole virtual desktop, not just the primary.
            self.assertEqual(fake.grabbed, FakeMSS.monitors[0])
            self.assertEqual(capture.last_origin, (-1920, 0))

    def test_click_on_secondary_monitor_maps_onto_the_image(self):
        # A click 10px into the left-hand monitor is at x=-1910 in desktop
        # coordinates but 10px from the left edge of the captured image.
        self.assertEqual(to_image_coordinates(-1910, 40, (-1920, 0)), (10, 40))
        self.assertEqual(to_image_coordinates(100, 40, (0, 0)), (100, 40))

    def test_recorder_stores_image_and_screen_coordinates(self):
        class LeftMonitorCapture:
            last_origin = (-1920, 0)

            def capture(self, output_dir, filename, marker=None):
                from PIL import Image

                output_dir.mkdir(parents=True, exist_ok=True)
                path = output_dir / filename
                Image.new("RGB", (3840, 1080), "#202733").save(path)
                return path

        with TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp))
            recorder = Recorder(store, LeftMonitorCapture(), hook_factory=NoopHook)
            recorder.start("evidence", {}, {})
            event = recorder.capture_click(-1910, 40)

            self.assertEqual((event["x"], event["y"]), (10, 40))
            self.assertEqual((event["screen_x"], event["screen_y"]), (-1910, 40))


if __name__ == "__main__":
    unittest.main()
