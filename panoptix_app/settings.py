from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .persistence import synchronized, write_json
from .schedule import validate_weekly_schedule


DEFAULT_SETTINGS: dict[str, Any] = {
    "observation_interval_seconds": 60,
    "background_enabled": False,
    "background_start_time": "09:00",
    "background_end_time": "15:30",
    "background_weekly_schedule": None,
    "background_interval_seconds": 5,
    "background_change_detection": True,
    "background_change_threshold": 4,
    "manual_hotkey_enabled": True,
    "manual_hotkey": "<ctrl>+<alt>+p",
    "launch_on_startup": False,
    "retention_days": 30,
    "storage_warning_mb": 500,
    "default_evidence_purpose": "UAS evidence",
    "export_directory": "",
    "marker_shape": "circle",
    "marker_color": "#ef233c",
    "marker_size": 32,
    "marker_stroke": 3,
}


class SettingsStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.path = self.root / "settings.json"
        self.last_good = dict(DEFAULT_SETTINGS)

    def set_root(self, root: Path) -> None:
        """Point at a new data folder. The background scheduler and hotkey
        service hold this instance, so mutating it keeps them in step when the
        screenshot folder changes."""
        self.root = Path(root)
        self.path = self.root / "settings.json"
        self.last_good = dict(DEFAULT_SETTINGS)

    @synchronized
    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            self.last_good = dict(DEFAULT_SETTINGS)
            return dict(self.last_good)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Settings file must contain a JSON object")
        self.last_good = {**DEFAULT_SETTINGS, **data}
        self.last_good["background_weekly_schedule"] = validate_weekly_schedule(self.last_good["background_weekly_schedule"])
        return dict(self.last_good)

    @synchronized
    def update(self, changes: dict[str, Any]) -> dict[str, Any]:
        settings = self.load()
        for key in DEFAULT_SETTINGS:
            if key in changes:
                settings[key] = self._coerce(key, changes[key])
        self.path.parent.mkdir(parents=True, exist_ok=True)
        write_json(self.path, settings)
        self.last_good = dict(settings)
        return settings

    @staticmethod
    def _coerce(key: str, value: Any) -> Any:
        if key == "background_weekly_schedule":
            return validate_weekly_schedule(value)
        if key in {"background_enabled", "background_change_detection", "manual_hotkey_enabled", "launch_on_startup"}:
            if isinstance(value, str):
                return value.strip().lower() in {"1", "true", "yes", "on"}
            return bool(value)
        if key == "marker_size":
            return max(6, int(value))
        if key in {
            "observation_interval_seconds",
            "background_interval_seconds",
            "background_change_threshold",
            "retention_days",
            "storage_warning_mb",
            "marker_size",
            "marker_stroke",
        }:
            return max(1, int(value))
        return str(value)
