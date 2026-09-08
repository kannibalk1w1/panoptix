from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from panoptix_app.capture import PlaceholderCapture
from panoptix_app.persistence import write_json
from panoptix_app.retention import cleanup_old_sessions, preview_cleanup
from panoptix_app.storage import SessionStore


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
