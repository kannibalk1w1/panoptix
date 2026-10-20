from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import sys
import unittest

from panoptix_app.linux_tray import start_linux_tray
from panoptix_app.tray import start_tray


@unittest.skipUnless(sys.platform.startswith('linux'), 'Linux system tray helper')
class LinuxTrayTests(unittest.TestCase):
    def test_linux_uses_native_tray_instead_of_menu_less_xorg_backend(self):
        native = object()
        with patch('panoptix_app.tray.start_linux_tray', return_value=native) as start:
            self.assertIs(start_tray('http://127.0.0.1:1234', object(), object(), object()), native)
            start.assert_called_once_with('http://127.0.0.1:1234')

    def test_parent_controls_helper_and_waits_for_exit(self):
        with TemporaryDirectory() as tmp:
            helper = Path(tmp) / 'helper.py'
            helper.write_text('import sys\nprint("READY", flush=True)\nfor line in sys.stdin:\n    if line.strip() == "quit":\n        break\n')
            with patch('panoptix_app.linux_tray.helper_path', return_value=helper):
                tray = start_linux_tray('http://127.0.0.1:1234')
            self.assertIsNotNone(tray)
            try:
                tray.visible = False
                tray.stop()
                self.assertEqual(tray.process.returncode, 0)
                self.assertFalse(tray.visible)
            finally:
                tray.stop()

    def test_unavailable_helper_does_not_leave_process_or_break_dashboard(self):
        with TemporaryDirectory() as tmp:
            helper = Path(tmp) / 'helper.py'
            helper.write_text('raise SystemExit(1)\n')
            with patch('panoptix_app.linux_tray.helper_path', return_value=helper), self.assertLogs(level='WARNING'):
                self.assertIsNone(start_linux_tray('http://127.0.0.1:1234'))
