from __future__ import annotations

import os
import sys
from pathlib import Path

from .app_config import get_configured_data_directory


def get_project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[1]


def default_data_root() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "Panoptix" / "data"
    return get_project_root() / "data"


def normalize_directory(directory: str) -> Path:
    return Path(str(directory).strip().strip('"')).expanduser()


def directory_problem(directory: Path) -> str:
    """Return an empty string when the folder can be created and written to."""
    directory = Path(directory)
    probe = directory / ".panoptix-write-test"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe.write_text("ok", encoding="utf-8")
    except OSError as exc:
        return str(exc)
    finally:
        try:
            probe.unlink(missing_ok=True)
        except OSError:
            pass
    return ""


def resolve_data_root() -> dict:
    default_root = default_data_root()
    override = os.environ.get("PANOPTIX_DATA_DIR")
    if override:
        requested = normalize_directory(override)
        return _status(requested, requested, default_root, using_configured=True, warning="")

    configured = get_configured_data_directory()
    if not configured:
        return _status(default_root, default_root, default_root, using_configured=False, warning="")

    requested = normalize_directory(configured)
    problem = directory_problem(requested)
    if problem:
        warning = (
            f"Configured data folder is not usable, so Panoptix is using local storage instead: {problem}"
        )
        return _status(default_root, requested, default_root, using_configured=False, warning=warning)
    return _status(requested, requested, default_root, using_configured=True, warning="")


def get_data_root() -> Path:
    return Path(resolve_data_root()["path"])


def _status(
    path: Path,
    requested: Path,
    default_root: Path,
    using_configured: bool,
    warning: str,
) -> dict:
    return {
        "path": str(path),
        "requested_path": str(requested),
        "default_path": str(default_root),
        "configured_directory": get_configured_data_directory(),
        "using_configured_directory": using_configured,
        "fallback_used": bool(warning),
        "writable": not warning,
        "warning": warning,
    }
