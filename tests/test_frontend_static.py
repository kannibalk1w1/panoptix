from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class FrontendStaticTests(unittest.TestCase):
    def test_review_ui_exposes_manual_redaction_box_controls(self):
        app_js = (Path(__file__).resolve().parents[1] / "frontend" / "app.js").read_text(encoding="utf-8")

        self.assertIn("Apply redaction box", app_js)
        self.assertIn("data-redact-box", app_js)
        self.assertIn("redaction-field", app_js)
        self.assertIn("async function redactBox", app_js)


if __name__ == "__main__":
    unittest.main()
