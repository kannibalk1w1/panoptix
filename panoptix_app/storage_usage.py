from __future__ import annotations

from pathlib import Path


def _directory_bytes(directory: Path) -> int:
    if not directory.exists():
        return 0
    return sum(path.stat().st_size for path in directory.rglob("*") if path.is_file())


def get_storage_usage(root: Path, warning_mb: int) -> dict:
    root = Path(root)
    total_bytes = _directory_bytes(root)
    sessions_dir = root / "sessions"
    trash_dir = root / "trash"
    session_count = len([path for path in sessions_dir.iterdir() if path.is_dir()]) if sessions_dir.exists() else 0
    # Deleted sessions keep using disk until they are purged, so report them
    # separately rather than leaving an unexplained gap in the total.
    trash_bytes = _directory_bytes(trash_dir)
    trash_count = len([path for path in trash_dir.iterdir() if path.is_dir()]) if trash_dir.exists() else 0
    total_mb = round(total_bytes / (1024 * 1024), 2)
    return {
        "root": str(root),
        "session_count": session_count,
        "total_bytes": total_bytes,
        "total_mb": total_mb,
        "trash_bytes": trash_bytes,
        "trash_mb": round(trash_bytes / (1024 * 1024), 2),
        "trash_count": trash_count,
        "warning_mb": warning_mb,
        "warning": total_mb >= warning_mb,
    }
