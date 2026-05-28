from __future__ import annotations

from datetime import datetime, timedelta

from .storage import SessionStore


def cleanup_old_sessions(store: SessionStore, retention_days: int, now: datetime | None = None) -> dict:
    now = now or datetime.now()
    cutoff = now - timedelta(days=max(1, int(retention_days)))
    deleted: list[str] = []
    kept: list[str] = []
    for summary in store.list_sessions():
        started = _parse_started(summary.get("started", ""))
        if started < cutoff:
            store.delete_session(summary["id"])
            deleted.append(summary["id"])
        else:
            kept.append(summary["id"])
    return {
        "retention_days": retention_days,
        "cutoff": cutoff.replace(microsecond=0).isoformat(),
        "deleted": deleted,
        "kept": kept,
    }


def _parse_started(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.now()
