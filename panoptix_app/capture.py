from __future__ import annotations

import base64
from pathlib import Path


PLACEHOLDER_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADggGOSHzRgAAAAABJRU5ErkJggg=="
)


class PlaceholderCapture:
    def __init__(self) -> None:
        self.last_origin: tuple[int, int] = (0, 0)

    def capture(self, output_dir: Path, filename: str, marker: tuple[int, int] | None = None) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / filename
        self.last_origin = (0, 0)
        try:
            from PIL import Image
            Image.new("RGB", (320, 180), "#202733").save(path)
        except ImportError:
            path.write_bytes(PLACEHOLDER_PNG)
        return path


class ScreenCapture:
    def __init__(self) -> None:
        # Top-left of the virtual desktop for the most recent capture. Mouse
        # coordinates are virtual-desktop absolute, so callers subtract this to
        # place a marker on the saved image. It is only non-zero when a monitor
        # sits above or to the left of the primary one.
        self.last_origin: tuple[int, int] = (0, 0)

    def capture(self, output_dir: Path, filename: str, marker: tuple[int, int] | None = None) -> Path:
        try:
            import mss
            from PIL import Image, ImageDraw
        except ImportError:
            fallback = PlaceholderCapture()
            path = fallback.capture(output_dir, filename, marker)
            self.last_origin = fallback.last_origin
            return path

        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / filename
        with mss.mss() as screen:
            # monitors[0] is the virtual screen bounding every display, so this
            # grabs all monitors. monitors[1] would only be the primary one.
            monitor = screen.monitors[0]
            shot = screen.grab(monitor)
            image = Image.frombytes("RGB", shot.size, shot.rgb)
        self.last_origin = (int(monitor["left"]), int(monitor["top"]))
        if marker is not None:
            x, y = to_image_coordinates(marker[0], marker[1], self.last_origin)
            draw = ImageDraw.Draw(image)
            radius = 16
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline="#ef233c", width=3)
        image.save(path)
        return path


def to_image_coordinates(x: int, y: int, origin: tuple[int, int]) -> tuple[int, int]:
    """Translate absolute mouse coordinates into pixels on the captured image."""
    return int(x) - int(origin[0]), int(y) - int(origin[1])
