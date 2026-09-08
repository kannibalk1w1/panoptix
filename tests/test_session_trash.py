from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from panoptix_app.capture import PlaceholderCapture
from panoptix_app.persistence import write_json
from panoptix_app.retention import cleanup_old_sessions, preview_cleanup
from panoptix_app.storage import SessionStore
from panoptix_app.storage_usage import get_storage_usage


class SessionTrashTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = SessionStore(self.root)

    def session(self, title="Recover me", started="2020-01-01T10:00:00"):
        session = self.store.create_session("evidence", {"activity": title})
        session["started"] = started
        write_json(self.store.sessions_dir / session["id"] / "session.json", session)
        image = PlaceholderCapture().capture(self.store.screenshot_dir(session["id"]), "001.png")
        self.store.add_event(session["id"], {"screenshot": image.name, "staff_note": "Original note"})
        return session["id"]

    def test_delete_restore_preserves_images_notes_and_local_exports(self):
        sid = self.session()
        image = (self.store.screenshot_dir(sid) / "001.png").read_bytes()
        exports = self.store.exports_dir / sid
        exports.mkdir()
        (exports / "report.html").write_text("saved export")
        self.store.delete_session(sid)
        self.assertEqual(self.store.list_sessions(), [])
        trash = self.store.list_trash()
        self.assertEqual(trash[0]["session_id"], sid)
        self.assertFalse(exports.exists())
        restored = self.store.restore_session(trash[0]["trash_id"])
        self.assertEqual(restored["events"][0]["staff_note"], "Original note")
        self.assertEqual((self.store.screenshot_dir(sid) / "001.png").read_bytes(), image)
        self.assertEqual((exports / "report.html").read_text(), "saved export")
        self.assertEqual(self.store.list_trash(), [])

    def test_restore_never_overwrites_conflicting_session(self):
        sid = self.session()
        self.store.delete_session(sid)
        entry = self.store.list_trash()[0]
        (self.store.sessions_dir / sid).mkdir()
        with self.assertRaisesRegex(ValueError, "overwrite"):
            self.store.restore_session(entry["trash_id"])
        self.assertEqual(len(self.store.list_trash()), 1)

    def test_failed_move_rolls_session_back(self):
        sid = self.session()
        exports = self.store.exports_dir / sid
        exports.mkdir()
        rename = Path.rename

        def fail_export(path, target):
            if path == exports:
                raise OSError("Share unavailable")
            return rename(path, target)

        with patch.object(Path, "rename", fail_export):
            with self.assertRaises(OSError):
                self.store.delete_session(sid)
        self.assertEqual(self.store.load_session(sid)["events"][0]["staff_note"], "Original note")
        self.assertEqual(self.store.list_trash(), [])

    def test_preview_is_read_only_and_cleanup_uses_only_previewed_ids(self):
        sid = self.session()
        preview = preview_cleanup(self.store, 30, datetime(2026, 9, 8))
        self.assertEqual([session["id"] for session in preview["sessions"]], [sid])
        self.assertEqual(self.store.list_trash(), [])
        later = self.session("Added after preview")
        result = cleanup_old_sessions(self.store, 30, datetime(2026, 9, 8), session_ids=[sid])
        self.assertEqual(result["deleted"], [sid])
        self.assertTrue(self.store.load_session(later))
        self.assertEqual(len(self.store.list_trash()), 1)

    def test_invalid_restore_paths_are_rejected(self):
        for value in ("..", "../sessions", "not-a-trash-id"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.store.restore_session(value)

    def test_folders_panoptix_did_not_write_never_block_the_trash_or_new_sessions(self):
        sid = self.session()
        self.store.delete_session(sid)
        stray = self.root / "trash" / "b7cc1aca6525457fbea11f416c025e50 (conflicted copy)"
        stray.mkdir(parents=True)
        (stray / "entry.json").write_text("{}")
        unreadable = self.root / "trash" / ("0" * 32)
        unreadable.mkdir()
        (unreadable / "entry.json").write_text("not json", encoding="utf-8")

        self.assertEqual([entry["session_id"] for entry in self.store.list_trash()], [sid])
        self.assertTrue(self.store.create_session("evidence", {"activity": "Still works"}))
        self.assertTrue(stray.exists())

    def test_corrupt_session_can_still_be_deleted_and_restored(self):
        sid = self.session()
        (self.store.sessions_dir / sid / "session.json").write_text("{ truncated", encoding="utf-8")

        self.store.delete_session(sid)

        entry = self.store.list_trash()[0]
        self.assertEqual(entry["session_id"], sid)
        self.assertEqual(entry["title"], sid)
        self.assertFalse((self.store.sessions_dir / sid).exists())
        restored = self.store.restore_session(entry["trash_id"])
        self.assertEqual(restored, {"id": sid, "unreadable": True})
        self.assertTrue((self.store.screenshot_dir(sid) / "001.png").exists())
        self.assertEqual(self.store.list_trash(), [])

    def test_session_without_its_json_is_removable_and_purgeable_but_not_restorable(self):
        sid = self.session()
        (self.store.sessions_dir / sid / "session.json").unlink()

        self.store.delete_session(sid)

        entry = self.store.list_trash()[0]
        self.assertFalse(entry["restorable"])
        with self.assertRaisesRegex(FileNotFoundError, "incomplete"):
            self.store.restore_session(entry["trash_id"])
        self.assertEqual(self.store.purge_trash(entry["trash_id"])["session_id"], sid)
        self.assertEqual(self.store.list_trash(), [])

    def test_deleting_a_missing_session_reports_it_instead_of_creating_an_empty_entry(self):
        with self.assertRaises(FileNotFoundError):
            self.store.delete_session("2020-01-01_10-00-00_evidence")
        self.assertEqual(self.store.list_trash(), [])

    def test_purging_frees_disk_space_and_empty_trash_clears_everything(self):
        first, second = self.session("First"), self.session("Second")
        self.store.delete_session(first)
        self.store.delete_session(second)
        self.assertEqual(get_storage_usage(self.root, 1)["trash_count"], 2)

        self.store.purge_trash(self.store.list_trash()[0]["trash_id"])
        self.assertEqual(len(self.store.list_trash()), 1)

        self.assertEqual(len(self.store.empty_trash()), 1)
        usage = get_storage_usage(self.root, 1)
        self.assertEqual(usage["trash_bytes"], 0)
        self.assertEqual(usage["trash_count"], 0)

    def test_retention_cleanup_purges_deleted_sessions_past_the_retention_period(self):
        expired, recent = self.session("Expired"), self.session("Recent")
        self.store.delete_session(expired)
        self.store.delete_session(recent)
        entries = {entry["session_id"]: entry for entry in self.store.list_trash()}
        write_json(
            self.root / "trash" / entries[expired]["trash_id"] / "entry.json",
            {**entries[expired], "deleted_at": "2020-01-05T10:00:00"},
        )

        preview = preview_cleanup(self.store, 30, datetime(2026, 9, 8))
        self.assertEqual([entry["session_id"] for entry in preview["expired_trash"]], [expired])
        self.assertEqual(len(self.store.list_trash()), 2)

        result = cleanup_old_sessions(self.store, 30, datetime(2026, 9, 8), session_ids=[])
        self.assertEqual(result["purged"], [expired])
        self.assertEqual([entry["session_id"] for entry in self.store.list_trash()], [recent])

    def test_undated_deleted_sessions_are_never_purged_automatically(self):
        sid = self.session()
        self.store.delete_session(sid)
        entry = self.store.list_trash()[0]
        write_json(self.root / "trash" / entry["trash_id"] / "entry.json", {"session_id": sid, "title": sid})

        result = cleanup_old_sessions(self.store, 30, datetime(2026, 9, 8), session_ids=[])

        self.assertEqual(result["purged"], [])
        self.assertEqual(len(self.store.list_trash()), 1)
