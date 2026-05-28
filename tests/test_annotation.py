from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image

from panoptix_app.annotation import DEFAULT_MARKER, annotate_click, update_event_marker
from panoptix_app.storage import SessionStore


class AnnotationTests(unittest.TestCase):
    def test_annotate_click_writes_annotated_copy_without_modifying_original(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / "original.png"
            annotated = root / "annotated.png"
            Image.new("RGB", (100, 100), "white").save(original)

            annotate_click(original, annotated, 50, 50, {**DEFAULT_MARKER, "shape": "crosshair", "size": 30})

            with Image.open(original) as image:
                self.assertEqual(image.getpixel((50, 50)), (255, 255, 255))
            with Image.open(annotated) as image:
                self.assertNotEqual(image.getpixel((50, 50)), (255, 255, 255))

    def test_annotate_click_supports_square_marker(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / "original.png"
            annotated = root / "annotated.png"
            Image.new("RGB", (80, 80), "white").save(original)

            annotate_click(original, annotated, 40, 40, {**DEFAULT_MARKER, "shape": "square", "size": 20})

            with Image.open(annotated) as image:
                self.assertNotEqual(image.getpixel((30, 30)), (255, 255, 255))

    def test_update_event_marker_regenerates_from_clean_original(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SessionStore(root)
            session = store.create_session("evidence", {}, {})
            screenshot_dir = store.screenshot_dir(session["id"])
            original_dir = screenshot_dir / "originals"
            original_dir.mkdir()
            original = original_dir / "001.png"
            annotated = screenshot_dir / "001.png"
            Image.new("RGB", (80, 80), "white").save(original)
            Image.new("RGB", (80, 80), "white").save(annotated)
            store.add_event(
                session["id"],
                {
                    "type": "click",
                    "timestamp": "now",
                    "screenshot": "001.png",
                    "original_screenshot": "originals/001.png",
                    "x": 40,
                    "y": 40,
                    "redactions": [{"type": "black_box"}],
                },
            )

            result = update_event_marker(store, session["id"], 1, {"shape": "crosshair", "color": "#0000ff", "size": 20})

            self.assertEqual(result["event"]["marker"]["shape"], "crosshair")
            self.assertEqual(result["event"]["redactions"], [])
            with Image.open(original) as image:
                self.assertEqual(image.getpixel((40, 40)), (255, 255, 255))
            with Image.open(annotated) as image:
                self.assertNotEqual(image.getpixel((40, 40)), (255, 255, 255))


if __name__ == "__main__":
    unittest.main()
