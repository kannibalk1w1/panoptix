from pathlib import Path
from tempfile import TemporaryDirectory
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panoptix_app.app_paths import get_data_root, get_project_root


class AppPathTests(unittest.TestCase):
    def test_data_root_uses_environment_override(self):
        with TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"PANOPTIX_DATA_DIR": tmp}):
                self.assertEqual(get_data_root(), Path(tmp))

    def test_data_root_uses_localappdata_when_available(self):
        with TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"LOCALAPPDATA": tmp}, clear=True):
                self.assertEqual(get_data_root(), Path(tmp) / "Panoptix" / "data")

    def test_project_root_is_parent_of_package(self):
        self.assertTrue((get_project_root() / "panoptix.py").exists())


if __name__ == "__main__":
    unittest.main()
