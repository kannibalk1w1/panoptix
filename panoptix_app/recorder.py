from __future__ import annotations

import threading
from typing import Any

from .capture import ScreenCapture
from .models import now_iso
from .storage import SessionStore


class Recorder:
    def __init__(self, store: SessionStore, capture: Any | None = None):
        self.store = store
        self.capture = capture or ScreenCapture()
        self.active_session_id: str | None = None
        self.active_mode: str | None = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._observation_thread: threading.Thread | None = None

    def status(self) -> dict[str, Any]:
        return {
            "active": self.active_session_id is not None,
            "session_id": self.active_session_id,
            "mode": self.active_mode,
        }

    def start(
        self,
        mode: str,
        metadata: dict[str, Any] | None = None,
        settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if self.active_session_id is not None:
                raise RuntimeError("A recording is already active")
            session = self.store.create_session(mode, metadata or {}, settings or {})
            self.active_session_id = session["id"]
            self.active_mode = mode
            self._stop_event.clear()
            if mode == "observation":
                interval = float((settings or {}).get("interval_seconds", 60))
                self._observation_thread = threading.Thread(
                    target=self._observation_loop,
                    args=(max(interval, 0.01),),
                    daemon=True,
                )
                self._observation_thread.start()
            return session

    def stop(self) -> dict[str, Any] | None:
        self._stop_event.set()
        if self._observation_thread is not None:
            self._observation_thread.join(timeout=2)
            self._observation_thread = None
        with self._lock:
            if self.active_session_id is None:
                return None
            session = self.store.stop_session(self.active_session_id)
            self.active_session_id = None
            self.active_mode = None
            return session

    def capture_click(self, x: int, y: int) -> dict[str, Any]:
        with self._lock:
            self._require_active()
            if self.active_mode != "evidence":
                raise RuntimeError("Click capture is only available in evidence mode")
            session_id = self.active_session_id
            filename = self.store.next_screenshot_name(session_id)
            screenshot = self.capture.capture(self.store.screenshot_dir(session_id), filename, (x, y))
            event = {
                "type": "click",
                "timestamp": now_iso(),
                "screenshot": screenshot.name,
                "x": x,
                "y": y,
                "title": "",
                "staff_note": "",
                "cyp_quote": "",
                "tags": [],
            }
            return self.store.add_event(session_id, event)["events"][-1]

    def capture_periodic(self) -> dict[str, Any]:
        with self._lock:
            self._require_active()
            session_id = self.active_session_id
            filename = self.store.next_screenshot_name(session_id)
            screenshot = self.capture.capture(self.store.screenshot_dir(session_id), filename)
            event = {
                "type": "periodic",
                "timestamp": now_iso(),
                "screenshot": screenshot.name,
                "title": "",
                "staff_note": "",
                "highlight": False,
            }
            return self.store.add_event(session_id, event)["events"][-1]

    def _require_active(self) -> None:
        if self.active_session_id is None:
            raise RuntimeError("No active recording")

    def _observation_loop(self, interval: float) -> None:
        while not self._stop_event.wait(interval):
            try:
                self.capture_periodic()
            except RuntimeError:
                break
