"""One-shot captions for deliberate captures, with a native Windows prompt."""
from __future__ import annotations

from contextlib import nullcontext
import json
import os
import subprocess
import sys
import threading
import time


PROMPT_SCRIPT = r"""
Add-Type -AssemblyName System.Windows.Forms | Out-Null
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public class PanoptixFocus {
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr handle);
}
'@
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$previousWindow = [PanoptixFocus]::GetForegroundWindow()
$initial = $env:PANOPTIX_CAPTURE_NOTE | ConvertFrom-Json
$form = New-Object System.Windows.Forms.Form
$form.Text = 'Panoptix - Caption next capture'
$form.ClientSize = New-Object System.Drawing.Size(520, 310)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.MinimizeBox = $false
$form.TopMost = $true
$help = New-Object System.Windows.Forms.Label
$help.Text = 'Save, then perform the action. Applies to the next click capture, manual screenshot or clip.'
$help.SetBounds(16, 12, 488, 36)
$titleLabel = New-Object System.Windows.Forms.Label
$titleLabel.Text = 'Title / instruction (optional)'
$titleLabel.SetBounds(16, 54, 488, 20)
$title = New-Object System.Windows.Forms.TextBox
$title.Text = $initial.title
$title.MaxLength = 200
$title.SetBounds(16, 76, 488, 26)
$noteLabel = New-Object System.Windows.Forms.Label
$noteLabel.Text = 'Context note (optional)'
$noteLabel.SetBounds(16, 114, 488, 20)
$note = New-Object System.Windows.Forms.TextBox
$note.Text = $initial.staff_note
$note.Multiline = $true
$note.AcceptsReturn = $true
$note.ScrollBars = 'Vertical'
$note.MaxLength = 4000
$note.SetBounds(16, 136, 488, 108)
$save = New-Object System.Windows.Forms.Button
$save.Text = 'Save for next capture'
$save.SetBounds(210, 262, 174, 32)
$save.DialogResult = [System.Windows.Forms.DialogResult]::OK
$cancel = New-Object System.Windows.Forms.Button
$cancel.Text = 'Cancel'
$cancel.SetBounds(394, 262, 110, 32)
$cancel.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
$form.Controls.AddRange(@($help, $titleLabel, $title, $noteLabel, $note, $save, $cancel))
$form.AcceptButton = $save
$form.CancelButton = $cancel
$form.Add_Shown({ $form.Activate(); $title.Focus(); $title.SelectAll() })
try {
    if ($form.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
        @{title = $title.Text; staff_note = $note.Text} | ConvertTo-Json -Compress
    }
} finally {
    $form.Dispose()
    [PanoptixFocus]::SetForegroundWindow($previousWindow) | Out-Null
}
"""


def show_capture_note(initial: dict) -> dict | None:
    if sys.platform != "win32":
        raise RuntimeError("The caption popup is available on Windows.")
    result = subprocess.run(
        ["powershell", "-NoProfile", "-STA", "-Command", PROMPT_SCRIPT],
        env={**os.environ, "PANOPTIX_CAPTURE_NOTE": json.dumps(initial)},
        capture_output=True, text=True, encoding="utf-8", timeout=600,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "The caption popup could not be opened")
    return json.loads(result.stdout) if result.stdout.strip() else None


class CaptureNotes:
    def __init__(self, prompt=None):
        self._lock = threading.RLock()
        self._pending = {}
        self._editing = False
        self._error = None
        self._thread = None
        self.prompt = prompt or show_capture_note

    def status(self) -> dict:
        with self._lock:
            return {"pending": dict(self._pending), "editing": self._editing, "error": self._error}

    def set(self, title: str = "", staff_note: str = "") -> dict:
        if not isinstance(title, str) or not isinstance(staff_note, str):
            raise ValueError("Caption and context note must be text")
        if len(title) > 200 or len(staff_note) > 4000:
            raise ValueError("Caption must be at most 200 characters; context note at most 4000")
        with self._lock:
            if self._editing:
                raise RuntimeError("Close the caption popup before changing its text")
            self._pending = {key: value.strip() for key, value in {"title": title, "staff_note": staff_note}.items() if value.strip()}
            self._error = None
            return self.status()

    def clear(self) -> None:
        with self._lock:
            self._pending = {}

    def open_prompt(self, clips=None) -> dict:
        # Match ClipRecorder.start's lock order so a clip cannot start while a
        # popup opens, or capture a popup that appears just after its first frame.
        with clips._lock if clips is not None else nullcontext():
            with self._lock:
                if self._editing:
                    return self.status()
                if clips is not None and clips.status()["active"]:
                    self._error = "Finish the current clip before captioning the next capture"
                    return self.status()
                self._editing = True
                self._error = None
                self._thread = threading.Thread(target=self._run_prompt, daemon=True)
                self._thread.start()
                return self.status()

    def _run_prompt(self):
        result = None
        error = None
        try:
            result = self.prompt(self.status()["pending"])
        except Exception as exc:
            error = str(exc)
        finally:
            # The window must be gone, and the confirmation click released,
            # before screenshot capture is allowed again.
            time.sleep(0.2)
            with self._lock:
                self._editing = False
                if result is not None:
                    try:
                        self.set(result.get("title", ""), result.get("staff_note", ""))
                    except Exception as exc:
                        error = str(exc)
                self._error = error
