from __future__ import annotations

import webbrowser
from typing import Any


def start_tray(url: str, recorder: Any, settings_store: Any, server: Any):
    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError:
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
        icon.stop()
        server.shutdown()

    image = Image.new("RGB", (64, 64), "#101318")
    draw = ImageDraw.Draw(image)
    draw.ellipse((14, 14, 50, 50), outline="#4ade80", width=5)
    draw.ellipse((28, 28, 36, 36), fill="#4ade80")

    icon = pystray.Icon(
        "Panoptix",
        image,
        "Panoptix",
        menu=pystray.Menu(
            pystray.MenuItem("Open dashboard", open_dashboard),
            pystray.MenuItem("Start passive capture now", start_background_now),
            pystray.MenuItem("Pause capture", pause),
            pystray.MenuItem("Resume capture", resume),
            pystray.MenuItem("Manual screenshot", manual_capture),
            pystray.MenuItem("Stop capture", stop_capture),
            pystray.MenuItem("Quit Panoptix", quit_panoptix),
        ),
    )
    icon.run_detached()
    return icon
