from __future__ import annotations

from datetime import datetime, time
import threading
from typing import Any


def parse_hhmm(value: str, fallback: time) -> time:
    try:
        hour, minute = str(value).split(":", 1)
        return time(max(0, min(23, int(hour))), max(0, min(59, int(minute))))
    except (TypeError, ValueError):
        return fallback


def daily_window_is_active(settings: dict, now: datetime | None = None) -> bool:
    current = now or datetime.now()
    start = parse_hhmm(settings.get("background_start_time", "09:00"), time(9, 0))
    end = parse_hhmm(settings.get("background_end_time", "15:30"), time(15, 30))
    current_time = current.time()
    if start <= end:
        return start <= current_time <= end
    return current_time >= start or current_time <= end


class BackgroundScheduler:
    def __init__(self, recorder: Any, settings_store: Any, poll_seconds: int = 30):
        self.recorder = recorder
        self.settings_store = settings_store
        self.poll_seconds = poll_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

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
        settings = self.settings_store.load()
        should_run = bool(settings.get("background_enabled")) and daily_window_is_active(settings, now)
        is_running = self.recorder.active_mode == "background"
        if should_run and not is_running and self.recorder.active_mode is None:
            self.recorder.start(
                "background",
                {"activity": "Scheduled passive capture", "purpose": settings.get("default_evidence_purpose", "UAS evidence")},
                {
                    "interval_seconds": int(settings.get("background_interval_seconds", 5)),
                    "change_detection": bool(settings.get("background_change_detection", True)),
                    "change_threshold": int(settings.get("background_change_threshold", 4)),
                },
            )
        elif not should_run and is_running:
            self.recorder.stop()

    def _loop(self) -> None:
        while not self._stop_event.wait(self.poll_seconds):
            self.evaluate()
