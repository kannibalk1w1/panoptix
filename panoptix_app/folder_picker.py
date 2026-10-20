from __future__ import annotations

import os
import subprocess
import sys
import shutil
from typing import Any, Callable
from pathlib import Path


PICKER_SCRIPT = """
Add-Type -AssemblyName System.Windows.Forms | Out-Null
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = 'Choose a folder for Panoptix'
$dialog.ShowNewFolderButton = $true
if ($env:PANOPTIX_PICKER_START) { $dialog.SelectedPath = $env:PANOPTIX_PICKER_START }
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $dialog.SelectedPath }
"""


def is_available() -> bool:
    return sys.platform == "win32" or (sys.platform.startswith("linux") and shutil.which("kdialog") is not None)


def pick_folder(initial: str = "", runner: Callable[[str], str] | None = None) -> dict[str, Any]:
    if runner is None:
        if not is_available():
            return {
                "available": False,
                "path": "",
                "cancelled": False,
                "error": "Install kdialog on Linux to browse folders, or type the folder path instead.",
            }
        runner = run_linux_picker if sys.platform.startswith("linux") else run_windows_picker
    try:
        selected = (runner(initial) or "").strip()
    except Exception as exc:
        return {"available": True, "path": "", "cancelled": False, "error": str(exc)}
    if not selected:
        return {"available": True, "path": "", "cancelled": True, "error": ""}
    return {"available": True, "path": selected, "cancelled": False, "error": ""}


def run_windows_picker(initial: str) -> str:
    env = dict(os.environ)
    env["PANOPTIX_PICKER_START"] = str(initial or "")
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result = subprocess.run(
        ["powershell", "-NoProfile", "-STA", "-Command", PICKER_SCRIPT],
        capture_output=True,
        text=True,
        env=env,
        timeout=600,
        creationflags=creationflags,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "The folder browser could not be opened.")
    return result.stdout.strip()


def run_linux_picker(initial: str) -> str:
    result = subprocess.run(
        ["kdialog", "--title", "Choose a folder for Panoptix", "--getexistingdirectory", initial or str(Path.home())],
        capture_output=True, text=True, timeout=600,
    )
    if result.returncode == 1:
        return ""
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "The folder browser could not be opened")
    return result.stdout.strip()
