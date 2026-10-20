from pathlib import Path
from tempfile import TemporaryDirectory
import json
import threading
import time
import unittest

from panoptix_app.capture import PlaceholderCapture
from panoptix_app.clips import ClipRecorder
from panoptix_app.exporter import HtmlExporter
from panoptix_app.recorder import Recorder, CaptureStateError
from panoptix_app.server import DataContext
from panoptix_app.storage import SessionStore
from tests.test_hooks import HookFactory


class LmsTests(unittest.TestCase):
    def test_manual_lesson_stores_context_and_caption_in_review_and_export(self):
        with TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp))
            hooks = HookFactory()
            recorder = Recorder(store, PlaceholderCapture(), hooks)
            session = recorder.start('lms', {'activity': 'Opening a project', 'course': 'Desktop basics', 'learning_context': 'Learn how to locate and open an existing project'})
            self.assertEqual(hooks.hooks, [])
            self.assertFalse(recorder.status()['click_capture_enabled'])
            with self.assertRaises(CaptureStateError):
                recorder.capture_periodic()
            self.assertTrue(recorder.status()['active'])
            recorder.notes.set('Open file', 'Choose File → Open')
            event = recorder.capture_manual_hotkey()
            recorder.stop()
            self.assertEqual(event['type'], 'lms_screenshot')
            self.assertEqual(event['title'], 'Open file')
            self.assertEqual(event['staff_note'], 'Choose File → Open')
            loaded = store.load_session(session['id'])
            self.assertEqual(loaded['mode'], 'lms')
            output = HtmlExporter(Path(tmp)).export(session['id']).read_text()
            for value in ('Desktop basics', 'Opening a project', 'Learn how to locate', 'Open file'):
                self.assertIn(value, output)

    def test_click_capture_is_optional_in_lms_mode(self):
        with TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp))
            hooks = HookFactory()
            recorder = Recorder(store, PlaceholderCapture(), hooks)
            session = recorder.start('lms', settings={'capture_clicks': True})
            recorder.notes.set('Open file')
            hooks.hooks[0].emit_click(30, 40)
            recorder.stop()
            events = store.load_session(session['id'])['events']
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]['type'], 'click')
            self.assertEqual(events[0]['title'], 'Open file')
            self.assertEqual((events[0]['x'], events[0]['y']), (30, 40))

    def test_lesson_clip_uses_lesson_settings_and_groups_originals(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SessionStore(root)
            recorder = Recorder(store, PlaceholderCapture())
            clips = ClipRecorder(root, PlaceholderCapture())
            DataContext(root, store, recorder, clips=clips)
            session = recorder.start('lms', {'course': 'Desktop basics', 'activity': 'Opening files'}, {'clip_duration_seconds': 1, 'clip_fps': 2, 'clip_make_gif': False})
            recorder.notes.set('Open file', 'Demonstrate the file picker')
            result = clips.start({'clip_duration_seconds': 30, 'clip_fps': 5, 'clip_make_gif': True})
            clips._thread.join(timeout=5)
            recorder.stop()
            folder = Path(result['folder'])
            manifest = json.loads((folder / 'clip.json').read_text())
            self.assertEqual(folder.parent, root / 'clips' / session['id'])
            self.assertEqual(manifest['session_id'], session['id'])
            self.assertEqual(manifest['metadata']['activity'], 'Opening files')
            self.assertEqual(manifest['title'], 'Open file')
            self.assertEqual(manifest['requested_fps'], 2)
            self.assertEqual(manifest['requested_duration_seconds'], 1)
            self.assertEqual(len(list((folder / 'frames').glob('*.png'))), 2)
            self.assertFalse((folder / 'clip.gif').exists())
            self.assertEqual(recorder.notes.status()['pending'], {})

    def test_pausing_or_stopping_lesson_finishes_its_clip(self):
        for action in ('pause', 'stop'):
            with self.subTest(action=action), TemporaryDirectory() as tmp:
                root = Path(tmp)
                store = SessionStore(root)
                recorder = Recorder(store, PlaceholderCapture())
                captured = threading.Event()
                class Capture(PlaceholderCapture):
                    def capture(self, *args, **kwargs):
                        result = super().capture(*args, **kwargs)
                        captured.set()
                        return result
                clips = ClipRecorder(root, Capture())
                DataContext(root, store, recorder, clips=clips)
                recorder.start('lms', settings={'clip_duration_seconds': 30})
                clips.start({})
                self.assertTrue(captured.wait(timeout=3))
                getattr(recorder, action)()
                clips._thread.join(timeout=3)
                self.assertFalse(clips.status()['active'])
                self.assertIsNone(clips.status()['error'])
                if action == 'pause':
                    with self.assertRaises(CaptureStateError):
                        clips.start({})
                    recorder.resume()
                    recorder.capture_manual_hotkey()
                recorder.stop()

    def test_invalid_lesson_clip_settings_do_not_create_session(self):
        with TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp))
            recorder = Recorder(store, PlaceholderCapture())
            for settings in ({'clip_fps': 0}, {'clip_duration_seconds': 121}):
                with self.subTest(settings=settings), self.assertRaises(ValueError):
                    recorder.start('lms', settings=settings)
            self.assertEqual(store.list_sessions(), [])
