from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from http.server import ThreadingHTTPServer
import json
import os
import subprocess
import threading
import unittest
from urllib.request import urlopen

from panoptix import send_action
from panoptix_app.app_paths import default_data_root
from panoptix_app.app_config import get_config_dir
from panoptix_app.capture import ScreenCapture, PlaceholderCapture
from panoptix_app.capture_notes import show_capture_note
from panoptix_app.desktop import is_wayland
from panoptix_app.recorder import Recorder
from panoptix_app.server import create_handler
from panoptix_app.startup import StartupManager
from panoptix_app.storage import SessionStore
from tests.test_review_regressions import NoopHook


class LinuxTests(unittest.TestCase):
    def test_detects_plasma_wayland_behind_xwayland(self):
        with patch('sys.platform', 'linux'), patch.dict(os.environ, {'XDG_SESSION_TYPE': 'x11', 'DESKTOP_SESSION': '/usr/share/wayland-sessions/plasma.desktop'}, clear=True):
            self.assertTrue(is_wayland())
        with patch('sys.platform', 'linux'), patch.dict(os.environ, {'XDG_SESSION_TYPE': 'x11'}, clear=True):
            self.assertFalse(is_wayland())

    def test_frozen_linux_paths_are_persistent_xdg_locations(self):
        with TemporaryDirectory() as tmp, patch('sys.platform', 'linux'), patch.dict(os.environ, {'XDG_DATA_HOME': tmp + '/data', 'XDG_CONFIG_HOME': tmp + '/config'}, clear=True), patch('sys.frozen', True, create=True):
            self.assertEqual(default_data_root(), Path(tmp) / 'data/panoptix')
            self.assertEqual(get_config_dir(), Path(tmp) / 'config/panoptix')

    def test_native_wayland_capture_uses_scaled_spectacle_output(self):
        with TemporaryDirectory() as tmp, patch('panoptix_app.capture.is_wayland', return_value=True), patch('panoptix_app.capture.is_kde', return_value=True), patch('panoptix_app.capture.shutil.which', return_value='/usr/bin/spectacle'), patch('panoptix_app.capture.subprocess.run') as run:
            def shot(args, **kwargs):
                PlaceholderCapture().capture(Path(tmp), '001.png')
                return subprocess.CompletedProcess(args, 0, stdout='', stderr='')
            run.side_effect = shot
            path = ScreenCapture().capture(Path(tmp), '001.png')
            self.assertTrue(path.is_file())
            args = run.call_args.args[0]
            self.assertIn('--scaled', args)
            self.assertIn('--nonotify', args)
            self.assertEqual(args[-1], str(path))

    def test_missing_wayland_backend_reports_error_instead_of_placeholder(self):
        with patch('panoptix_app.capture.is_wayland', return_value=True), patch('panoptix_app.capture.is_kde', return_value=True), patch('panoptix_app.capture.shutil.which', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'spectacle'):
                ScreenCapture().capture(Path('/tmp'), 'missing.png')

    def test_kde_caption_dialogs_pass_text_as_arguments_and_support_cancel(self):
        text = 'Open file $(literal) — café'
        with patch('sys.platform', 'linux'), patch('panoptix_app.capture_notes.shutil.which', return_value='/usr/bin/kdialog'), patch('panoptix_app.capture_notes.subprocess.run') as run:
            run.side_effect = [subprocess.CompletedProcess([], 0, text + '\n', ''), subprocess.CompletedProcess([], 0, 'Line 1\nLine 2\n', '')]
            result = show_capture_note({'title': text, 'staff_note': ''})
            self.assertEqual(result, {'title': text, 'staff_note': 'Line 1\nLine 2'})
            self.assertEqual(run.call_args_list[0].args[0][-1], text)
            run.side_effect = [subprocess.CompletedProcess([], 0, 'new title\n', ''), subprocess.CompletedProcess([], 1, '', '')]
            self.assertIsNone(show_capture_note({}))

    def test_linux_autostart_uses_desktop_entry(self):
        with TemporaryDirectory() as tmp, patch('sys.platform', 'linux'), patch('sys.frozen', True, create=True):
            manager = StartupManager(Path(tmp), Path('/opt/Panoptix/panoptix'))
            manager.set_enabled(True)
            self.assertEqual(manager.shortcut_path.name, 'panoptix.desktop')
            self.assertIn('Exec="/opt/Panoptix/panoptix" --background', manager.shortcut_path.read_text())
            self.assertNotIn('start ""', manager.shortcut_path.read_text())
            manager.set_enabled(False)
            self.assertFalse(manager.is_enabled())

    def test_cli_manual_capture_and_kwin_bridge_scaled_coordinates(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SessionStore(root)
            recorder = Recorder(store, PlaceholderCapture(), NoopHook)
            handler = create_handler(root, store, recorder)
            server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            session = recorder.start('evidence')
            base = f'http://127.0.0.1:{server.server_port}'
            try:
                recorder.notes.set('Open file', 'LMS context')
                send_action('capture', port=server.server_port)
                event = store.load_session(session['id'])['events'][0]
                self.assertEqual(event['title'], 'Open file')
                with urlopen(base + '/api/desktop/kwin') as response:
                    self.assertTrue(json.load(response)['active'])
                from urllib.request import Request
                payload = {'session_id': session['id'], 'x': 0, 'y': 100, 'desktop_geometry': {'left': -500, 'top': 0, 'width': 1000, 'height': 500}}
                request = Request(base + '/api/desktop/kwin-click', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
                with urlopen(request) as response:
                    self.assertTrue(json.load(response)['ok'])
                recorder.stop()
                event = store.load_session(session['id'])['events'][1]
                self.assertEqual((event['x'], event['y']), (160, 36))
                self.assertEqual((event['screen_x'], event['screen_y']), (0, 100))
            finally:
                recorder.stop()
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
