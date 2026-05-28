from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panoptix_app.capture import PlaceholderCapture
from panoptix_app.exporter import HtmlExporter
from panoptix_app.storage import SessionStore


class HtmlExporterTests(unittest.TestCase):
    def test_export_writes_self_contained_html_report(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SessionStore(root)
            session = store.create_session(
                "evidence",
                {"cyp": "AB", "activity": "Scratch game", "staff": "KS"},
                {},
            )
            screenshot = PlaceholderCapture().capture(
                root / "sessions" / session["id"] / "screenshots",
                "001.png",
            )
            store.add_event(
                session["id"],
                {
                    "type": "click",
                    "timestamp": "2026-05-28T10:00:00",
                    "screenshot": screenshot.name,
                    "x": 10,
                    "y": 20,
                    "title": "Opened Scratch",
                    "staff_note": "CYP selected the correct project.",
                    "cyp_quote": "I know where my game is.",
                    "tags": ["independent work"],
                },
            )

            output = HtmlExporter(root).export(session["id"])
            html = output.read_text(encoding="utf-8")

            self.assertIn("Scratch game", html)
            self.assertIn("Opened Scratch", html)
            self.assertIn("data:image/png;base64,", html)
            self.assertIn("independent work", html)


if __name__ == "__main__":
    unittest.main()
