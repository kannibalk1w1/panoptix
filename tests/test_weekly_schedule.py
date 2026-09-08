from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from panoptix_app.background import BackgroundScheduler
from panoptix_app.capture import PlaceholderCapture
from panoptix_app.recorder import Recorder
from panoptix_app.schedule import active_schedule_window, daily_window_is_active, timetable_for_editor
from panoptix_app.settings import SettingsStore
from panoptix_app.storage import SessionStore


def empty_week():
    return [[False] * 48 for _ in range(7)]


class WeeklyScheduleTests(unittest.TestCase):
    def test_weekdays_and_half_hour_boundaries(self):
        week = empty_week()
        week[0][18] = True
        week[2][27] = True
        settings = {"background_weekly_schedule": week}
        for value, expected in ((datetime(2026, 9, 7, 8, 59, 59), False), (datetime(2026, 9, 7, 9), True), (datetime(2026, 9, 7, 9, 29, 59), True), (datetime(2026, 9, 7, 9, 30), False), (datetime(2026, 9, 8, 9), False), (datetime(2026, 9, 9, 13, 30), True), (datetime(2026, 9, 9, 14), False)):
            with self.subTest(value=value):
                self.assertEqual(daily_window_is_active(settings, value), expected)

    def test_adjacent_and_overnight_slots_share_a_block(self):
        week = empty_week()
        week[6][47] = week[0][0] = week[0][1] = True
        settings = {"background_weekly_schedule": week}
        first = active_schedule_window(settings, datetime(2026, 9, 6, 23, 45))
        self.assertEqual(first, active_schedule_window(settings, datetime(2026, 9, 7, 0, 45)))
        self.assertIsNone(active_schedule_window(settings, datetime(2026, 9, 7, 1)))
        self.assertNotEqual(first, active_schedule_window(settings, datetime(2026, 9, 13, 23, 45)))

    def test_empty_and_full_week(self):
        self.assertIsNone(active_schedule_window({"background_weekly_schedule": empty_week()}))
        self.assertEqual(active_schedule_window({"background_weekly_schedule": [[True] * 48 for _ in range(7)]}), "weekly-continuous")

    def test_legacy_times_remain_exact_until_weekly_schedule_saved(self):
        settings = {"background_start_time": "09:10", "background_end_time": "15:10"}
        self.assertFalse(daily_window_is_active(settings, datetime(2026, 9, 7, 9, 5)))
        week = timetable_for_editor(settings)
        self.assertTrue(week[0][18])
        self.assertTrue(week[0][30])
        self.assertFalse(week[0][31])
        week[0][18] = False
        self.assertTrue(week[1][18])

    def test_saved_timetable_round_trips_and_rejects_invalid_shapes(self):
        with TemporaryDirectory() as tmp:
            store = SettingsStore(Path(tmp))
            week = empty_week()
            week[4][47] = True
            store.update({"background_weekly_schedule": week})
            self.assertEqual(SettingsStore(Path(tmp)).load()["background_weekly_schedule"], week)
            for invalid in ([], [[False] * 47 for _ in range(7)], [[1] * 48 for _ in range(7)], "Monday"):
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    store.update({"background_weekly_schedule": invalid})
            self.assertEqual(store.load()["background_weekly_schedule"], week)

    def test_scheduler_preserves_adjacent_slots_and_resumes_after_gap(self):
        with TemporaryDirectory() as tmp:
            settings = SettingsStore(Path(tmp))
            week = empty_week()
            week[0][18] = week[0][19] = week[0][22] = True
            settings.update({"background_enabled": True, "background_weekly_schedule": week, "background_interval_seconds": 3600})
            recorder = Recorder(SessionStore(Path(tmp)), PlaceholderCapture())
            scheduler = BackgroundScheduler(recorder, settings)
            try:
                scheduler.evaluate(datetime(2026, 9, 7, 9))
                first = recorder.active_session_id
                scheduler.evaluate(datetime(2026, 9, 7, 9, 30))
                self.assertEqual(recorder.active_session_id, first)
                recorder.stop()
                scheduler.evaluate(datetime(2026, 9, 7, 9, 45))
                self.assertIsNone(recorder.active_session_id)
                scheduler.evaluate(datetime(2026, 9, 7, 11))
                self.assertIsNotNone(recorder.active_session_id)
                scheduler.evaluate(datetime(2026, 9, 7, 11, 30))
                self.assertIsNone(recorder.active_session_id)
            finally:
                recorder.stop()

    def test_missed_gap_starts_a_new_session(self):
        with TemporaryDirectory() as tmp:
            settings = SettingsStore(Path(tmp))
            week = empty_week()
            week[0][18] = week[0][22] = True
            settings.update({"background_enabled": True, "background_weekly_schedule": week, "background_interval_seconds": 3600})
            recorder = Recorder(SessionStore(Path(tmp)), PlaceholderCapture())
            scheduler = BackgroundScheduler(recorder, settings)
            try:
                scheduler.evaluate(datetime(2026, 9, 7, 9))
                first = recorder.active_session_id
                scheduler.evaluate(datetime(2026, 9, 7, 11))
                self.assertNotEqual(recorder.active_session_id, first)
                self.assertIsNotNone(recorder.store.load_session(first)["stopped"])
            finally:
                recorder.stop()
