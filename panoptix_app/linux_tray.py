"""Launch KDE's Qt StatusNotifier tray using the distribution's Qt libraries."""
from __future__ import annotations

import logging
from contextlib import suppress
import os
from pathlib import Path
import select
import subprocess
import sys
import threading


class LinuxTray:
    def __init__(self, process: subprocess.Popen):
        self.process = process
        self._lock = threading.Lock()

    def _send(self, command: bytes) -> None:
        with self._lock:
            if self.process.poll() is not None:
                return
            try:
                self.process.stdin.write(command + b"\n")
                self.process.stdin.flush()
            except (BrokenPipeError, OSError, ValueError):
                pass

    @property
    def visible(self):
        return self.process.poll() is None

    @visible.setter
    def visible(self, value):
        self._send(b"show" if value else b"hide")

    def stop(self) -> None:
        self._send(b"quit")
        try:
            self.process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                self.process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=0.5)
        finally:
            with suppress(BrokenPipeError, OSError):
                self.process.stdin.close()
            self.process.stdout.close()


def helper_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "helpers" / "qt_tray.py"
    return Path(__file__).with_name("qt_tray.py")


def start_linux_tray(url: str) -> LinuxTray | None:
    # Use Arch's matching Python/Qt pair, not PyInstaller's embedded Python.
    env = dict(os.environ)
    if getattr(sys, "frozen", False):
        if "LD_LIBRARY_PATH_ORIG" in env:
            env["LD_LIBRARY_PATH"] = env["LD_LIBRARY_PATH_ORIG"]
        else:
            env.pop("LD_LIBRARY_PATH", None)
        env.pop("PYTHONHOME", None)
        env.pop("PYTHONPATH", None)
    try:
        process = subprocess.Popen(
            ["/usr/bin/python3", str(helper_path()), url],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env,
        )
    except OSError:
        logging.exception("Could not start the native Linux tray")
        return None
    tray = LinuxTray(process)
    if select.select([process.stdout], [], [], 3)[0] and process.stdout.readline() == b"READY\n":
        return tray
    logging.warning("Native Linux tray unavailable; install python-pyqt6. Quit remains available on the dashboard or with --quit.")
    tray.stop()
    return None
