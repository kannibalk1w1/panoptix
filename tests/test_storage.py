from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panoptix_app.storage import SessionStore


class SessionStoreTests(unittest.TestCase):
    def test_create_evidence_session_writes_json(self):
        with TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp))
            session = store.create_session(
                mode="evidence",
                metadata={"cyp": "AB", "activity": "Scratch game"},
                settings={},
            )

            loaded = store.load_session(session["id"])

            self.assertEqual(loaded["mode"], "evidence")
            self.assertEqual(loaded["metadata"]["cyp"], "AB")
            self.assertEqual(loaded["events"], [])
            self.assertTrue((Path(tmp) / "sessions" / session["id"] / "session.json").exists())

    def test_add_event_persists_click_coordinates(self):
        with TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp))
            session = store.create_session("evidence", {}, {})

            updated = store.add_event(
                session["id"],
                {
                    "type": "click",
                    "timestamp": "2026-05-28T10:00:00",
                    "screenshot": "001.png",
                    "x": 100,
                    "y": 200,
                    "title": "",
                    "staff_note": "",
                    "cyp_quote": "",
                    "tags": [],
                },
            )

            self.assertEqual(updated["events"][0]["index"], 1)
            self.assertEqual(updated["events"][0]["x"], 100)

    def test_list_sessions_returns_newest_first(self):
        with TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp))
            first = store.create_session("evidence", {"activity": "First"}, {})
            second = store.create_session("observation", {"activity": "Second"}, {})

            sessions = store.list_sessions()

            self.assertEqual([item["id"] for item in sessions], [second["id"], first["id"]])

    def test_update_event_edits_notes_tags_and_highlight(self):
        with TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp))
            session = store.create_session("observation", {}, {})
            store.add_event(
                session["id"],
                {
                    "type": "periodic",
                    "timestamp": "2026-05-28T10:00:00",
                    "screenshot": "001.png",
                    "title": "",
                    "staff_note": "",
                    "highlight": False,
                },
            )

            updated = store.update_event(
                session["id"],
                1,
                {
                    "title": "Good progress",
                    "staff_note": "Stayed focused on the task.",
                    "tags": ["project progress", "independent work"],
                    "highlight": True,
                },
            )

            event = updated["events"][0]
            self.assertEqual(event["title"], "Good progress")
            self.assertEqual(event["staff_note"], "Stayed focused on the task.")
            self.assertEqual(event["tags"], ["project progress", "independent work"])
            self.assertTrue(event["highlight"])

    def test_delete_event_removes_event_and_reindexes_remaining(self):
        with TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp))
            session = store.create_session("evidence", {}, {})
            store.add_event(session["id"], {"type": "click", "timestamp": "one", "screenshot": "001.png"})
            store.add_event(session["id"], {"type": "click", "timestamp": "two", "screenshot": "002.png"})

            updated = store.delete_event(session["id"], 1)

            self.assertEqual(len(updated["events"]), 1)
            self.assertEqual(updated["events"][0]["index"], 1)
            self.assertEqual(updated["events"][0]["timestamp"], "two")


if __name__ == "__main__":
    unittest.main()
