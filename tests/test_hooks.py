from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panoptix_app.capture import PlaceholderCapture
from panoptix_app.recorder import Recorder
from panoptix_app.storage import SessionStore


class SlowCapture(PlaceholderCapture):
    def capture(self, output_dir, filename, marker=None):
        time.sleep(0.2)
        return super().capture(output_dir, filename, marker)


class FakeHook:
    def __init__(self, on_click):
        self.on_click = on_click
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def emit_click(self, x, y):
        self.on_click(x, y)


class HookFactory:
    def __init__(self):
        self.hooks = []

    def __call__(self, on_click):
        hook = FakeHook(on_click)
        self.hooks.append(hook)
        return hook


class HookIntegrationTests(unittest.TestCase):
    def test_evidence_mode_starts_hook_and_records_forwarded_clicks(self):
        with TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp))
            hook_factory = HookFactory()
            recorder = Recorder(store, PlaceholderCapture(), hook_factory=hook_factory)
            session = recorder.start("evidence", {}, {})

            hook_factory.hooks[0].emit_click(320, 180)
            recorder.stop()

            loaded = store.load_session(session["id"])
            self.assertTrue(hook_factory.hooks[0].started)
            self.assertTrue(hook_factory.hooks[0].stopped)
            self.assertEqual(loaded["events"][0]["type"], "click")
            self.assertEqual(loaded["events"][0]["x"], 320)
            self.assertEqual(loaded["events"][0]["y"], 180)

    def test_forwarded_hook_click_does_not_block_on_screenshot_capture(self):
        with TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp))
            hook_factory = HookFactory()
            recorder = Recorder(store, SlowCapture(), hook_factory=hook_factory)
            session = recorder.start("evidence", {}, {})

            start = time.perf_counter()
            hook_factory.hooks[0].emit_click(320, 180)
            elapsed = time.perf_counter() - start
            recorder.stop()

            loaded = store.load_session(session["id"])
            self.assertLess(elapsed, 0.1)
            self.assertEqual(loaded["events"][0]["type"], "click")

    def test_observation_mode_does_not_start_click_hook(self):
        with TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp))
            hook_factory = HookFactory()
            recorder = Recorder(store, PlaceholderCapture(), hook_factory=hook_factory)

            recorder.start("observation", {}, {"interval_seconds": 60})
            recorder.stop()

            self.assertEqual(hook_factory.hooks, [])


if __name__ == "__main__":
    unittest.main()
