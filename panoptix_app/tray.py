from __future__ import annotations

import webbrowser
import logging
import sys
import threading
from typing import Any

from .linux_tray import start_linux_tray


_shutdown_lock = threading.Lock()


def request_shutdown(server: Any) -> None:
    # HTTPServer.shutdown must run outside the server's serving thread. Tray
    # callbacks must also return promptly so the native event loop can clean up.
    with _shutdown_lock:
        if getattr(server, "_panoptix_quitting", False):
            return
        server._panoptix_quitting = True
        threading.Thread(target=server.shutdown, name="panoptix-shutdown", daemon=True).start()


def stop_tray(icon: Any, timeout: float = 2) -> None:
    if icon is None:
        return
    def cleanup():
        try:
            icon.visible = False
        except Exception:
            logging.exception("Could not hide the tray icon")
        finally:
            try:
                icon.stop()
            except Exception:
                logging.exception("Could not stop the tray event loop")
    worker = threading.Thread(target=cleanup, name="panoptix-tray-stop", daemon=True)
    worker.start()
    worker.join(timeout=timeout)
    if worker.is_alive():
        logging.warning("Tray cleanup did not respond; continuing application shutdown")


def start_tray(url: str, recorder: Any, settings_store: Any, server: Any):
    if sys.platform.startswith("linux"):
        return start_linux_tray(url)
    try:
        import pystray
        from PIL import Image, ImageDraw
    except (ImportError, OSError):
        return None

    def open_dashboard(icon=None, item=None) -> None:
        webbrowser.open(url)

    def start_background_now(icon=None, item=None) -> None:
        if recorder.active_mode is not None:
            return
        settings = settings_store.load()
        recorder.start(
            "background",
            {"activity": "Manual passive capture", "purpose": settings.get("default_evidence_purpose", "UAS evidence")},
            {
                "interval_seconds": int(settings.get("background_interval_seconds", 5)),
                "change_detection": bool(settings.get("background_change_detection", True)),
                "change_threshold": int(settings.get("background_change_threshold", 4)),
            },
        )

    def pause(icon=None, item=None) -> None:
        recorder.pause()

    def resume(icon=None, item=None) -> None:
        recorder.resume()

    def manual_capture(icon=None, item=None) -> None:
        try:
            recorder.capture_manual_hotkey()
        except Exception:
            pass  # Recorder exposes capture failures in dashboard status.

    def stop_capture(icon=None, item=None) -> None:
        recorder.stop()

    def quit_panoptix(icon, item=None) -> None:
        request_shutdown(server)

    image = Image.new("RGB", (64, 64), "#101318")
    draw = ImageDraw.Draw(image)
    draw.ellipse((14, 14, 50, 50), outline="#4ade80", width=5)
    draw.ellipse((28, 28, 36, 36), fill="#4ade80")

    icon = pystray.Icon(
        "Panoptix",
        image,
        "Panoptix",
        menu=pystray.Menu(
            pystray.MenuItem("Open dashboard", open_dashboard, default=True),
            pystray.MenuItem("Start passive capture now", start_background_now),
            pystray.MenuItem("Pause capture", pause),
            pystray.MenuItem("Resume capture", resume),
            pystray.MenuItem("Manual screenshot", manual_capture),
            pystray.MenuItem("Stop capture", stop_capture),
            pystray.MenuItem("Quit Panoptix", quit_panoptix),
        ),
    )
    try:
        if sys.platform == "darwin":
            icon.run_detached()
        else:
            # pystray's Xorg run_detached creates a non-daemon thread. A stalled
            # X connection would otherwise keep the entire app alive after Quit.
            def run():
                try:
                    icon.run()
                except Exception:
                    logging.exception("Tray event loop failed")
            threading.Thread(target=run, name="panoptix-tray", daemon=True).start()
    except Exception:
        return None  # Keep the dashboard usable when a tray is unavailable.
    return icon
