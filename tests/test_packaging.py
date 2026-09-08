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


class InstallerSetupTests(unittest.TestCase):
    def setUp(self):
        self.iss = (PROJECT_ROOT / "installer" / "panoptix.iss").read_text(encoding="utf-8")

    def test_installs_as_64_bit(self):
        # Panoptix.exe is PE32+; a 32-bit install would leave a dead shortcut.
        self.assertIn("ArchitecturesAllowed=x64compatible", self.iss)
        self.assertIn("ArchitecturesInstallIn64BitMode=x64compatible", self.iss)

    def test_reinstall_closes_the_running_tray_app(self):
        self.assertIn("CloseApplications=yes", self.iss)

    def test_shortcuts_point_at_the_installed_executable(self):
        shortcuts = re.findall(r'^Name:\s*"([^"]+)";\s*Filename:\s*"([^"]+)"', self.iss, re.MULTILINE)
        desktop = [target for name, target in shortcuts if "autodesktop" in name]
        self.assertEqual(desktop, ["{app}\\{#AppExeName}"])


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
