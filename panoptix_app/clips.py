"""Timed screen clips, stored independently of evidence sessions."""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .capture import ScreenCapture
from .capture_notes import CaptureNotes


def export_gif(folder: Path, frames: list[dict], duration: float) -> None:
    # Write one indexed frame at a time: long/full-screen clips must not require
    # keeping every decoded PNG in memory. Each frame carries its own palette.
    from PIL import Image, GifImagePlugin

    temporary = folder / "clip.gif.tmp"
    try:
        with temporary.open("wb") as output:
            boundary = 0
            for index, frame in enumerate(frames):
                end = frames[index + 1]["seconds"] if index + 1 < len(frames) else duration
                next_boundary = max(boundary + 1, round(end * 100))
                with Image.open(folder / "frames" / frame["file"]) as source:
                    source.thumbnail((960, 960))
                    image = source.convert("RGB").quantize(colors=256)
                if index == 0:
                    header, _ = GifImagePlugin.getheader(image, info={"loop": 0})
                    for block in header:
                        output.write(block)
                for block in GifImagePlugin.getdata(
                    image, duration=(next_boundary - boundary) * 10,
                    include_color_table=True, disposal=2,
                ):
                    output.write(block)
                boundary = next_boundary
            output.write(b";")
        temporary.replace(folder / "clip.gif")
    finally:
        temporary.unlink(missing_ok=True)


class ClipRecorder:
    def __init__(self, root: Path, capture=None, notes: CaptureNotes | None = None):
        self.context_provider = lambda: {}
        self.session_active = lambda session_id: True
        self.notes = notes or CaptureNotes()
        self.root = Path(root)
        self.capture = capture or ScreenCapture()
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread = None
        self._status = {"active": False, "phase": "idle", "frame_count": 0, "folder": None, "error": None}

    def status(self) -> dict:
        with self._lock:
            return dict(self._status)

    def start(self, settings: dict) -> dict:
        context = self.context_provider()
        settings = {**settings, **context.get("clip_settings", {})}
        seconds = int(settings.get("clip_duration_seconds", 30))
        fps = int(settings.get("clip_fps", 5))
        if not 1 <= seconds <= 120 or not 1 <= fps <= 30:
            raise ValueError("Clip duration must be 1–120 seconds and frame rate 1–30 fps")
        with self._lock, self.notes._lock:
            if self.notes.status()["editing"]:
                raise RuntimeError("Close the caption popup before starting a clip")
            if self._status["active"]:
                raise RuntimeError("A clip is already recording or exporting")
            parent = self.root / "clips"
            if context.get("mode") == "lms":
                parent /= context["session_id"]
            folder = parent / (datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid4().hex[:8])
            (folder / "frames").mkdir(parents=True)
            self._stop = threading.Event()
            self._status = {"active": True, "phase": "recording", "frame_count": 0,
                            "folder": str(folder), "error": None, "duration_seconds": seconds, "fps": fps, "session_id": context.get("session_id")}
            self._thread = threading.Thread(target=self._run, args=(folder, seconds, fps, bool(settings.get("clip_make_gif", True)), self.notes.status()["pending"], context), daemon=True)
            self._thread.start()
            self.notes.clear()
            return dict(self._status)

    def stop(self) -> dict:
        self._stop.set()
        return self.status()

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join()

    def _update(self, **changes):
        with self._lock:
            self._status.update(changes)

    def _run(self, folder: Path, seconds: int, fps: int, make_gif: bool, caption: dict, context: dict):
        frames = []
        start = time.monotonic()
        error = None
        try:
            slot = 0
            while not self._stop.is_set():
                if context.get("mode") == "lms" and not self.session_active(context["session_id"]):
                    break
                elapsed = time.monotonic() - start
                if elapsed >= seconds:
                    break
                filename = f"frame_{len(frames):06d}.png"
                self.capture.capture(folder / "frames", filename)
                frames.append({"file": filename, "seconds": elapsed})
                self._update(frame_count=len(frames))
                # Skip missed deadlines if PNG writing is slower than requested.
                slot = max(slot + 1, int((time.monotonic() - start) * fps) + 1)
                if self._stop.wait(max(0, min(seconds, slot / fps) - (time.monotonic() - start))):
                    break
        except Exception as exc:
            error = f"Clip capture failed: {exc}"
        duration = min(seconds, time.monotonic() - start)
        try:
            manifest = {**context, **caption, "requested_fps": fps, "requested_duration_seconds": seconds,
                        "duration_seconds": duration, "frames": frames, "capture_error": error}
            if not frames and caption:
                # No item was collected; retain its caption unless another one
                # has already been armed by the user.
                with self.notes._lock:
                    if not self.notes.status()["pending"]:
                        self.notes.set(**caption)
            (folder / "clip.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            if make_gif and frames:
                self._update(phase="exporting")
                export_gif(folder, frames, duration)
        except Exception as exc:
            error = f"{error + '; ' if error else ''}Clip export failed; PNG frames are kept: {exc}"
        finally:
            self._update(active=False, phase="finished", error=error)
