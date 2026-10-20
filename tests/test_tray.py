from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import sys
import threading
import types
import unittest
from http.server import ThreadingHTTPServer

from panoptix import send_action
from panoptix_app.capture import PlaceholderCapture
from panoptix_app.recorder import Recorder
from panoptix_app.server import create_handler, run_server
from panoptix_app.storage import SessionStore
from panoptix_app.tray import request_shutdown, start_tray, stop_tray


class TrayTests(unittest.TestCase):
    def test_quit_callback_returns_and_shutdown_runs_on_another_thread(self):
        icons = []
        class Icon:
            def __init__(self, *args, **kwargs):
                self.menu = kwargs['menu']
                self.ready = threading.Event()
                self.stopped = threading.Event()
                self.visible = True
                icons.append(self)
            def run(self):
                self.ready.set()
                self.stopped.wait(timeout=3)
            def stop(self):
                self.stopped.set()
        module = types.SimpleNamespace(Icon=Icon, Menu=lambda *items: items, MenuItem=lambda label, action, **kwargs: (label, action))
        shutdown_called = threading.Event()
        release = threading.Event()
        class Server:
            def shutdown(self):
                shutdown_called.set()
                release.wait(timeout=3)
        with patch.dict(sys.modules, {'pystray': module}), patch('panoptix_app.tray.sys.platform', 'win32'):
            icon = start_tray('http://127.0.0.1:8765', object(), object(), Server())
            self.assertTrue(icon.ready.wait(timeout=1))
            quit_action = dict(icon.menu)['Quit Panoptix']
            quit_action(icon)
            self.assertTrue(shutdown_called.wait(timeout=1))
            self.assertFalse(icon.stopped.is_set())
            stop_tray(icon)
            release.set()
            self.assertFalse(icon.visible)
            self.assertTrue(icon.stopped.is_set())

    def test_tray_hide_failure_does_not_prevent_stop(self):
        stopped = threading.Event()
        class Icon:
            @property
            def visible(self):
                return True
            @visible.setter
            def visible(self, value):
                raise RuntimeError('tray disconnected')
            def stop(self):
                stopped.set()
        with self.assertLogs(level='ERROR'):
            stop_tray(Icon())
        self.assertTrue(stopped.is_set())

    def test_unresponsive_tray_does_not_block_quitting(self):
        release = threading.Event()
        class Icon:
            visible = True
            def stop(self):
                release.wait(timeout=3)
        with self.assertLogs(level='WARNING'):
            stop_tray(Icon(), timeout=0.02)
        release.set()

    def test_quit_request_is_idempotent(self):
        calls = []
        done = threading.Event()
        class Server:
            def shutdown(self):
                calls.append(1)
                done.set()
        server = Server()
        request_shutdown(server)
        request_shutdown(server)
        self.assertTrue(done.wait(timeout=1))
        self.assertEqual(calls, [1])

    def test_cli_quit_stops_serving_and_preserves_saved_session(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SessionStore(root)
            recorder = Recorder(store, PlaceholderCapture())
            session = recorder.start('observation', settings={'interval_seconds': 60})
            recorder.capture_periodic()
            server = ThreadingHTTPServer(('127.0.0.1', 0), create_handler(root, store, recorder))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                send_action('quit', port=server.server_port)
                thread.join(timeout=2)
                self.assertFalse(thread.is_alive())
                self.assertEqual(len(store.load_session(session['id'])['events']), 1)
            finally:
                recorder.stop()
                server.shutdown()
                server.server_close()

    def test_failed_tray_cleanup_does_not_skip_capture_or_server_cleanup(self):
        with TemporaryDirectory() as tmp:
            callbacks = []
            class Component:
                def start(self):
                    pass
                def stop(self):
                    callbacks.append('stop')
                def close(self):
                    callbacks.append('close')
            class FakeServer:
                server_address = ('127.0.0.1', 8765)
                def __init__(self, *args):
                    pass
                def serve_forever(self):
                    pass
                def server_close(self):
                    callbacks.append('server_close')
            class BrokenIcon:
                @property
                def visible(self):
                    return True
                @visible.setter
                def visible(self, value):
                    raise RuntimeError('gone')
                def stop(self):
                    raise RuntimeError('gone')
            with patch('panoptix_app.server.start_tray', return_value=BrokenIcon()), patch('panoptix_app.server.BackgroundScheduler', return_value=Component()), patch('panoptix_app.server.HotkeyService', return_value=Component()), patch('panoptix_app.server.Recorder', return_value=Component()), patch('panoptix_app.server.ClipRecorder', return_value=Component()), patch('panoptix_app.server.StartupManager') as startup, patch('panoptix_app.server.create_handler'), patch('panoptix_app.server.ThreadingHTTPServer', FakeServer), self.assertLogs(level='ERROR'):
                recorder = Component()
                recorder.notes = object()
                with patch('panoptix_app.server.Recorder', return_value=recorder):
                    run_server(Path(tmp))
            self.assertEqual(callbacks, ['stop', 'stop', 'stop', 'close', 'server_close'])
