from __future__ import annotations

from typing import Any, Callable


class HotkeyService:
    def __init__(self, settings_store: Any, recorder: Any, listener_factory: Callable | None = None):
        self.settings_store = settings_store
        self.recorder = recorder
        self.listener_factory = listener_factory
        self.listener = None
        self.error: str | None = None

    def start(self) -> None:
        settings = self.settings_store.load()
        if not settings.get("manual_hotkey_enabled"):
            return
        hotkey = str(settings.get("manual_hotkey") or "").strip()
        if not hotkey:
            return
        factory = self.listener_factory or self._default_listener_factory()
        if factory is None:
            self.error = "pynput is not installed; manual hotkey is unavailable"
            return
        try:
            self.listener = factory({hotkey: self._capture})
            self.listener.start()
        except Exception as exc:
            self.error = str(exc)
            self.listener = None

    def stop(self) -> None:
        if self.listener is not None:
            self.listener.stop()
            self.listener = None

    def restart(self) -> None:
        self.stop()
        self.start()

    def _capture(self) -> None:
        try:
            self.recorder.capture_manual_hotkey()
        except RuntimeError:
            return

    @staticmethod
    def _default_listener_factory() -> Callable | None:
        try:
            from pynput import keyboard
        except ImportError:
            return None
        return keyboard.GlobalHotKeys
