from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


VALID_MODES = {"evidence", "observation"}


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


@dataclass
class SessionSummary:
    id: str
    mode: str
    title: str
    started: str
    stopped: str | None
    event_count: int


@dataclass
class Session:
    id: str
    mode: str
    metadata: dict[str, Any] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)
    started: str = field(default_factory=now_iso)
    stopped: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "mode": self.mode,
            "metadata": self.metadata,
            "settings": self.settings,
            "started": self.started,
            "stopped": self.stopped,
            "events": self.events,
        }
