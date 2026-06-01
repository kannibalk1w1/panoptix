from __future__ import annotations

import os
import sys
from pathlib import Path


class StartupManager:
    def __init__(self, startup_dir: Path | None = None, app_path: Path | None = None):
        self.startup_dir = startup_dir or self._default_startup_dir()
        self.app_path = app_path or Path(sys.executable)
        self.shortcut_path = self.startup_dir / "Panoptix.cmd"

    def is_enabled(self) -> bool:
        return self.shortcut_path.exists()

    def set_enabled(self, enabled: bool) -> None:
        if enabled:
            self.startup_dir.mkdir(parents=True, exist_ok=True)
            self.shortcut_path.write_text(self._command(), encoding="utf-8")
        else:
            self.shortcut_path.unlink(missing_ok=True)

    def _command(self) -> str:
        target = str(self.app_path)
        if target.lower().endswith(".exe"):
            return f'@echo off\nstart "" "{target}" --background\n'
        script = Path(__file__).resolve().parents[1] / "panoptix.py"
        return f'@echo off\nstart "" "{target}" "{script}" --background\n'

    @staticmethod
    def _default_startup_dir() -> Path:
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        return Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
