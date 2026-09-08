from __future__ import annotations

from datetime import datetime, timedelta

from .storage import SessionStore


def preview_cleanup(store: SessionStore, retention_days: int, now: datetime | None = None, protected_session_id: str | None = None) -> dict:
    now = now or datetime.now()
    cutoff = now - timedelta(days=max(1, int(retention_days)))
    sessions = []
    kept: list[str] = []
    for summary in store.list_sessions():
        started = _parse_started(summary.get("started", ""))
        if started < cutoff and summary["id"] != protected_session_id:
            sessions.append(summary)
        else:
            kept.append(summary["id"])
    # Deleted sessions are kept for the same retention period, then purged for
    # good. Without this the retention policy would never free any disk space.
    expired_trash = [entry for entry in store.list_trash() if _parse_started(entry["deleted_at"]) < cutoff]
    return {
        "retention_days": retention_days,
        "cutoff": cutoff.replace(microsecond=0).isoformat(),
        "sessions": sessions,
        "kept": kept,
        "expired_trash": expired_trash,
    }


def cleanup_old_sessions(
    store: SessionStore,
    retention_days: int,
    now: datetime | None = None,
    protected_session_id: str | None = None,
    session_ids: list[str] | None = None,
    trash_ids: list[str] | None = None,
) -> dict:
    with store.transaction():
        preview = preview_cleanup(store, retention_days, now, protected_session_id)
        deleted = []
        for session in preview["sessions"]:
            if session_ids is None or session["id"] in session_ids:
                store.delete_session(session["id"])
                deleted.append(session["id"])
            else:
                preview["kept"].append(session["id"])
        purged = []
        for entry in preview["expired_trash"]:
            if trash_ids is None or entry["trash_id"] in trash_ids:
                store.purge_trash(entry["trash_id"])
                purged.append(entry["session_id"])
        return {**preview, "deleted": deleted, "purged": purged}


def _parse_started(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.now()
