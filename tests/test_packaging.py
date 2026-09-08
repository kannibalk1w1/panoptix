from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def installer_file_sources() -> list[str]:
    text = (PROJECT_ROOT / "installer" / "panoptix.iss").read_text(encoding="utf-8")
    section = text.split("[Files]", 1)[1].split("[", 1)[0]
    return re.findall(r'Source:\s*"([^"]+)"', section)


class InstallerContentsTests(unittest.TestCase):
    def test_installer_ships_only_the_executable(self):
        self.assertEqual(installer_file_sources(), ["..\\dist\\{#AppExeName}"])

    def test_installer_ships_no_markdown(self):
        # Loose Markdown in Program Files got testers antivirus and
        # unwanted-file warnings, and nothing reads these at runtime.
        markdown = [src for src in installer_file_sources() if src.lower().endswith(".md")]
        self.assertEqual(markdown, [])


class SpecTests(unittest.TestCase):
    def setUp(self):
        self.spec = (PROJECT_ROOT / "panoptix.spec").read_text(encoding="utf-8")

    def test_upx_is_disabled(self):
        # UPX-packed executables trip antivirus heuristics far more often.
        self.assertIn("upx=False", self.spec)
        self.assertNotIn("upx=True", self.spec)

    def test_executable_carries_a_version_resource(self):
        self.assertIn("version=version_resource", self.spec)
        self.assertTrue((PROJECT_ROOT / "installer" / "version_info.txt").exists())


if __name__ == "__main__":
    unittest.main()
