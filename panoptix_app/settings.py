from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_SETTINGS: dict[str, Any] = {
    "observation_interval_seconds": 60,
    "retention_days": 30,
    "storage_warning_mb": 500,
    "default_evidence_purpose": "UAS evidence",
    "marker_shape": "circle",
    "marker_color": "#ef233c",
    "marker_size": 32,
    "marker_stroke": 3,
}


class SettingsStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.path = self.root / "settings.json"

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return dict(DEFAULT_SETTINGS)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return {**DEFAULT_SETTINGS, **data}

    def update(self, changes: dict[str, Any]) -> dict[str, Any]:
        settings = self.load()
        for key in DEFAULT_SETTINGS:
            if key in changes:
                settings[key] = self._coerce(key, changes[key])
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        return settings

    @staticmethod
    def _coerce(key: str, value: Any) -> Any:
        if key == "marker_size":
            return max(6, int(value))
        if key in {"observation_interval_seconds", "retention_days", "storage_warning_mb", "marker_size", "marker_stroke"}:
            return max(1, int(value))
        return str(value)
