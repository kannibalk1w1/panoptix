"""Real browser regressions: python -m unittest tests.browser_review -v."""
from http.server import ThreadingHTTPServer
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch
from zipfile import ZipFile
from PIL import Image

from playwright.sync_api import sync_playwright, expect

from panoptix_app.capture import PlaceholderCapture
from panoptix_app.recorder import Recorder
from panoptix_app.server import create_handler
from panoptix_app.storage import SessionStore
from panoptix_app.persistence import write_json
from panoptix_app.settings import SettingsStore
from tests.test_review_regressions import NoopHook


class BrowserReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(executable_path=os.environ.get("PANOPTIX_TEST_BROWSER"))

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        temporary = TemporaryDirectory(prefix="panoptix-browser-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        env = patch.dict(os.environ, {"PANOPTIX_DATA_DIR": str(self.root), "PANOPTIX_CONFIG_DIR": str(self.root / "config")})
        env.start()
        self.addCleanup(env.stop)
        self.store = SessionStore(self.root)
        self.recorder = Recorder(self.store, PlaceholderCapture(), NoopHook)
        self.sid = self.recorder.start("evidence", {"activity": "Browser review"})["id"]
        for _ in range(2):
            self.recorder.capture_click(60, 60)
        self.recorder.stop()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(self.root, self.store, self.recorder))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)
        self.context = self.browser.new_context()
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.dialogs = []
        self.page.on("dialog", self.accept_dialog)
        self.page.goto(f"http://127.0.0.1:{self.server.server_port}")
        expect(self.page.locator("#page-title")).to_have_text("Home")

    def close_server(self):
        self.recorder.stop()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def accept_dialog(self, dialog):
        self.dialogs.append(dialog.message)
        dialog.accept()

    def open_review(self):
        self.page.locator('[data-view="sessions"]').click()
        self.page.locator(f'[data-open="{self.sid}"]').click()
        expect(self.page.locator("#export-pack")).to_be_visible()

    def note(self, index):
        return self.page.locator(f'[data-event="{index}"][data-field="staff_note"]')

    def test_drafts_survive_save_filter_navigation_and_export(self):
        self.open_review()
        self.note(1).fill("Saved first note")
        self.note(2).fill("Unsaved second note")
        self.page.locator('[data-save-event="1"]').click()
        self.page.wait_for_function("reviewSession.events[0].staff_note === 'Saved first note' && !reviewDrafts.has(draftKey(currentSessionId, '001.png'))")
        self.page.locator('[data-review-filter="unselected"]').click()
        expect(self.note(2)).to_have_count(0)
        self.page.locator('[data-review-filter="all"]').click()
        expect(self.note(2)).to_have_value("Unsaved second note")
        self.page.locator('[data-view="home"]').click()
        self.open_review()
        expect(self.note(2)).to_have_value("Unsaved second note")
        self.page.locator("#privacy-review-confirmed").check()
        with self.page.expect_response(lambda response: response.url.endswith("/export-pack")) as exported:
            self.page.locator("#export-pack").click()
        self.assertEqual(exported.value.status, 200)
        self.page.wait_for_function("reviewDrafts.size === 0")
        self.assertEqual(self.store.load_session(self.sid)["events"][1]["staff_note"], "Unsaved second note")

    def test_filter_does_not_block_export_of_hidden_selected_images(self):
        self.store.update_event(self.sid, 2, {"selected_for_export": False})
        self.open_review()
        self.page.locator('[data-review-filter="unselected"]').click()
        expect(self.note(1)).to_have_count(0)
        self.page.locator("#privacy-review-confirmed").check()
        with self.page.expect_response(lambda response: response.url.endswith("/export-images")) as exported:
            self.page.locator("#export-annotated-images").click()
        self.assertEqual(exported.value.status, 200)
        with ZipFile(self.root / "exports" / self.sid / "selected-images-annotated.zip") as archive:
            self.assertTrue(any(name.endswith("001_annotated.png") for name in archive.namelist()))
            self.assertFalse(any(name.endswith("002_annotated.png") for name in archive.namelist()))

    def test_failed_export_shows_error_without_success(self):
        self.open_review()
        self.page.route("**/export-pack", lambda route: route.fulfill(status=400, json={"error": "Export folder is read-only"}))
        self.page.locator("#privacy-review-confirmed").check()
        with self.page.expect_event("dialog") as shown:
            self.page.locator("#export-pack").click()
        self.assertEqual(shown.value.message, "Export folder is read-only")
        self.assertFalse(any("Exported evidence pack" in message for message in self.dialogs))

    def test_failed_settings_save_does_not_claim_success(self):
        self.page.locator('[data-view="settings"]').click()
        expect(self.page.locator("#settings-form")).to_be_visible()
        self.page.route("**/api/settings", lambda route: route.fulfill(status=400, json={"error": "Cannot save settings"}) if route.request.method == "PATCH" else route.continue_())
        self.page.locator('[name="storage_warning_mb"]').fill("750")
        with self.page.expect_event("dialog") as shown:
            self.page.locator('#settings-form button[type="submit"]').click()
        self.assertEqual(shown.value.message, "Cannot save settings")
        expect(self.page.locator("#settings-save-feedback")).to_have_count(0)

    def test_originals_require_explicit_choice_and_warning(self):
        self.open_review()
        self.page.locator("#privacy-review-confirmed").check()
        with self.page.expect_response(lambda response: response.url.endswith("/export-pack")) as exported:
            self.page.locator("#export-pack").click()
        self.assertFalse(exported.value.request.post_data_json["include_originals"])
        self.page.locator("#pack-include-originals").check()
        with self.page.expect_response(lambda response: response.url.endswith("/export-pack")) as exported:
            self.page.locator("#export-pack").click()
        self.assertTrue(exported.value.request.post_data_json["include_originals"])
        self.assertTrue(any("UNREDACTED originals" in message for message in self.dialogs))

    def test_pause_and_stop_send_one_request_each(self):
        self.recorder.start("observation", settings={"interval_seconds": 3600})
        self.page.locator('[data-view="observation"]').click()
        expect(self.page.locator("#banner-pause")).to_have_text("Pause")
        calls = []
        self.page.on("request", lambda request: calls.append(request.url) if request.method == "POST" else None)
        self.page.locator("#banner-pause").click()
        expect(self.page.locator("#banner-pause")).to_have_text("Resume")
        self.assertEqual(sum(url.endswith("/api/record/pause") for url in calls), 1)
        self.page.locator("#banner-stop").click()
        expect(self.page.locator("#banner-stop")).to_have_count(0)
        self.assertEqual(sum(url.endswith("/api/record/stop") for url in calls), 1)

    def test_review_stays_open_when_recording_status_changes(self):
        # This path previously left currentView set to observation after Stop.
        self.recorder.start("observation", settings={"interval_seconds": 3600})
        self.page.locator('[data-view="observation"]').click()
        self.page.locator("#stop").click()
        self.page.locator(f'[data-open="{self.sid}"]').click()
        expect(self.page.locator("#export-pack")).to_be_visible()

        self.recorder.start("observation", settings={"interval_seconds": 3600})
        self.page.evaluate("pollStatus()")
        expect(self.page.locator("#page-title")).to_have_text("Review")
        expect(self.page.locator("#export-pack")).to_be_visible()

    def test_save_all_includes_filtered_drafts_and_updates_indicator(self):
        self.open_review()
        expect(self.page.locator("#draft-status")).to_have_text("All changes saved")
        self.note(1).fill("First draft")
        self.note(2).fill("Second draft")
        expect(self.page.locator("#draft-status")).to_contain_text("2 screenshots")
        self.page.locator('[data-review-filter="highlights"]').click()
        expect(self.note(1)).to_have_count(0)
        self.page.locator("#save-all-notes").click()
        expect(self.page.locator("#draft-status")).to_have_text("All changes saved")
        expect(self.page.locator("#save-all-notes")).to_be_disabled()
        self.assertEqual([event["staff_note"] for event in self.store.load_session(self.sid)["events"]], ["First draft", "Second draft"])

    def test_open_export_folder_uses_session_destination(self):
        self.open_review()
        with patch("panoptix_app.server.open_folder") as opened:
            with self.page.expect_response(lambda response: response.url.endswith("/api/exports/open-folder")) as response:
                self.page.locator("#open-export-folder").click()
            self.assertEqual(response.value.status, 200)
            opened.assert_called_once_with(self.root / "exports" / self.sid)

    def test_session_search_and_inclusive_dates(self):
        for title, date in (("Alpha activity", "2025-01-10T10:00:00"), ("Beta activity", "2025-01-11T10:00:00")):
            session = self.store.create_session("observation", {"activity": title})
            session["started"] = date
            write_json(self.store.sessions_dir / session["id"] / "session.json", session)
        self.page.locator('[data-view="sessions"]').click()
        self.page.locator("#session-search").fill("activity")
        expect(self.page.locator("#session-rows .session-row")).to_have_count(2)
        self.page.locator("#session-from").fill("2025-01-10")
        self.page.locator("#session-to").fill("2025-01-10")
        expect(self.page.locator("#session-rows .session-row")).to_have_count(1)
        expect(self.page.locator("#session-rows")).to_contain_text("Alpha activity")
        self.page.locator("#clear-session-filters").click()
        expect(self.page.locator("#session-rows .session-row")).to_have_count(3)

    def test_zoomed_reverse_drag_redacts_correct_image_pixels(self):
        self.open_review()
        self.page.locator('[data-zoom-event="1"]').click()
        self.page.wait_for_function("document.querySelector('.zoom-image').naturalWidth > 0")
        self.page.locator("#image-zoom").select_option("2")
        image = self.page.locator(".zoom-image")
        expect(image).to_have_css("width", "640px")
        bounds = image.bounding_box()
        self.page.mouse.move(bounds["x"] + 200, bounds["y"] + 160)
        self.page.mouse.down()
        self.page.mouse.move(bounds["x"] + 40, bounds["y"] + 20, steps=5)
        self.page.mouse.up()
        with self.page.expect_response(lambda response: response.url.endswith("/redact")) as response:
            self.page.locator("#apply-drag-redaction").click()
        self.assertEqual(response.value.status, 200)
        rect = response.value.request.post_data_json["rect"]
        for key, expected in {"x": 20, "y": 10, "width": 80, "height": 70}.items():
            self.assertAlmostEqual(rect[key], expected, delta=1)
        with Image.open(self.store.screenshot_dir(self.sid) / "001.png") as saved:
            self.assertEqual(saved.getpixel((30, 20)), (0, 0, 0))
        self.page.locator("[data-close-dialog]").click()
        expect(self.page.locator(".redaction-count")).to_have_text("1 redaction applied")

    def test_retention_preview_cancel_then_restore(self):
        session = self.store.load_session(self.sid)
        session["started"] = "2020-01-01T10:00:00"
        write_json(self.store.sessions_dir / self.sid / "session.json", session)
        self.page.locator('[data-view="settings"]').click()
        self.page.locator("#cleanup-retention").click()
        expect(self.page.locator("#cleanup-sessions")).to_contain_text("Browser review")
        self.page.locator("[data-close-dialog]").click()
        self.assertTrue(self.store.load_session(self.sid))
        self.page.locator("#cleanup-retention").click()
        self.page.locator("#confirm-cleanup").click()
        expect(self.page.locator("#page-title")).to_have_text("Deleted sessions")
        self.assertEqual(self.store.list_sessions(), [])
        self.page.locator("[data-restore-session]").click()
        expect(self.page.locator("[data-restore-session]")).to_have_count(0)
        self.assertEqual(len(self.store.load_session(self.sid)["events"]), 2)

    def test_deleted_session_can_be_permanently_removed(self):
        self.page.locator('[data-view="sessions"]').click()
        self.page.locator(f'[data-delete-session="{self.sid}"]').click()
        self.page.locator("#show-trash").click()
        expect(self.page.locator("[data-purge-session]")).to_have_count(1)
        self.page.locator("[data-purge-session]").click()
        expect(self.page.locator("[data-purge-session]")).to_have_count(0)
        self.assertTrue(any("cannot be undone" in message for message in self.dialogs))
        self.assertEqual(self.store.list_trash(), [])
        self.assertFalse(any((self.root / "trash").iterdir()))

    def test_fit_view_redaction_maps_large_screenshot_to_native_pixels(self):
        directory = self.store.screenshot_dir(self.sid)
        for path in (directory / "001.png", directory / "originals" / "001.png"):
            Image.new("RGB", (3200, 1800), "white").save(path)
        self.open_review()
        self.page.locator('[data-zoom-event="1"]').click()
        self.page.wait_for_function("document.querySelector('.zoom-image').naturalWidth === 3200")
        image = self.page.locator(".zoom-image")
        bounds = image.bounding_box()
        self.assertLess(bounds["width"], 3200)
        self.page.mouse.move(bounds["x"] + bounds["width"] * 0.1, bounds["y"] + bounds["height"] * 0.2)
        self.page.mouse.down()
        self.page.mouse.move(bounds["x"] + bounds["width"] * 0.3, bounds["y"] + bounds["height"] * 0.4, steps=5)
        self.page.mouse.up()
        with self.page.expect_response(lambda response: response.url.endswith("/redact")) as response:
            self.page.locator("#apply-drag-redaction").click()
        self.assertEqual(response.value.status, 200)
        rect = response.value.request.post_data_json["rect"]
        for key, expected in {"x": 320, "y": 360, "width": 640, "height": 360}.items():
            self.assertAlmostEqual(rect[key], expected, delta=3)
        with Image.open(directory / "001.png") as saved:
            self.assertEqual(saved.getpixel((400, 400)), (0, 0, 0))
            self.assertEqual(saved.getpixel((1200, 800)), (255, 255, 255))

    def test_weekly_timetable_drag_keyboard_and_save(self):
        self.page.locator('[data-view="settings"]').click()
        self.page.locator('[data-schedule-action="clear"]').click()
        cell = lambda day, slot: self.page.locator(f'[data-day="{day}"][data-slot="{slot}"]')
        cell(0, 18).scroll_into_view_if_needed()
        first, last = cell(0, 18).bounding_box(), cell(2, 20).bounding_box()
        self.page.mouse.move(first["x"] + first["width"] / 2, first["y"] + first["height"] / 2)
        self.page.mouse.down()
        self.page.mouse.move(last["x"] + last["width"] / 2, last["y"] + last["height"] / 2, steps=6)
        self.page.mouse.up()
        expect(cell(1, 19)).to_have_attribute("aria-pressed", "true")
        expect(cell(3, 19)).to_have_attribute("aria-pressed", "false")
        cell(1, 19).focus()
        cell(1, 19).press("Space")
        expect(cell(1, 19)).to_have_attribute("aria-pressed", "false")
        self.page.locator('[name="background_enabled"]').check()
        self.page.locator('#settings-form button[type="submit"]').click()
        expect(self.page.locator("#settings-save-feedback")).to_have_text("Settings saved")
        saved = SettingsStore(self.root).load()["background_weekly_schedule"]
        self.assertEqual(sum(sum(day) for day in saved), 8)
        self.assertTrue(saved[2][20])
        self.assertFalse(saved[1][19])
        self.page.reload()
        self.page.locator('[data-view="settings"]').click()
        expect(cell(2, 20)).to_have_attribute("aria-pressed", "true")
        expect(cell(1, 19)).to_have_attribute("aria-pressed", "false")

    def test_timetable_presets_copy_and_keep_edits_during_status_change(self):
        self.page.locator('[data-view="settings"]').click()
        self.page.locator('[data-schedule-action="weekdays"]').click()
        expect(self.page.locator('[data-day="5"][data-slot="18"]')).to_have_attribute("aria-pressed", "false")
        self.page.locator('[data-schedule-action="copy"]').click()
        expect(self.page.locator('[data-day="5"][data-slot="18"]')).to_have_attribute("aria-pressed", "true")
        self.recorder.start("observation", settings={"interval_seconds": 3600})
        self.page.evaluate("pollStatus()")
        expect(self.page.locator('[data-day="5"][data-slot="18"]')).to_have_attribute("aria-pressed", "true")
        expect(self.page.locator("#timetable-summary")).to_contain_text("45.5 hours")
