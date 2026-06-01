from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panoptix_app.hotkeys import HotkeyService
from panoptix_app.settings import SettingsStore


class FakeListener:
    def __init__(self, mapping):
        self.mapping = mapping
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


class HotkeyTests(unittest.TestCase):
    def test_hotkey_service_registers_configured_manual_capture_hotkey(self):
        with TemporaryDirectory() as tmp:
            settings = SettingsStore(Path(tmp))
            settings.update({"manual_hotkey": "<ctrl>+<alt>+m", "manual_hotkey_enabled": True})
            created = []

            def factory(mapping):
                listener = FakeListener(mapping)
                created.append(listener)
                return listener

            service = HotkeyService(settings, recorder=object(), listener_factory=factory)
            service.start()

            self.assertTrue(created[0].started)
            self.assertIn("<ctrl>+<alt>+m", created[0].mapping)
            service.stop()
            self.assertTrue(created[0].stopped)


if __name__ == "__main__":
    unittest.main()
