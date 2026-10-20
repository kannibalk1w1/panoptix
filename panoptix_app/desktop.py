"""Desktop capabilities shared by the Linux capture and shortcut integrations."""
from __future__ import annotations

import os
import sys


def is_wayland() -> bool:
    # Some launchers expose DISPLAY through Xwayland and override SESSION_TYPE.
    # The desktop-session path still identifies the underlying compositor.
    return sys.platform.startswith("linux") and bool(
        os.environ.get("WAYLAND_DISPLAY")
        or os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
        or "wayland" in os.environ.get("DESKTOP_SESSION", "").lower()
    )


def is_kde() -> bool:
    return "kde" in os.environ.get("XDG_CURRENT_DESKTOP", "").lower() or "plasma" in os.environ.get("DESKTOP_SESSION", "").lower()
