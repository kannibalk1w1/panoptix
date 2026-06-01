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

    def test_review_ui_exposes_redaction_preset_controls_and_history(self):
        app_js = (Path(__file__).resolve().parents[1] / "frontend" / "app.js").read_text(encoding="utf-8")

        self.assertIn("Top strip", app_js)
        self.assertIn("Bottom strip", app_js)
        self.assertIn("Left strip", app_js)
        self.assertIn("Right strip", app_js)
        self.assertIn("data-redact-preset", app_js)
        self.assertIn("renderRedactionHistory", app_js)

    def test_review_ui_exposes_evidence_pack_export(self):
        app_js = (Path(__file__).resolve().parents[1] / "frontend" / "app.js").read_text(encoding="utf-8")

        self.assertIn("Export evidence pack", app_js)
        self.assertIn("export-pack", app_js)
        self.assertIn("exportEvidencePack", app_js)

    def test_review_ui_exposes_evidence_pack_verification(self):
        app_js = (Path(__file__).resolve().parents[1] / "frontend" / "app.js").read_text(encoding="utf-8")

        self.assertIn("Verify evidence pack", app_js)
        self.assertIn("verify-pack", app_js)
        self.assertIn("verifyEvidencePack", app_js)

    def test_review_ui_exposes_search_and_filter_controls(self):
        app_js = (Path(__file__).resolve().parents[1] / "frontend" / "app.js").read_text(encoding="utf-8")

        self.assertIn("review-search", app_js)
        self.assertIn("data-review-filter=\"selected\"", app_js)
        self.assertIn("data-review-filter=\"redacted\"", app_js)
        self.assertIn("data-review-filter=\"clicks\"", app_js)
        self.assertIn("filterReviewEvents", app_js)

    def test_index_loads_review_filter_helper_before_app(self):
        index_html = (Path(__file__).resolve().parents[1] / "frontend" / "index.html").read_text(encoding="utf-8")

        self.assertLess(index_html.index("/reviewFilters.js"), index_html.index("/app.js"))


if __name__ == "__main__":
    unittest.main()
