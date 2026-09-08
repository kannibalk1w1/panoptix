from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any

from .models import VALID_MODES, now_iso
from .persistence import data_lock, synchronized, write_json


def session_transaction(function):
    @wraps(function)
    def wrapped(root, *args, **kwargs):
        store = root if isinstance(root, SessionStore) else SessionStore(Path(root))
        with store.transaction():
            return function(store, *args, **kwargs)
    return wrapped


class SessionStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.sessions_dir = self.root / "sessions"
        self.exports_dir = self.root / "exports"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)

    def transaction(self):
        return data_lock(self.root)

    @synchronized
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

    @synchronized
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

    @synchronized
    def load_session(self, session_id: str) -> dict[str, Any]:
        self._validate_session_id(session_id)
        path = self._session_dir(session_id) / "session.json"
        if not path.exists():
            raise FileNotFoundError(session_id)
        return self._read_json(path)

    @synchronized
    def update_session(self, session_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        session = self.load_session(session_id)
        for key in ("metadata", "settings", "events"):
            if key in changes:
                session[key] = changes[key]
        self._write_session(session)
        return session

    @synchronized
    def add_event(self, session_id: str, event: dict[str, Any]) -> dict[str, Any]:
        session = self.load_session(session_id)
        event = dict(event)
        event["index"] = len(session["events"]) + 1
        event.setdefault("selected_for_export", True)
        session["events"].append(event)
        self._write_session(session)
        return session

    @synchronized
    def update_event(self, session_id: str, event_index: int, changes: dict[str, Any]) -> dict[str, Any]:
        session = self.load_session(session_id)
        allowed = {
            "title",
            "staff_note",
            "cyp_quote",
            "tags",
            "highlight",
            "redactions",
            "selected_for_export",
            "marker",
        }
        for event in session["events"]:
            if event.get("index") == event_index:
                if "expected_screenshot" in changes and changes["expected_screenshot"] != event.get("screenshot"):
                    raise ValueError("This screenshot changed position; reload the session before saving")
                for key, value in changes.items():
                    if key in allowed:
                        event[key] = value
                self._write_session(session)
                return session
        raise KeyError(f"Event not found: {event_index}")

    @synchronized
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

    @synchronized
    def stop_session(self, session_id: str) -> dict[str, Any]:
        session = self.load_session(session_id)
        session["stopped"] = now_iso()
        self._write_session(session)
        return session

    @synchronized
    def delete_session(self, session_id: str) -> None:
        source = self._session_dir(session_id)
        exports = self._contained(self.exports_dir, session_id)
        if not source.exists() and not exports.exists():
            raise FileNotFoundError(session_id)
        try:
            title = self.load_session(session_id).get("metadata", {}).get("activity") or session_id
        except (OSError, ValueError):
            # A corrupt or half-written session must still be removable.
            title = session_id
        trash = self._trash_dir(uuid.uuid4().hex)
        trash.mkdir(parents=True)
        write_json(trash / "entry.json", {"session_id": session_id, "title": title, "deleted_at": now_iso()})
        try:
            self._move_parts([(source, trash / "session"), (exports, trash / "exports")])
        except Exception:
            if not (trash / "session").exists() and not (trash / "exports").exists():
                (trash / "entry.json").unlink()
                trash.rmdir()
            raise

    def _trash_dir(self, trash_id: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{32}", trash_id):
            raise ValueError("Invalid deleted-session id")
        parent = self._contained(self.root, "trash")
        return self._contained(parent, trash_id)

    @staticmethod
    def _move_parts(parts) -> None:
        moved = []
        try:
            for source, target in parts:
                if source.exists():
                    source.rename(target)
                    moved.append((source, target))
        except Exception:
            for source, target in reversed(moved):
                target.rename(source)
            raise

    @synchronized
    def list_trash(self) -> list[dict[str, Any]]:
        entries = []
        parent = self._contained(self.root, "trash")
        for path in parent.glob("*/entry.json"):
            try:
                directory = self._trash_dir(path.parent.name)
                entry = self._read_json(path)
            except (OSError, ValueError):
                # Folders Panoptix did not write, such as a sync tool's conflicted
                # copy, are left alone rather than failing every listing.
                continue
            if not isinstance(entry, dict) or not isinstance(entry.get("session_id"), str):
                continue
            entries.append(
                {
                    **entry,
                    "trash_id": directory.name,
                    "title": entry.get("title") or entry["session_id"],
                    "deleted_at": entry.get("deleted_at") or "",
                    "restorable": (directory / "session" / "session.json").is_file(),
                }
            )
        return sorted(entries, key=lambda entry: entry["deleted_at"], reverse=True)

    @synchronized
    def purge_trash(self, trash_id: str) -> dict[str, Any]:
        """Permanently remove one deleted session. This cannot be undone."""
        trash = self._trash_dir(trash_id)
        if not trash.is_dir():
            raise FileNotFoundError("Deleted session not found")
        try:
            session_id = self._read_json(trash / "entry.json").get("session_id")
        except (OSError, ValueError):
            session_id = None
        shutil.rmtree(trash)
        return {"trash_id": trash_id, "session_id": session_id}

    @synchronized
    def empty_trash(self) -> list[str]:
        return [self.purge_trash(entry["trash_id"])["session_id"] for entry in self.list_trash()]

    @synchronized
    def restore_session(self, trash_id: str) -> dict[str, Any]:
        trash = self._trash_dir(trash_id)
        entry = self._read_json(trash / "entry.json")
        session_id = entry["session_id"]
        target = self._session_dir(session_id)
        exports = self._contained(self.exports_dir, session_id)
        source = self._contained(trash, "session")
        source_exports = self._contained(trash, "exports")
        if target.exists() or exports.exists():
            raise ValueError("A session or export folder with this id already exists; restore would overwrite it")
        if not (source / "session.json").is_file():
            raise FileNotFoundError("Deleted session is incomplete")
        self._move_parts([(source, target), (source_exports, exports)])
        (trash / "entry.json").unlink()
        trash.rmdir()
        try:
            return self.load_session(session_id)
        except (OSError, ValueError):
            # The files are back in place even though this session's JSON cannot
            # be read; report that rather than failing a restore that already happened.
            return {"id": session_id, "unreadable": True}

    def screenshot_dir(self, session_id: str) -> Path:
        self._validate_session_id(session_id)
        path = self._contained(self._session_dir(session_id), "screenshots")
        path.mkdir(parents=True, exist_ok=True)
        return path

    @synchronized
    def next_screenshot_name(self, session_id: str) -> str:
        session = self.load_session(session_id)
        directory = self.screenshot_dir(session_id)
        if "next_screenshot_number" in session:
            number = max(1, int(session["next_screenshot_number"]))
        else:
            # Migrate old sessions, including orphaned files retained by removal.
            names = [path.stem for path in directory.rglob("*.png")]
            names.extend(Path(event.get("screenshot", "")).stem for event in session["events"])
            number = max((int(name) for name in names if name.isdigit()), default=0) + 1
        while (directory / f"{number:03d}.png").exists() or (directory / "originals" / f"{number:03d}.png").exists():
            number += 1
        session["next_screenshot_number"] = number + 1
        self._write_session(session)
        return f"{number:03d}.png"

    def _new_session_id(self, mode: str) -> str:
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        base = f"{stamp}_{mode}"
        candidate = base
        counter = 2
        reserved = {entry["session_id"] for entry in self.list_trash()}
        while self._session_dir(candidate).exists() or candidate in reserved:
            candidate = f"{base}_{counter}"
            counter += 1
        return candidate

    def _session_dir(self, session_id: str) -> Path:
        self._validate_session_id(session_id)
        return self._contained(self.sessions_dir, session_id)

    @staticmethod
    def _contained(parent: Path, name: str) -> Path:
        target = parent / name
        if target.is_symlink() or target.resolve().parent != parent.resolve():
            raise ValueError("Path must be a direct child of the evidence folder")
        return target

    def _write_session(self, session: dict[str, Any]) -> None:
        path = self._session_dir(session["id"]) / "session.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json(path, session)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _validate_session_id(session_id: str) -> None:
        if session_id in {".", ".."} or not re.fullmatch(r"[A-Za-z0-9_.-]+", session_id):
            raise ValueError("Invalid session id")
