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

    def test_settings_ui_exposes_export_directory(self):
        app_js = (Path(__file__).resolve().parents[1] / "frontend" / "app.js").read_text(encoding="utf-8")

        self.assertIn("Export folder", app_js)
        self.assertIn("export_directory", app_js)

    def test_settings_ui_exposes_selectable_screenshot_folder(self):
        app_js = (Path(__file__).resolve().parents[1] / "frontend" / "app.js").read_text(encoding="utf-8")

        self.assertIn("Screenshot storage folder", app_js)
        self.assertIn("renderDataLocationCard", app_js)
        self.assertIn("data-directory", app_js)
        self.assertIn("browse-data-directory", app_js)
        self.assertIn("save-data-directory", app_js)
        self.assertIn("reset-data-directory", app_js)
        self.assertIn("/api/data-location", app_js)
        self.assertIn("/api/browse-folder", app_js)
        self.assertIn("Restart Panoptix to start using it", app_js)

    def test_settings_ui_exposes_folder_browse_for_exports(self):
        app_js = (Path(__file__).resolve().parents[1] / "frontend" / "app.js").read_text(encoding="utf-8")

        self.assertIn("browseForFolder", app_js)
        self.assertIn("data-browse-folder=\"export_directory\"", app_js)

    def test_dashboard_surfaces_screenshot_folder_warning(self):
        app_js = (Path(__file__).resolve().parents[1] / "frontend" / "app.js").read_text(encoding="utf-8")

        self.assertIn("Screenshot folder warning", app_js)
        self.assertIn("data_location", app_js)

    def test_settings_ui_exposes_background_capture_controls(self):
        app_js = (Path(__file__).resolve().parents[1] / "frontend" / "app.js").read_text(encoding="utf-8")

        self.assertIn("Scheduled passive capture", app_js)
        self.assertIn("background_enabled", app_js)
        self.assertIn("background_start_time", app_js)
        self.assertIn("background_end_time", app_js)
        self.assertIn("background_interval_seconds", app_js)
        self.assertIn("background_change_detection", app_js)

    def test_settings_ui_exposes_manual_hotkey_controls(self):
        app_js = (Path(__file__).resolve().parents[1] / "frontend" / "app.js").read_text(encoding="utf-8")

        self.assertIn("Manual capture hotkey", app_js)
        self.assertIn("manual_hotkey_enabled", app_js)
        self.assertIn("manual_hotkey", app_js)
        self.assertIn("launch_on_startup", app_js)

    def test_dashboard_surfaces_background_system_status(self):
        app_js = (Path(__file__).resolve().parents[1] / "frontend" / "app.js").read_text(encoding="utf-8")

        self.assertIn("renderSystemStatus", app_js)
        self.assertIn("Skipped unchanged frames", app_js)
        self.assertIn("Export folder warning", app_js)
        self.assertIn("Windows startup", app_js)
        self.assertIn("Manual hotkey", app_js)

    def test_review_exports_require_personal_data_acknowledgement(self):
        app_js = (Path(__file__).resolve().parents[1] / "frontend" / "app.js").read_text(encoding="utf-8")

        self.assertIn("Personal data check", app_js)
        self.assertIn("privacy-review-confirmed", app_js)
        self.assertIn("requirePrivacyReview", app_js)
        self.assertIn("check selected screenshots for personal data", app_js)

    def test_review_refreshes_mutated_screenshot_urls_and_blocks_empty_image_exports(self):
        app_js = (Path(__file__).resolve().parents[1] / "frontend" / "app.js").read_text(encoding="utf-8")

        self.assertIn("screenshotVersion", app_js)
        self.assertIn("cacheKey", app_js)
        self.assertIn("selectedImageCount", app_js)
        self.assertIn("requireSelectedScreenshots", app_js)
        self.assertIn("No screenshots are currently selected for export", app_js)

    def test_status_poll_updates_banner_and_rerenders_on_tray_state_changes(self):
        app_js = (Path(__file__).resolve().parents[1] / "frontend" / "app.js").read_text(encoding="utf-8")

        self.assertIn("statusSignature", app_js)
        self.assertIn("updateLiveStatusDisplay", app_js)
        self.assertIn("data-live-event-count", app_js)
        self.assertIn("data-system-skipped", app_js)
        # The elapsed time has to be live too, not baked into the banner markup.
        self.assertIn("data-live-elapsed", app_js)

    def test_status_catches_up_when_the_page_is_looked_at_again(self):
        app_js = (Path(__file__).resolve().parents[1] / "frontend" / "app.js").read_text(encoding="utf-8")

        # Browsers throttle timers in background tabs, so the 5s poll alone
        # leaves the screenshot count stale while staff work in another window.
        self.assertIn("visibilitychange", app_js)
        self.assertIn('window.addEventListener("focus", pollStatus)', app_js)
        self.assertIn("setInterval(pollStatus, 5000)", app_js)
        # A failed poll must not stop the timer.
        self.assertIn("Status poll failed", app_js)

    def test_settings_and_review_show_feedback_for_save_and_search(self):
        app_js = (Path(__file__).resolve().parents[1] / "frontend" / "app.js").read_text(encoding="utf-8")

        self.assertIn("settings-save-feedback", app_js)
        self.assertIn("Settings saved", app_js)
        self.assertIn("Search active", app_js)
        self.assertIn("clear-review-search", app_js)


if __name__ == "__main__":
    unittest.main()
