from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panoptix_app.startup import StartupManager


class StartupTests(unittest.TestCase):
    def test_startup_manager_writes_and_removes_user_startup_command(self):
        with TemporaryDirectory() as tmp:
            startup_dir = Path(tmp) / "Startup"
            app_path = Path(tmp) / "Panoptix.exe"
            manager = StartupManager(startup_dir=startup_dir, app_path=app_path)

            manager.set_enabled(True)
            self.assertTrue(manager.is_enabled())
            command = manager.shortcut_path.read_text(encoding="utf-8")
            self.assertIn(str(app_path), command)
            self.assertIn("--background", command)

            manager.set_enabled(False)
            self.assertFalse(manager.is_enabled())


if __name__ == "__main__":
    unittest.main()
