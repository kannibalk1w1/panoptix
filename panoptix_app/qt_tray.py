"""Standalone Qt tray helper; executed with the Linux system Python."""
from __future__ import annotations

import json
import os
import signal
import sys

from PyQt6.QtCore import QSocketNotifier, QTimer, QUrl
from PyQt6.QtGui import QColor, QDesktopServices, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon


def main():
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Panoptix")
    app.setQuitOnLastWindowClosed(False)
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return 1
    base_url = sys.argv[1].rstrip("/")
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor("transparent"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#4ade80"), 5))
    painter.drawEllipse(14, 14, 36, 36)
    painter.setBrush(QColor("#4ade80"))
    painter.drawEllipse(28, 28, 8, 8)
    painter.end()
    tray = QSystemTrayIcon(QIcon(pixmap))
    tray.setToolTip("Panoptix")
    menu = QMenu()
    tray.setContextMenu(menu)
    network = QNetworkAccessManager(app)
    actions = {}

    def open_dashboard():
        QDesktopServices.openUrl(QUrl(base_url))

    def post(path, quitting=False):
        request = QNetworkRequest(QUrl(base_url + path))
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        request.setTransferTimeout(5000)
        reply = network.post(request, b"{}")
        def finished():
            if reply.error() != QNetworkReply.NetworkError.NoError:
                tray.showMessage("Panoptix", "The action could not be completed. Check the dashboard.")
            elif quitting:
                tray.hide()
                app.quit()
            reply.deleteLater()
        reply.finished.connect(finished)

    action = menu.addAction("Open dashboard")
    action.triggered.connect(open_dashboard)
    menu.addSeparator()
    for label, path in (
        ("Start passive capture now", "/api/tray/start-background"),
        ("Caption next capture", "/api/capture-note/prompt"),
        ("Capture screenshot", "/api/capture/manual"),
        ("Record clip", "/api/clips/start"),
        ("Pause capture", "/api/record/pause"),
        ("Resume capture", "/api/record/resume"),
        ("Stop capture", "/api/record/stop"),
    ):
        action = menu.addAction(label)
        action.triggered.connect(lambda checked=False, path=path: post(path))
        actions[label] = action
    menu.addSeparator()
    quit_action = menu.addAction("Quit Panoptix")
    quit_action.triggered.connect(lambda: post("/api/app/quit", quitting=True))
    tray.activated.connect(lambda reason: open_dashboard() if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick) else None)

    poll_pending = False
    def poll():
        nonlocal poll_pending
        if poll_pending:
            return
        poll_pending = True
        request = QNetworkRequest(QUrl(base_url + "/api/status"))
        request.setTransferTimeout(3000)
        reply = network.get(request)
        def finished():
            nonlocal poll_pending
            poll_pending = False
            try:
                state = json.loads(bytes(reply.readAll()))
                active, paused = state.get("active", False), state.get("paused", False)
                clip_active = state.get("clip", {}).get("active", False)
                editing = state.get("capture_note", {}).get("editing", False)
                actions["Start passive capture now"].setEnabled(not active)
                actions["Capture screenshot"].setEnabled(active and not paused and not editing)
                actions["Caption next capture"].setEnabled(not clip_active and not editing)
                actions["Record clip"].setEnabled(not clip_active and not editing and not (state.get("mode") == "lms" and paused))
                actions["Pause capture"].setEnabled(active and not paused)
                actions["Resume capture"].setEnabled(active and paused)
                actions["Stop capture"].setEnabled(active)
            except (ValueError, TypeError):
                pass
            reply.deleteLater()
        reply.finished.connect(finished)
    timer = QTimer(app)
    timer.timeout.connect(poll)
    timer.start(2000)

    # EOF means the parent has exited, even if it was killed unexpectedly.
    notifier = QSocketNotifier(sys.stdin.fileno(), QSocketNotifier.Type.Read, app)
    pending = b""
    def control(*_):
        nonlocal pending
        data = os.read(sys.stdin.fileno(), 4096)
        if not data:
            app.quit()
            return
        pending += data
        while b"\n" in pending:
            command, pending = pending.split(b"\n", 1)
            if command == b"quit":
                app.quit()
            elif command == b"hide":
                tray.hide()
            elif command == b"show":
                tray.show()
    notifier.activated.connect(control)
    app.aboutToQuit.connect(tray.hide)
    signal.signal(signal.SIGTERM, lambda *_: app.quit())
    tray.show()
    QTimer.singleShot(0, lambda: print("READY", flush=True))
    QTimer.singleShot(0, poll)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
