from __future__ import annotations

import threading
import math
from functools import wraps
from datetime import datetime
from typing import Any

from .annotation import DEFAULT_MARKER, annotate_click, normalize_marker
from .capture import ScreenCapture, to_image_coordinates
from .frame_diff import images_are_different
from .hooks import GlobalMouseHook
from .models import now_iso
from .storage import SessionStore


class CaptureStateError(RuntimeError):
    pass


def lifecycle_operation(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self._lifecycle_lock:
            return method(self, *args, **kwargs)
    return wrapped


def capture_operation(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self._lock:
            self._require_active()
            try:
                with self.store.transaction():
                    return method(self, *args, **kwargs)
            except CaptureStateError:
                raise
            except Exception as exc:
                self._fail_capture_locked(exc)
                raise
    return wrapped


class Recorder:
    def __init__(self, store: SessionStore, capture: Any | None = None, hook_factory: Any | None = None):
        self.store = store
        self.capture = capture or ScreenCapture()
        self.hook_factory = hook_factory or GlobalMouseHook
        self.active_session_id: str | None = None
        self.active_mode: str | None = None
        self.started_at: datetime | None = None
        self._lock = threading.RLock()
        self._lifecycle_lock = threading.RLock()
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._observation_thread: threading.Thread | None = None
        self._click_threads: list[threading.Thread] = []
        self._mouse_hook: Any | None = None
        self._last_saved_screenshot: str | None = None
        self._skipped_unchanged = 0
        self.hook_error: str | None = None
        self.capture_error: str | None = None

    def status(self) -> dict[str, Any]:
        with self._lock:
            return self._status_locked()

    def _status_locked(self) -> dict[str, Any]:
        event_count = 0
        elapsed_seconds = 0
        if self.active_session_id is not None:
            try:
                event_count = len(self.store.load_session(self.active_session_id).get("events", []))
            except (OSError, ValueError) as exc:
                self._fail_capture_locked(exc)
                event_count = 0
        if self.started_at is not None:
            elapsed_seconds = int((datetime.now() - self.started_at).total_seconds())
        return {
            "active": self.active_session_id is not None,
            "session_id": self.active_session_id,
            "mode": self.active_mode,
            "hook_error": self.hook_error,
            "capture_error": self.capture_error,
            "elapsed_seconds": elapsed_seconds,
            "event_count": event_count,
            "paused": self._pause_event.is_set(),
            "skipped_unchanged": self._skipped_unchanged,
        }

    @lifecycle_operation
    def start(
        self,
        mode: str,
        metadata: dict[str, Any] | None = None,
        settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if self.active_session_id is not None:
                raise RuntimeError("A recording is already active")
            interval = float((settings or {}).get("interval_seconds", 60))
            if not math.isfinite(interval) or interval <= 0:
                raise ValueError("Screenshot interval must be a positive finite number")
            self._stop_hook()
            session = self.store.create_session(mode, metadata or {}, settings or {})
            self.active_session_id = session["id"]
            self.active_mode = mode
            self.started_at = datetime.now()
            self.hook_error = None
            self.capture_error = None
            self._last_saved_screenshot = None
            self._skipped_unchanged = 0
            self._stop_event = threading.Event()
            self._pause_event.clear()
            if mode in {"observation", "background"}:
                self._observation_thread = threading.Thread(
                    target=self._observation_loop,
                    args=(max(interval, 0.01), self._stop_event, session["id"]),
                    daemon=True,
                )
                self._observation_thread.start()
            if mode == "evidence":
                self._mouse_hook = self.hook_factory(lambda x, y: self._queue_click_capture(x, y, session["id"]))
                try:
                    self._mouse_hook.start()
                except Exception as exc:
                    self.hook_error = str(exc)
                    self._mouse_hook = None
            return session

    @lifecycle_operation
    def stop(self, expected_session_id: str | None = None) -> dict[str, Any] | None:
        with self._lock:
            if expected_session_id is not None and self.active_session_id != expected_session_id:
                return None
        self._stop_event.set()
        if self._observation_thread is not None:
            self._observation_thread.join(timeout=2)
            self._observation_thread = None
        self._stop_hook()
        for thread in self._pending_click_threads():
            thread.join(timeout=2)
        with self._lock:
            if self.active_session_id is None:
                return None
            try:
                session = self.store.stop_session(self.active_session_id)
            except Exception as exc:
                self.capture_error = f"Recording stopped, but session could not be finalized: {exc}"
                session = None
            finally:
                self._clear_active()
            return session

    def _stop_hook(self) -> None:
        hook, self._mouse_hook = self._mouse_hook, None
        if hook is not None:
            try:
                hook.stop()
            except Exception as exc:
                self.hook_error = str(exc)

    def _clear_active(self) -> None:
        self.active_session_id = None
        self.active_mode = None
        self.started_at = None
        self._pause_event.clear()
        self._last_saved_screenshot = None

    def _fail_capture_locked(self, exc: Exception) -> None:
        self.capture_error = f"Capture stopped: {exc}"
        self._stop_event.set()
        try:
            if self.active_session_id is not None:
                self.store.stop_session(self.active_session_id)
        except Exception:
            pass  # Keep the original capture error visible even if storage is offline.
        self._clear_active()
        self._stop_hook()

    def delete_session(self, session_id: str) -> None:
        with self._lock:
            if session_id == self.active_session_id:
                raise ValueError("Stop the recording before deleting this session")
            self.store.delete_session(session_id)

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

    @capture_operation
    def capture_click(self, x: int, y: int) -> dict[str, Any]:
        with self._lock:
            self._require_active()
            if self.active_mode != "evidence":
                raise CaptureStateError("Click capture is only available in evidence mode")
            session_id = self.active_session_id
            filename = self.store.next_screenshot_name(session_id)
            screenshot_dir = self.store.screenshot_dir(session_id)
            original_dir = screenshot_dir / "originals"
            marker = normalize_marker(self.store.load_session(session_id).get("settings", {}).get("marker", DEFAULT_MARKER))
            original = self.capture.capture(original_dir, filename)
            # The capture spans every monitor, so the click has to be moved out of
            # virtual-desktop space and into pixels on the saved image.
            origin = getattr(self.capture, "last_origin", (0, 0))
            image_x, image_y = to_image_coordinates(x, y, origin)
            screenshot = annotate_click(original, screenshot_dir / filename, image_x, image_y, marker)
            event = {
                "type": "click",
                "timestamp": now_iso(),
                "screenshot": screenshot.name,
                "original_screenshot": f"originals/{original.name}",
                "x": image_x,
                "y": image_y,
                "screen_x": x,
                "screen_y": y,
                "marker": marker,
                "title": "",
                "staff_note": "",
                "cyp_quote": "",
                "tags": [],
            }
            return self.store.add_event(session_id, event)["events"][-1]

    def _queue_click_capture(self, x: int, y: int, session_id: str | None = None) -> None:
        with self._lock:
            if self.active_session_id is None or self._stop_event.is_set() or self._pause_event.is_set():
                return
            if session_id is not None and session_id != self.active_session_id:
                return
            thread = threading.Thread(target=self._capture_queued_click, args=(x, y, self.active_session_id), daemon=True)
            self._click_threads.append(thread)
            thread.start()

    def _capture_queued_click(self, x: int, y: int, session_id: str) -> None:
        thread = threading.current_thread()
        try:
            with self._lock:
                if session_id != self.active_session_id:
                    return
                self.capture_click(x, y)
        except Exception:
            pass
        finally:
            with self._lock:
                if thread in self._click_threads:
                    self._click_threads.remove(thread)

    @capture_operation
    def capture_periodic(self) -> dict[str, Any] | None:
        with self._lock:
            return self._capture_periodic_locked()

    @capture_operation
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
            raise CaptureStateError("No active recording")
        if self._pause_event.is_set():
            raise CaptureStateError("Recording is paused")

    def _observation_loop(self, interval: float, stop_event=None, session_id=None) -> None:
        stop_event = stop_event or self._stop_event
        session_id = session_id or self.active_session_id
        while not stop_event.wait(interval):
            with self._lock:
                if session_id != self.active_session_id or stop_event.is_set():
                    break
                if self._pause_event.is_set():
                    continue
                try:
                    self.capture_periodic()
                except Exception as exc:
                    if self.active_session_id is not None:
                        self._fail_capture_locked(exc)
                    break
