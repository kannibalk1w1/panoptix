from __future__ import annotations

from pathlib import Path


def get_storage_usage(root: Path, warning_mb: int) -> dict:
    root = Path(root)
    total_bytes = 0
    if root.exists():
        for path in root.rglob("*"):
            if path.is_file():
                total_bytes += path.stat().st_size
    sessions_dir = root / "sessions"
    session_count = len([path for path in sessions_dir.iterdir() if path.is_dir()]) if sessions_dir.exists() else 0
    total_mb = round(total_bytes / (1024 * 1024), 2)
    return {
        "root": str(root),
        "session_count": session_count,
        "total_bytes": total_bytes,
        "total_mb": total_mb,
        "warning_mb": warning_mb,
        "warning": total_mb >= warning_mb,
    }
