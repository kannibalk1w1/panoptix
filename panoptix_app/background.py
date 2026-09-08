from __future__ import annotations

from datetime import datetime
import logging
import threading
from typing import Any
from .schedule import active_schedule_window, daily_window_is_active, parse_hhmm


class BackgroundScheduler:
    def __init__(self, recorder: Any, settings_store: Any, poll_seconds: int = 30):
        self.recorder = recorder
        self.settings_store = settings_store
        self.poll_seconds = poll_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._owned_session_id: str | None = None
        self._owned_window: str | None = None
        self._suppressed_window: str | None = None
        self.error: str | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def evaluate(self, now: datetime | None = None) -> None:
        now = now or datetime.now()
        settings = self.settings_store.load()
        window = active_schedule_window(settings, now)
        should_run = bool(settings.get("background_enabled")) and window is not None
        # Only stop sessions started by this scheduler. A manual stop suppresses
        # this window, including overnight windows, without disabling tomorrow.
        if self._owned_session_id and self.recorder.active_session_id != self._owned_session_id:
            self._suppressed_window = self._owned_window
            self._owned_session_id = None
        # A missed poll/sleep may cross a gap without observing an inactive slot.
        if self._owned_session_id and self._owned_window != window:
            self.recorder.stop(expected_session_id=self._owned_session_id)
            self._owned_session_id = None
        if not should_run:
            self._suppressed_window = None
            if self._owned_session_id:
                self.recorder.stop(expected_session_id=self._owned_session_id)
                self._owned_session_id = None
        elif self.recorder.active_mode is None and self._suppressed_window != window:
            session = self.recorder.start(
                "background",
                {"activity": "Scheduled passive capture", "purpose": settings.get("default_evidence_purpose", "UAS evidence")},
                {
                    "interval_seconds": int(settings.get("background_interval_seconds", 5)),
                    "change_detection": bool(settings.get("background_change_detection", True)),
                    "change_threshold": int(settings.get("background_change_threshold", 4)),
                },
            )
            self._owned_session_id = session["id"]
            self._owned_window = window
        self.error = None

    def _loop(self) -> None:
        while not self._stop_event.wait(self.poll_seconds):
            try:
                self.evaluate()
            except Exception as exc:
                self.error = str(exc)
                logging.exception("Background scheduler could not evaluate the capture window")
