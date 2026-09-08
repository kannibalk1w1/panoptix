from __future__ import annotations

import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote, urlparse

from .annotation import update_event_marker
from .app_config import set_configured_data_directory
from .app_paths import (
    directory_problem,
    get_project_root,
    normalize_directory,
    resolve_data_root,
)
from .background import BackgroundScheduler, daily_window_is_active
from .schedule import timetable_for_editor
from .folder_picker import pick_folder
from .exporter import (
    EvidencePackExporter,
    EvidencePackVerifier,
    ImageZipExporter,
    SessionExporter,
    export_destination_status,
)
from .hotkeys import HotkeyService
from .redaction import redact_event_screenshot, restore_original_screenshot
from .recorder import Recorder
from .retention import cleanup_old_sessions, preview_cleanup
from .open_folder import open_folder
from .settings import SettingsStore
from .startup import StartupManager
from .storage import SessionStore
from .storage_usage import get_storage_usage
from .tray import start_tray


class DataContext:
    """Holds everything bound to the data folder so it can be swapped without
    restarting Panoptix."""

    def __init__(self, root: Path, store: SessionStore, recorder: Recorder, settings_store: SettingsStore | None = None):
        self.root = Path(root)
        self.store = store
        self.recorder = recorder
        self.settings_store = settings_store or SettingsStore(self.root)

    def switch_root(self, new_root: Path) -> bool:
        with self.recorder._lock:
            if self.recorder.active_session_id is not None:
                raise ValueError("Stop the current recording before changing the screenshot folder.")
            return self._switch_root(new_root)

    def _switch_root(self, new_root: Path) -> bool:
        new_root = Path(new_root)
        if new_root == self.root:
            return False
        # Carry the current settings across so switching folders does not silently
        # reset the capture schedule, hotkey and marker preferences.
        settings = self.settings_store.load()
        new_store = SessionStore(new_root)
        new_settings = SettingsStore(new_root)
        if not new_settings.path.exists():
            new_settings.update(settings)
        self.root = new_root
        self.store = new_store
        self.recorder.store = new_store
        self.settings_store.set_root(new_root)
        return True


def create_handler(
    root: Path,
    store: SessionStore,
    recorder: Recorder,
    hotkeys: HotkeyService | None = None,
    startup: StartupManager | None = None,
    settings_store: SettingsStore | None = None,
    scheduler: BackgroundScheduler | None = None,
):
    frontend_dir = get_project_root() / "frontend"
    context = DataContext(root, store, recorder, settings_store)

    def data_location_status() -> dict[str, Any]:
        status = resolve_data_root()
        status["active_path"] = str(context.root)
        status["restart_required"] = Path(status["path"]) != context.root
        return status

    def app_status() -> dict[str, Any]:
        storage_error = None
        try:
            settings = context.settings_store.load()
        except (OSError, ValueError) as exc:
            settings = context.settings_store.last_good
            storage_error = str(exc)
        status = recorder.status()
        status["storage_error"] = storage_error
        status["background"] = {
            "enabled": bool(settings.get("background_enabled")),
            "window": "Weekly timetable" if settings.get("background_weekly_schedule") is not None else f"{settings.get('background_start_time')}-{settings.get('background_end_time')}",
            "start_time": settings.get("background_start_time"),
            "end_time": settings.get("background_end_time"),
            "interval_seconds": settings.get("background_interval_seconds"),
            "change_detection": bool(settings.get("background_change_detection")),
            "change_threshold": settings.get("background_change_threshold"),
            "window_active": daily_window_is_active(settings),
            "error": scheduler.error if scheduler else None,
        }
        status["hotkey"] = {
            "enabled": bool(settings.get("manual_hotkey_enabled")),
            "shortcut": settings.get("manual_hotkey"),
            "error": getattr(hotkeys, "error", None) if hotkeys is not None else None,
        }
        status["startup"] = {
            "requested": bool(settings.get("launch_on_startup")),
            "installed": startup.is_enabled() if startup is not None else False,
        }
        try:
            status["export_destination"] = export_destination_status(context.root)
        except (OSError, ValueError) as exc:
            status["export_destination"] = {"warning": str(exc), "writable": False}
        try:
            status["data_location"] = data_location_status()
        except (OSError, ValueError) as exc:
            status["data_location"] = {"active_path": str(context.root), "warning": str(exc)}
        return status

    class PanoptixHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = urlparse(self.path).path
            try:
                if path == "/api/status":
                    self._json(app_status())
                elif path == "/api/settings":
                    settings = context.settings_store.load()
                    self._json({"settings": settings, "timetable": timetable_for_editor(settings)})
                elif path == "/api/data-location":
                    self._json({"data_location": data_location_status()})
                elif path == "/api/storage":
                    settings = context.settings_store.load()
                    self._json({"storage": get_storage_usage(context.root, settings["storage_warning_mb"])})
                elif path == "/api/sessions":
                    self._json({"sessions": context.store.list_sessions()})
                elif path == "/api/trash":
                    self._json({"sessions": context.store.list_trash()})
                elif path == "/api/retention/preview":
                    with recorder._lock:
                        self._json(preview_cleanup(context.store, context.settings_store.load()["retention_days"], protected_session_id=recorder.active_session_id))
                elif path.startswith("/api/sessions/") and "/screenshots/" in path:
                    self._screenshot(path)
                elif path.startswith("/api/sessions/"):
                    session_id = unquote(path.removeprefix("/api/sessions/"))
                    self._json({"session": context.store.load_session(session_id)})
                else:
                    self._static(path)
            except Exception as exc:
                self._error(exc)

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            try:
                payload = self._payload()
                if path == "/api/record/start":
                    session = recorder.start(
                        payload.get("mode", "evidence"),
                        payload.get("metadata", {}),
                        payload.get("settings", {}),
                    )
                    self._json({"session": session})
                elif path == "/api/record/stop":
                    self._json({"session": recorder.stop()})
                elif path == "/api/record/pause":
                    recorder.pause()
                    self._json(recorder.status())
                elif path == "/api/record/resume":
                    recorder.resume()
                    self._json(recorder.status())
                elif path == "/api/capture/click":
                    event = recorder.capture_click(int(payload["x"]), int(payload["y"]))
                    self._json({"event": event})
                elif path == "/api/capture/periodic":
                    self._json({"event": recorder.capture_periodic()})
                elif path.startswith("/api/sessions/") and path.endswith("/export"):
                    session_id = unquote(path.split("/")[-2])
                    output = SessionExporter(context.root).export(session_id)
                    self._json({"html": str(output["html"]), "pdf": str(output["pdf"])})
                elif path.startswith("/api/sessions/") and path.endswith("/export-images"):
                    session_id = unquote(path.split("/")[-2])
                    output = ImageZipExporter(context.root).export(session_id, variant=payload.get("variant", "annotated"))
                    self._json({"zip": str(output)})
                elif path.startswith("/api/sessions/") and path.endswith("/export-pack"):
                    session_id = unquote(path.split("/")[-2])
                    output = EvidencePackExporter(context.root).export(session_id, include_originals=payload.get("include_originals") is True)
                    self._json({"zip": str(output)})
                elif path.startswith("/api/sessions/") and path.endswith("/verify-pack"):
                    session_id = unquote(path.split("/")[-2])
                    self._json(EvidencePackVerifier(context.root).verify(session_id))
                elif path.startswith("/api/sessions/") and path.endswith("/redact"):
                    parts = path.split("/")
                    session_id = unquote(parts[3])
                    event_index = int(parts[5])
                    result = redact_event_screenshot(
                        context.store,
                        session_id,
                        event_index,
                        rect=payload.get("rect"),
                        preset=payload.get("preset"),
                        expected_screenshot=payload.get("expected_screenshot"),
                    )
                    self._json(result)
                elif path.startswith("/api/sessions/") and path.endswith("/marker"):
                    parts = path.split("/")
                    session_id = unquote(parts[3])
                    event_index = int(parts[5])
                    self._json(update_event_marker(context.store, session_id, event_index, payload))
                elif path.startswith("/api/sessions/") and path.endswith("/restore-original"):
                    parts = path.split("/")
                    session_id = unquote(parts[3])
                    event_index = int(parts[5])
                    self._json(restore_original_screenshot(context.store, session_id, event_index))
                elif path == "/api/browse-folder":
                    self._json({"result": pick_folder(str(payload.get("initial", "")))})
                elif path == "/api/exports/open-folder":
                    session_id = payload.get("session_id")
                    if session_id:
                        context.store.load_session(session_id)
                    destination = export_destination_status(context.root, session_id)
                    open_folder(Path(destination["path"]))
                    self._json({"path": destination["path"]})
                elif path.startswith("/api/trash/") and path.endswith("/restore"):
                    self._json({"session": context.store.restore_session(unquote(path.split("/")[3]))})
                elif path == "/api/retention/cleanup":
                    settings = context.settings_store.load()
                    with recorder._lock:
                        ids = payload.get("session_ids")
                        if ids is not None and (not isinstance(ids, list) or not all(isinstance(item, str) for item in ids)):
                            raise ValueError("Expected a list of session ids")
                        self._json(cleanup_old_sessions(context.store, settings["retention_days"], protected_session_id=recorder.active_session_id, session_ids=ids))
                else:
                    self.send_error(404)
            except Exception as exc:
                self._error(exc)

        def do_PATCH(self) -> None:
            path = urlparse(self.path).path
            try:
                if path == "/api/settings":
                    updated_settings = context.settings_store.update(self._payload())
                    if startup is not None:
                        startup.set_enabled(bool(updated_settings.get("launch_on_startup")))
                    if hotkeys is not None:
                        hotkeys.restart()
                    self._json({"settings": updated_settings})
                elif path == "/api/data-location":
                    directory = str(self._payload().get("directory", "")).strip()
                    if directory:
                        problem = directory_problem(normalize_directory(directory))
                        if problem:
                            raise ValueError(f"That folder cannot be used: {problem}")
                    with recorder._lock:
                        if recorder.active_session_id is not None:
                            raise ValueError("Stop the current recording before changing the screenshot folder.")
                        set_configured_data_directory(directory)
                        context.switch_root(Path(resolve_data_root()["path"]))
                    if hotkeys is not None:
                        hotkeys.restart()
                    if startup is not None:
                        startup.set_enabled(bool(context.settings_store.load().get("launch_on_startup")))
                    self._json({"data_location": data_location_status()})
                elif path.startswith("/api/sessions/") and "/events/" in path:
                    parts = path.split("/")
                    session_id = unquote(parts[3])
                    event_index = int(parts[5])
                    session = context.store.update_event(session_id, event_index, self._payload())
                    event = next(item for item in session["events"] if item.get("index") == event_index)
                    self._json({"session": session, "event": event})
                elif path.startswith("/api/sessions/"):
                    session_id = unquote(path.removeprefix("/api/sessions/"))
                    self._json({"session": context.store.update_session(session_id, self._payload())})
                else:
                    self.send_error(404)
            except Exception as exc:
                self._error(exc)

        def do_DELETE(self) -> None:
            path = urlparse(self.path).path
            try:
                if path.startswith("/api/sessions/") and "/events/" in path:
                    parts = path.split("/")
                    session_id = unquote(parts[3])
                    event_index = int(parts[5])
                    self._json({"session": context.store.delete_event(session_id, event_index)})
                elif path.startswith("/api/sessions/"):
                    session_id = unquote(path.removeprefix("/api/sessions/"))
                    recorder.delete_session(session_id)
                    self._json({"ok": True})
                else:
                    self.send_error(404)
            except Exception as exc:
                self._error(exc)

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _payload(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length == 0:
                return {}
            raw = self.rfile.read(length).decode("utf-8")
            if not raw.strip():
                return {}
            return json.loads(raw)

        def _json(self, payload: dict[str, Any], status: int = 200) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _error(self, exc: Exception) -> None:
            self._json({"error": str(exc)}, status=400)

        def _static(self, path: str) -> None:
            relative = "index.html" if path in ("", "/") else path.lstrip("/")
            target = (frontend_dir / relative).resolve()
            if not target.is_relative_to(frontend_dir.resolve()) or not target.is_file():
                self.send_error(404)
                return
            body = target.read_bytes()
            mime = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _screenshot(self, path: str) -> None:
            parts = path.split("/")
            session_id = unquote(parts[3])
            filename = unquote(parts[5])
            if "/" in filename or "\\" in filename or not filename.endswith(".png"):
                self.send_error(404)
                return
            with context.store.transaction():
                context.store.load_session(session_id)
                target = context.store.screenshot_dir(session_id) / filename
                if not target.exists():
                    self.send_error(404)
                    return
                body = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return PanoptixHandler


def run_server(root: Path, host: str = "127.0.0.1", port: int = 8765, on_ready: Callable | None = None) -> ThreadingHTTPServer:
    root = Path(root)
    store = SessionStore(root)
    recorder = Recorder(store)
    settings_store = SettingsStore(root)
    scheduler = BackgroundScheduler(recorder, settings_store)
    hotkeys = HotkeyService(settings_store, recorder)
    startup = StartupManager()
    # The scheduler and hotkey service share this settings store, so they follow
    # the handler when the screenshot folder is changed at runtime.
    handler = create_handler(root, store, recorder, hotkeys, startup, settings_store, scheduler)
    server = ThreadingHTTPServer((host, port), handler)
    tray_icon = None
    try:
        scheduler.start()
        hotkeys.start()
        startup.set_enabled(bool(settings_store.load().get("launch_on_startup")))
        tray_icon = start_tray(f"http://{host}:{server.server_address[1]}", recorder, settings_store, server)
        print(f"Panoptix running at http://{host}:{server.server_address[1]}")
        if on_ready:
            on_ready()
        server.serve_forever()
    finally:
        if tray_icon is not None:
            tray_icon.stop()
        hotkeys.stop()
        scheduler.stop()
        recorder.stop()
        server.server_close()
    return server
