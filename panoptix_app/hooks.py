from __future__ import annotations

from typing import Callable


class GlobalMouseHook:
    def __init__(self, on_click: Callable[[int, int], None]):
        self.on_click = on_click
        self._listener = None

    def start(self) -> None:
        try:
            from pynput import mouse
        except ImportError as exc:
            raise RuntimeError("pynput is not installed; global click capture is unavailable") from exc

        def handle_click(x, y, button, pressed):
            if not pressed:
                return
            if button == mouse.Button.left:
                self.on_click(int(x), int(y))

        self._listener = mouse.Listener(on_click=handle_click)
        self._listener.daemon = True
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
