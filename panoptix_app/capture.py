from __future__ import annotations

import base64
from pathlib import Path


PLACEHOLDER_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADggGOSHzRgAAAAABJRU5ErkJggg=="
)


class PlaceholderCapture:
    def capture(self, output_dir: Path, filename: str, marker: tuple[int, int] | None = None) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / filename
        try:
            from PIL import Image
            Image.new("RGB", (320, 180), "#202733").save(path)
        except ImportError:
            path.write_bytes(PLACEHOLDER_PNG)
        return path


class ScreenCapture:
    def capture(self, output_dir: Path, filename: str, marker: tuple[int, int] | None = None) -> Path:
        try:
            import mss
            from PIL import Image, ImageDraw
        except ImportError:
            return PlaceholderCapture().capture(output_dir, filename, marker)

        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / filename
        with mss.mss() as screen:
            monitor = screen.monitors[1]
            shot = screen.grab(monitor)
            image = Image.frombytes("RGB", shot.size, shot.rgb)
        if marker is not None:
            x, y = marker
            draw = ImageDraw.Draw(image)
            radius = 16
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline="#ef233c", width=3)
        image.save(path)
        return path
