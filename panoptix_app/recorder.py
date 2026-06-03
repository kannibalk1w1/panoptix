from __future__ import annotations

import threading
from datetime import datetime
from typing import Any

from .annotation import DEFAULT_MARKER, annotate_click, normalize_marker
from .capture import ScreenCapture
from .frame_diff import images_are_different
from .hooks import GlobalMouseHook
from .models import now_iso
from .storage import SessionStore


class Recorder:
    def __init__(self, store: SessionStore, capture: Any | None = None, hook_factory: Any | None = None):
        self.store = store
        self.capture = capture or ScreenCapture()
        self.hook_factory = hook_factory or GlobalMouseHook
        self.active_session_id: str | None = None
        self.active_mode: str | None = None
        self.started_at: datetime | None = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._observation_thread: threading.Thread | None = None
        self._click_threads: list[threading.Thread] = []
        self._mouse_hook: Any | None = None
        self._last_saved_screenshot: str | None = None
        self._skipped_unchanged = 0
        self.hook_error: str | None = None

    def status(self) -> dict[str, Any]:
        event_count = 0
        elapsed_seconds = 0
        if self.active_session_id is not None:
            try:
                event_count = len(self.store.load_session(self.active_session_id).get("events", []))
            except FileNotFoundError:
                event_count = 0
        if self.started_at is not None:
            elapsed_seconds = int((datetime.now() - self.started_at).total_seconds())
        return {
            "active": self.active_session_id is not None,
            "session_id": self.active_session_id,
            "mode": self.active_mode,
            "hook_error": self.hook_error,
            "elapsed_seconds": elapsed_seconds,
            "event_count": event_count,
            "paused": self._pause_event.is_set(),
            "skipped_unchanged": self._skipped_unchanged,
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
            self.started_at = datetime.now()
            self.hook_error = None
            self._last_saved_screenshot = None
            self._skipped_unchanged = 0
            self._stop_event.clear()
            self._pause_event.clear()
            if mode in {"observation", "background"}:
                interval = float((settings or {}).get("interval_seconds", 60))
                self._observation_thread = threading.Thread(
                    target=self._observation_loop,
                    args=(max(interval, 0.01),),
                    daemon=True,
                )
                self._observation_thread.start()
            if mode == "evidence":
                self._mouse_hook = self.hook_factory(self._queue_click_capture)
                try:
                    self._mouse_hook.start()
                except RuntimeError as exc:
                    self.hook_error = str(exc)
                    self._mouse_hook = None
            return session

    def stop(self) -> dict[str, Any] | None:
        self._stop_event.set()
        if self._observation_thread is not None:
            self._observation_thread.join(timeout=2)
            self._observation_thread = None
        if self._mouse_hook is not None:
            self._mouse_hook.stop()
            self._mouse_hook = None
        for thread in self._pending_click_threads():
            thread.join(timeout=2)
        with self._lock:
            if self.active_session_id is None:
                return None
            session = self.store.stop_session(self.active_session_id)
            self.active_session_id = None
            self.active_mode = None
            self.started_at = None
            self._pause_event.clear()
            self._last_saved_screenshot = None
            return session

    def _pending_click_threads(self) -> list[threading.Thread]:
        with self._lock:
            return list(self._click_threads)

    def pause(self) -> None:
        with self._lock:
            if self.active_session_id is not None:
                self._pause_event.set()

    def resume(self) -> None:
        with self._lock:
            self._pause_event.clear()

    def capture_click(self, x: int, y: int) -> dict[str, Any]:
        with self._lock:
            self._require_active()
            if self.active_mode != "evidence":
                raise RuntimeError("Click capture is only available in evidence mode")
            session_id = self.active_session_id
            filename = self.store.next_screenshot_name(session_id)
            screenshot_dir = self.store.screenshot_dir(session_id)
            original_dir = screenshot_dir / "originals"
            marker = normalize_marker(self.store.load_session(session_id).get("settings", {}).get("marker", DEFAULT_MARKER))
            original = self.capture.capture(original_dir, filename)
            screenshot = annotate_click(original, screenshot_dir / filename, x, y, marker)
            event = {
                "type": "click",
                "timestamp": now_iso(),
                "screenshot": screenshot.name,
                "original_screenshot": f"originals/{original.name}",
                "x": x,
                "y": y,
                "marker": marker,
                "title": "",
                "staff_note": "",
                "cyp_quote": "",
                "tags": [],
            }
            return self.store.add_event(session_id, event)["events"][-1]

    def _queue_click_capture(self, x: int, y: int) -> None:
        with self._lock:
            if self.active_session_id is None:
                return
            thread = threading.Thread(target=self._capture_queued_click, args=(x, y), daemon=True)
            self._click_threads.append(thread)
        thread.start()

    def _capture_queued_click(self, x: int, y: int) -> None:
        thread = threading.current_thread()
        try:
            self.capture_click(x, y)
        except RuntimeError:
            pass
        finally:
            with self._lock:
                if thread in self._click_threads:
                    self._click_threads.remove(thread)

    def capture_periodic(self) -> dict[str, Any]:
        with self._lock:
            return self._capture_periodic_locked()

    def capture_manual_hotkey(self) -> dict[str, Any]:
        with self._lock:
            self._require_active()
            session_id = self.active_session_id
            filename = self.store.next_screenshot_name(session_id)
            screenshot = self.capture.capture(self.store.screenshot_dir(session_id), filename)
            event = {
                "type": "manual_hotkey",
                "timestamp": now_iso(),
                "screenshot": screenshot.name,
                "title": "Manual CYP capture",
                "staff_note": "",
                "highlight": True,
            }
            saved = self.store.add_event(session_id, event)["events"][-1]
            self._last_saved_screenshot = screenshot.name
            return saved

    def _capture_periodic_locked(self) -> dict[str, Any]:
        self._require_active()
        session_id = self.active_session_id
        filename = self.store.next_screenshot_name(session_id)
        screenshot_dir = self.store.screenshot_dir(session_id)
        screenshot = self.capture.capture(screenshot_dir, filename)
        session = self.store.load_session(session_id)
        settings = session.get("settings", {})
        if self._should_skip_unchanged(screenshot_dir, screenshot, settings):
            screenshot.unlink(missing_ok=True)
            self._skipped_unchanged += 1
            return None
        event_type = "background" if self.active_mode == "background" else "periodic"
        event = {
            "type": event_type,
            "timestamp": now_iso(),
            "screenshot": screenshot.name,
            "title": "",
            "staff_note": "",
            "highlight": False,
        }
        saved = self.store.add_event(session_id, event)["events"][-1]
        self._last_saved_screenshot = screenshot.name
        return saved

    def _should_skip_unchanged(self, screenshot_dir, screenshot, settings: dict[str, Any]) -> bool:
        if not settings.get("change_detection"):
            return False
        if self._last_saved_screenshot is None:
            return False
        previous = screenshot_dir / self._last_saved_screenshot
        if not previous.exists():
            return False
        threshold = float(settings.get("change_threshold", 4))
        return not images_are_different(previous, screenshot, threshold)

    def _require_active(self) -> None:
        if self.active_session_id is None:
            raise RuntimeError("No active recording")

    def _observation_loop(self, interval: float) -> None:
        while not self._stop_event.wait(interval):
            with self._lock:
                if self._pause_event.is_set():
                    continue
                try:
                    self._capture_periodic_locked()
                except RuntimeError:
                    break
