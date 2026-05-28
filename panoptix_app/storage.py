from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import VALID_MODES, now_iso


class SessionStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.sessions_dir = self.root / "sessions"
        self.exports_dir = self.root / "exports"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)

    def create_session(
        self,
        mode: str,
        metadata: dict[str, Any] | None = None,
        settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if mode not in VALID_MODES:
            raise ValueError(f"Unsupported mode: {mode}")

        session_id = self._new_session_id(mode)
        session_dir = self._session_dir(session_id)
        (session_dir / "screenshots").mkdir(parents=True, exist_ok=True)
        session = {
            "id": session_id,
            "mode": mode,
            "metadata": metadata or {},
            "settings": settings or {},
            "started": now_iso(),
            "stopped": None,
            "events": [],
        }
        self._write_session(session)
        return session

    def list_sessions(self) -> list[dict[str, Any]]:
        summaries = []
        for path in self.sessions_dir.glob("*/session.json"):
            session = self._read_json(path)
            metadata = session.get("metadata", {})
            title = metadata.get("activity") or metadata.get("cyp") or session["id"]
            summaries.append(
                {
                    "id": session["id"],
                    "mode": session["mode"],
                    "title": title,
                    "started": session["started"],
                    "stopped": session.get("stopped"),
                    "event_count": len(session.get("events", [])),
                }
            )
        return sorted(summaries, key=lambda item: (item["started"], item["id"]), reverse=True)

    def load_session(self, session_id: str) -> dict[str, Any]:
        self._validate_session_id(session_id)
        path = self._session_dir(session_id) / "session.json"
        if not path.exists():
            raise FileNotFoundError(session_id)
        return self._read_json(path)

    def update_session(self, session_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        session = self.load_session(session_id)
        for key in ("metadata", "settings", "events"):
            if key in changes:
                session[key] = changes[key]
        self._write_session(session)
        return session

    def add_event(self, session_id: str, event: dict[str, Any]) -> dict[str, Any]:
        session = self.load_session(session_id)
        event = dict(event)
        event["index"] = len(session["events"]) + 1
        session["events"].append(event)
        self._write_session(session)
        return session

    def update_event(self, session_id: str, event_index: int, changes: dict[str, Any]) -> dict[str, Any]:
        session = self.load_session(session_id)
        allowed = {"title", "staff_note", "cyp_quote", "tags", "highlight", "redactions"}
        for event in session["events"]:
            if event.get("index") == event_index:
                for key, value in changes.items():
                    if key in allowed:
                        event[key] = value
                self._write_session(session)
                return session
        raise KeyError(f"Event not found: {event_index}")

    def delete_event(self, session_id: str, event_index: int) -> dict[str, Any]:
        session = self.load_session(session_id)
        original_count = len(session["events"])
        session["events"] = [event for event in session["events"] if event.get("index") != event_index]
        if len(session["events"]) == original_count:
            raise KeyError(f"Event not found: {event_index}")
        for index, event in enumerate(session["events"], start=1):
            event["index"] = index
        self._write_session(session)
        return session

    def stop_session(self, session_id: str) -> dict[str, Any]:
        session = self.load_session(session_id)
        session["stopped"] = now_iso()
        self._write_session(session)
        return session

    def delete_session(self, session_id: str) -> None:
        self._validate_session_id(session_id)
        shutil.rmtree(self._session_dir(session_id), ignore_errors=True)
        shutil.rmtree(self.exports_dir / session_id, ignore_errors=True)

    def screenshot_dir(self, session_id: str) -> Path:
        self._validate_session_id(session_id)
        path = self._session_dir(session_id) / "screenshots"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def next_screenshot_name(self, session_id: str) -> str:
        session = self.load_session(session_id)
        return f"{len(session['events']) + 1:03d}.png"

    def _new_session_id(self, mode: str) -> str:
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        base = f"{stamp}_{mode}"
        candidate = base
        counter = 2
        while self._session_dir(candidate).exists():
            candidate = f"{base}_{counter}"
            counter += 1
        return candidate

    def _session_dir(self, session_id: str) -> Path:
        return self.sessions_dir / session_id

    def _write_session(self, session: dict[str, Any]) -> None:
        path = self._session_dir(session["id"]) / "session.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(session, indent=2), encoding="utf-8")

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _validate_session_id(session_id: str) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", session_id):
            raise ValueError("Invalid session id")
