from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import subprocess
import threading
import time
import unittest

from panoptix_app.capture import PlaceholderCapture
from panoptix_app.capture_notes import CaptureNotes, show_capture_note
from panoptix_app.clips import ClipRecorder
from panoptix_app.hotkeys import HotkeyService
from panoptix_app.recorder import Recorder, CaptureStateError
from panoptix_app.settings import SettingsStore
from panoptix_app.storage import SessionStore
from tests.test_hotkeys import FakeListener
from tests.test_review_regressions import NoopHook


class CaptureNoteTests(unittest.TestCase):
    def test_caption_and_context_apply_to_next_click_only(self):
        with TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp))
            recorder = Recorder(store, PlaceholderCapture(), NoopHook)
            session = recorder.start("evidence")
            recorder.notes.set("Open file", "Show how to load the project")
            first = recorder.capture_click(10, 20)
            second = recorder.capture_click(30, 40)
            recorder.stop()
            self.assertEqual(first["title"], "Open file")
            self.assertEqual(first["staff_note"], "Show how to load the project")
            self.assertEqual(second["title"], "")
            self.assertEqual(second["staff_note"], "")
            self.assertEqual(store.load_session(session["id"])["events"][0]["title"], "Open file")
            self.assertEqual(recorder.notes.status()["pending"], {})

    def test_automatic_capture_leaves_note_pending_for_manual_capture(self):
        with TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp))
            recorder = Recorder(store, PlaceholderCapture())
            recorder.start("background", settings={"interval_seconds": 60})
            recorder.notes.set(staff_note="Explain the result")
            periodic = recorder.capture_periodic()
            self.assertEqual(periodic["staff_note"], "")
            self.assertEqual(recorder.notes.status()["pending"], {"staff_note": "Explain the result"})
            manual = recorder.capture_manual_hotkey()
            recorder.stop()
            self.assertEqual(manual["staff_note"], "Explain the result")
            self.assertEqual(manual["title"], "Manual CYP capture")

    def test_failed_capture_or_write_does_not_consume_note(self):
        for failure in ("capture", "save"):
            with self.subTest(failure=failure), TemporaryDirectory() as tmp:
                store = SessionStore(Path(tmp))
                recorder = Recorder(store, PlaceholderCapture())
                recorder.start("background")
                recorder.notes.set("Open file")
                target = recorder.capture if failure == "capture" else store
                method = "capture" if failure == "capture" else "add_event"
                with patch.object(target, method, side_effect=OSError("Disk full")):
                    with self.assertRaises(OSError):
                        recorder.capture_manual_hotkey()
                self.assertEqual(recorder.notes.status()["pending"], {"title": "Open file"})
                self.assertFalse(recorder.status()["active"])
                recorder.stop()

    def test_prompt_blocks_captures_and_ignores_dialog_clicks_then_resumes(self):
        with TemporaryDirectory() as tmp:
            close_prompt = threading.Event()
            calls = []

            def prompt(initial):
                calls.append(initial)
                close_prompt.wait(timeout=3)
                return {"title": "Open file", "staff_note": "For LMS"}

            notes = CaptureNotes(prompt)
            store = SessionStore(Path(tmp))
            recorder = Recorder(store, PlaceholderCapture(), NoopHook, notes=notes)
            session = recorder.start("evidence")
            notes.open_prompt()
            notes.open_prompt()
            recorder._queue_click_capture(100, 100)
            self.assertEqual(store.load_session(session["id"])["events"], [])
            with self.assertRaises(CaptureStateError):
                recorder.capture_click(100, 100)
            self.assertTrue(recorder.status()["active"])
            close_prompt.set()
            notes._thread.join(timeout=3)
            self.assertEqual(len(calls), 1)
            self.assertFalse(notes.status()["editing"])
            event = recorder.capture_click(10, 20)
            recorder.stop()
            self.assertEqual(event["title"], "Open file")

    def test_observation_waits_for_prompt_without_stopping_recording(self):
        with TemporaryDirectory() as tmp:
            close_prompt = threading.Event()
            notes = CaptureNotes(lambda initial: close_prompt.wait(timeout=3) and None)
            notes.open_prompt()
            store = SessionStore(Path(tmp))
            recorder = Recorder(store, PlaceholderCapture(), notes=notes)
            session = recorder.start("observation", settings={"interval_seconds": 0.02})
            time.sleep(0.08)
            self.assertTrue(recorder.status()["active"])
            self.assertEqual(store.load_session(session["id"])["events"], [])
            close_prompt.set()
            notes._thread.join(timeout=3)
            time.sleep(0.08)
            recorder.stop()
            self.assertGreater(len(store.load_session(session["id"])["events"]), 0)

    def test_cancel_and_prompt_error_preserve_pending_note(self):
        for fail in (False, True):
            with self.subTest(fail=fail):
                def prompt(initial):
                    self.assertEqual(initial, {"title": "Previous"})
                    if fail:
                        raise OSError("No GUI")
                    return None
                notes = CaptureNotes(prompt)
                notes.set("Previous")
                notes.open_prompt()
                notes._thread.join(timeout=3)
                self.assertEqual(notes.status()["pending"], {"title": "Previous"})
                self.assertFalse(notes.status()["editing"])
                self.assertEqual(notes.status()["error"], "No GUI" if fail else None)

    def test_clip_gets_caption_in_manifest_and_consumes_it(self):
        with TemporaryDirectory() as tmp:
            notes = CaptureNotes()
            notes.set("Open file", "Load a project")
            clips = ClipRecorder(Path(tmp), PlaceholderCapture(), notes)
            clips.start({"clip_duration_seconds": 1, "clip_fps": 1, "clip_make_gif": False})
            clips._thread.join(timeout=3)
            manifest = json.loads((Path(clips.status()["folder"]) / "clip.json").read_text())
            self.assertEqual(manifest["title"], "Open file")
            self.assertEqual(manifest["staff_note"], "Load a project")
            self.assertEqual(notes.status()["pending"], {})

    def test_clip_failure_before_any_frame_restores_caption(self):
        with TemporaryDirectory() as tmp:
            notes = CaptureNotes()
            notes.set("Open file")
            capture = PlaceholderCapture()
            clips = ClipRecorder(Path(tmp), capture, notes)
            with patch.object(capture, "capture", side_effect=OSError("Screen unavailable")):
                clips.start({})
                clips._thread.join(timeout=3)
            self.assertEqual(notes.status()["pending"], {"title": "Open file"})

    def test_popup_and_clip_cannot_overlap(self):
        with TemporaryDirectory() as tmp:
            close_prompt = threading.Event()
            notes = CaptureNotes(lambda initial: close_prompt.wait(timeout=3) and None)
            clips = ClipRecorder(Path(tmp), PlaceholderCapture(), notes)
            notes.open_prompt(clips)
            with self.assertRaises(RuntimeError):
                clips.start({})
            close_prompt.set()
            notes._thread.join(timeout=3)
            clips.start({"clip_make_gif": False})
            self.assertIn("Finish", notes.open_prompt(clips)["error"])
            self.assertFalse(notes.status()["editing"])
            clips.close()

    def test_hotkey_opens_prompt_with_configurable_shortcut(self):
        with TemporaryDirectory() as tmp:
            settings = SettingsStore(Path(tmp))
            settings.update({"capture_note_hotkey_enabled": True, "capture_note_hotkey": "<ctrl>+<alt>+t"})
            notes = CaptureNotes(lambda initial: {"title": "Open file"})
            recorder = Recorder(SessionStore(Path(tmp)), notes=notes)
            service = HotkeyService(settings, recorder, FakeListener)
            service.start()
            service.listener.mapping["<ctrl>+<alt>+t"]()
            notes._thread.join(timeout=3)
            service.stop()
            self.assertEqual(notes.status()["pending"], {"title": "Open file"})

    def test_hotkey_validation_rejects_blank_and_equivalent_shortcuts(self):
        with TemporaryDirectory() as tmp:
            settings = SettingsStore(Path(tmp))
            for shortcut in ("", "<alt>+<ctrl>+p"):
                with self.subTest(shortcut=shortcut), self.assertRaises(ValueError):
                    settings.update({"capture_note_hotkey_enabled": True, "capture_note_hotkey": shortcut})
            with self.assertRaises(ValueError):
                settings.update({"capture_note_hotkey_enabled": True, "clip_hotkey_enabled": True, "capture_note_hotkey": "<ctrl>+<alt>+r"})

    def test_windows_prompt_passes_user_text_as_data_and_handles_cancel(self):
        text = 'Open "file"; $(anything) — café'
        for output in ('', json.dumps({"title": text, "staff_note": "Context"})):
            with self.subTest(output=output), patch("panoptix_app.capture_notes.sys.platform", "win32"), patch("panoptix_app.capture_notes.subprocess.run") as run:
                run.return_value = subprocess.CompletedProcess([], 0, stdout=output, stderr="")
                result = show_capture_note({"title": text})
                self.assertEqual(result, json.loads(output) if output else None)
                self.assertNotIn(text, run.call_args.args[0][-1])
                self.assertEqual(json.loads(run.call_args.kwargs["env"]["PANOPTIX_CAPTURE_NOTE"]), {"title": text})

    def test_invalid_note_does_not_replace_existing_one(self):
        notes = CaptureNotes()
        notes.set("Open file")
        for value in (None, 42, "x" * 201):
            with self.subTest(value=value), self.assertRaises(ValueError):
                notes.set(value)
        self.assertEqual(notes.status()["pending"], {"title": "Open file"})
        notes.set()
        self.assertEqual(notes.status()["pending"], {})
