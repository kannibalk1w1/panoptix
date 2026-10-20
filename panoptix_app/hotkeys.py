from __future__ import annotations

from typing import Any, Callable
import logging


class HotkeyService:
    def __init__(self, settings_store: Any, recorder: Any, listener_factory: Callable | None = None, clip_recorder: Any | None = None):
        self.clip_recorder = clip_recorder
        self.settings_store = settings_store
        self.recorder = recorder
        self.listener_factory = listener_factory
        self.listener = None
        self.error: str | None = None

    def start(self) -> None:
        self.error = None
        settings = self.settings_store.load()
        mapping = {}
        if settings.get("manual_hotkey_enabled") and settings.get("manual_hotkey"):
            mapping[settings["manual_hotkey"]] = self._capture
        if self.clip_recorder is not None and settings.get("clip_hotkey_enabled") and settings.get("clip_hotkey"):
            mapping[settings["clip_hotkey"]] = self._clip
        if settings.get("capture_note_hotkey_enabled") and settings.get("capture_note_hotkey"):
            mapping[settings["capture_note_hotkey"]] = self._note
        if not mapping:
            return
        factory = self.listener_factory or self._default_listener_factory()
        if factory is None:
            self.error = "pynput is not installed; capture hotkeys are unavailable"
            return
        try:
            self.listener = factory(mapping)
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
        except Exception:
            logging.exception("Manual capture failed")

    def _note(self) -> None:
        self.recorder.notes.open_prompt(self.clip_recorder)

    def _clip(self) -> None:
        try:
            self.clip_recorder.start(self.settings_store.load())
        except RuntimeError:
            return  # Key repeat never starts overlapping clips.
        except Exception:
            logging.exception("Clip could not start")

    @staticmethod
    def _default_listener_factory() -> Callable | None:
        try:
            from pynput import keyboard
        except ImportError:
            return None
        return keyboard.GlobalHotKeys
