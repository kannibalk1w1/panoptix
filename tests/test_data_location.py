from pathlib import Path
from tempfile import TemporaryDirectory
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panoptix_app.app_config import (
    get_config_path,
    get_configured_data_directory,
    load_config,
    set_configured_data_directory,
)
from panoptix_app.app_paths import (
    default_data_root,
    directory_problem,
    get_data_root,
    normalize_directory,
    resolve_data_root,
)
from panoptix_app.folder_picker import pick_folder


class ConfigTests(unittest.TestCase):
    def test_config_defaults_to_empty_data_directory(self):
        with TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"PANOPTIX_CONFIG_DIR": tmp}, clear=True):
                self.assertEqual(get_configured_data_directory(), "")

    def test_configured_data_directory_persists(self):
        with TemporaryDirectory() as tmp, TemporaryDirectory() as share:
            with patch.dict(os.environ, {"PANOPTIX_CONFIG_DIR": tmp}, clear=True):
                set_configured_data_directory(share)

                self.assertTrue(get_config_path().exists())
                self.assertEqual(get_configured_data_directory(), share)
                self.assertEqual(load_config()["data_directory"], share)

    def test_unreadable_config_falls_back_to_defaults(self):
        with TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"PANOPTIX_CONFIG_DIR": tmp}, clear=True):
                get_config_path().write_text("not json", encoding="utf-8")

                self.assertEqual(get_configured_data_directory(), "")


class DataRootTests(unittest.TestCase):
    def test_configured_folder_is_used_for_screenshots(self):
        with TemporaryDirectory() as tmp, TemporaryDirectory() as local, TemporaryDirectory() as share:
            chosen = str(Path(share) / "panoptix-evidence")
            with patch.dict(
                os.environ,
                {"PANOPTIX_CONFIG_DIR": tmp, "LOCALAPPDATA": local},
                clear=True,
            ):
                set_configured_data_directory(chosen)
                status = resolve_data_root()

                self.assertEqual(status["path"], chosen)
                self.assertTrue(status["using_configured_directory"])
                self.assertFalse(status["fallback_used"])
                self.assertEqual(status["warning"], "")
                self.assertEqual(get_data_root(), Path(chosen))

    def test_unusable_configured_folder_falls_back_to_default(self):
        with TemporaryDirectory() as tmp, TemporaryDirectory() as local:
            blocker = Path(local) / "not-a-folder.txt"
            blocker.write_text("blocked", encoding="utf-8")
            with patch.dict(
                os.environ,
                {"PANOPTIX_CONFIG_DIR": tmp, "LOCALAPPDATA": local},
                clear=True,
            ):
                set_configured_data_directory(str(blocker / "evidence"))
                status = resolve_data_root()

                self.assertEqual(status["path"], str(default_data_root()))
                self.assertFalse(status["using_configured_directory"])
                self.assertTrue(status["fallback_used"])
                self.assertIn("not usable", status["warning"])

    def test_environment_override_wins_over_configured_folder(self):
        with TemporaryDirectory() as tmp, TemporaryDirectory() as share, TemporaryDirectory() as override:
            with patch.dict(
                os.environ,
                {"PANOPTIX_CONFIG_DIR": tmp, "PANOPTIX_DATA_DIR": override},
                clear=True,
            ):
                set_configured_data_directory(share)

                self.assertEqual(get_data_root(), Path(override))

    def test_directory_problem_reports_unusable_folders(self):
        with TemporaryDirectory() as tmp:
            usable = Path(tmp) / "usable"
            blocked = Path(tmp) / "blocked.txt"
            blocked.write_text("blocked", encoding="utf-8")

            self.assertEqual(directory_problem(usable), "")
            self.assertNotEqual(directory_problem(blocked / "child"), "")

    def test_normalize_directory_strips_quotes_and_whitespace(self):
        self.assertEqual(normalize_directory('  "/srv/share/evidence" '), Path("/srv/share/evidence"))


class FolderPickerTests(unittest.TestCase):
    def test_selected_folder_is_returned(self):
        result = pick_folder(initial="C:/", runner=lambda initial: "\\\\server\\evidence\n")

        self.assertEqual(result["path"], "\\\\server\\evidence")
        self.assertFalse(result["cancelled"])
        self.assertEqual(result["error"], "")

    def test_cancelled_dialog_reports_no_path(self):
        result = pick_folder(runner=lambda initial: "")

        self.assertEqual(result["path"], "")
        self.assertTrue(result["cancelled"])

    def test_picker_failure_is_reported(self):
        def broken(initial):
            raise RuntimeError("dialog failed")

        result = pick_folder(runner=broken)

        self.assertEqual(result["path"], "")
        self.assertEqual(result["error"], "dialog failed")

    def test_picker_is_unavailable_off_windows(self):
        with patch("panoptix_app.folder_picker.sys.platform", "linux"):
            result = pick_folder()

        self.assertFalse(result["available"])
        self.assertIn("Windows", result["error"])


if __name__ == "__main__":
    unittest.main()
