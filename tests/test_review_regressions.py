from datetime import datetime
from http.server import ThreadingHTTPServer
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zipfile import ZipFile

from PIL import Image
from fpdf import FPDF

import panoptix
from panoptix_app.annotation import update_event_marker
from panoptix_app.background import BackgroundScheduler
from panoptix_app.capture import PlaceholderCapture
from panoptix_app.exporter import EvidencePackExporter, EvidencePackVerifier, ImageZipExporter, PdfExporter
from panoptix_app.persistence import write_json
from panoptix_app.recorder import Recorder
from panoptix_app.redaction import redact_event_screenshot
from panoptix_app.retention import cleanup_old_sessions
from panoptix_app.server import create_handler
from panoptix_app.settings import SettingsStore
from panoptix_app.startup import StartupManager
from panoptix_app.storage import SessionStore


class NoopHook:
    def __init__(self, callback):
        self.callback = callback

    def start(self):
        pass

    def stop(self):
        pass


class ChangingCapture(PlaceholderCapture):
    count = 0

    def capture(self, directory, filename):
        path = super().capture(directory, filename)
        self.count += 1
        Image.new("RGB", (100, 100), (self.count * 30, 100, 100)).save(path)
        return path


class ReviewRegressionTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(prefix="panoptix-regression-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = SessionStore(self.root)
        self.recorder = Recorder(self.store, ChangingCapture(), NoopHook)
        self.addCleanup(self.recorder.stop)

    def evidence(self):
        session = self.recorder.start("evidence")
        self.recorder.capture_click(60, 60)
        self.recorder.stop()
        return session["id"]

    def test_dot_segments_cannot_reach_recursive_deletion(self):
        for session_id in (".", "..", "../other", "..\\other"):
            with self.subTest(session_id=session_id), patch("panoptix_app.storage.shutil.rmtree") as remove:
                with self.assertRaises(ValueError):
                    self.store.delete_session(session_id)
                remove.assert_not_called()

    def test_symlink_session_cannot_delete_external_data(self):
        external = self.root / "outside"
        external.mkdir()
        link = self.store.sessions_dir / "linked"
        try:
            link.symlink_to(external, target_is_directory=True)
        except OSError:
            self.skipTest("Symlinks are unavailable for this Windows user")
        with patch("panoptix_app.storage.shutil.rmtree") as remove:
            with self.assertRaises(ValueError):
                self.store.delete_session("linked")
            remove.assert_not_called()

    def test_delete_during_capture_does_not_reuse_screenshot(self):
        sid = self.recorder.start("evidence")["id"]
        for _ in range(3):
            self.recorder.capture_click(60, 60)
        old_image = (self.store.screenshot_dir(sid) / "003.png").read_bytes()
        self.store.delete_event(sid, 1)
        new = self.recorder.capture_click(60, 60)
        self.assertEqual(new["screenshot"], "004.png")
        self.assertEqual((self.store.screenshot_dir(sid) / "003.png").read_bytes(), old_image)
        self.assertEqual(len({e["screenshot"] for e in self.store.load_session(sid)["events"]}), 3)

    def test_marker_keeps_redactions_and_original_pixels(self):
        sid = self.evidence()
        original = (self.store.screenshot_dir(sid) / "originals/001.png").read_bytes()
        redact_event_screenshot(self.store, sid, 1, preset="top_strip")
        result = update_event_marker(self.store, sid, 1, {"shape": "square"})
        with Image.open(self.store.screenshot_dir(sid) / "001.png") as image:
            self.assertEqual(image.getpixel((5, 5)), (0, 0, 0))
        self.assertEqual(len(result["event"]["redactions"]), 1)
        self.assertEqual((self.store.screenshot_dir(sid) / "originals/001.png").read_bytes(), original)

    def test_pack_redactions_are_safe_by_default_and_originals_are_explicit(self):
        sid = self.evidence()
        redact_event_screenshot(self.store, sid, 1, preset="top_strip")
        exporter = EvidencePackExporter(self.root)
        with ZipFile(exporter.export(sid)) as archive:
            self.assertFalse(any(name.endswith("_original.png") for name in archive.namelist()))
            png = next(name for name in archive.namelist() if name.endswith("_annotated.png"))
            with Image.open(BytesIO(archive.read(png))) as image:
                self.assertEqual(image.getpixel((5, 5)), (0, 0, 0))
        with ZipFile(exporter.export(sid, include_originals=True)) as archive:
            png = next(name for name in archive.namelist() if name.endswith("_original.png"))
            with Image.open(BytesIO(archive.read(png))) as image:
                self.assertNotEqual(image.getpixel((5, 5)), (0, 0, 0))
        self.assertTrue(EvidencePackVerifier(self.root).verify(sid)["ok"])

    def test_selected_image_metadata_excludes_private_notes(self):
        sid = self.evidence()
        self.store.add_event(sid, {"screenshot": "missing.png", "staff_note": "PRIVATE EXCLUDED NOTE", "selected_for_export": False})
        with ZipFile(ImageZipExporter(self.root).export(sid)) as archive:
            self.assertNotIn("PRIVATE EXCLUDED NOTE", archive.read("metadata.json").decode())

    def test_empty_or_incomplete_pack_fails_verification(self):
        sid = self.evidence()
        pack = EvidencePackExporter(self.root).export(sid)
        with ZipFile(pack) as archive:
            manifest = json.loads(archive.read("manifest.json"))
        for invalid in ({}, [], {**manifest, "files": []}):
            with self.subTest(manifest=invalid), ZipFile(pack, "w") as archive:
                archive.writestr("manifest.json", json.dumps(invalid))
            self.assertFalse(EvidencePackVerifier(self.root).verify(sid)["ok"])

    def test_pdf_metadata_stays_inside_page(self):
        pdf = FPDF()
        positions = []
        original = pdf.multi_cell

        def record(width, height, text, **kwargs):
            positions.append((pdf.get_x(), width, text))
            return original(width, height, text, **kwargs)

        with patch.object(pdf, "multi_cell", side_effect=record):
            PdfExporter(self.root)._add_summary_page(pdf, {
                "metadata": {"cyp": "AB", "activity": "Maths", "staff": "Teacher", "purpose": "Evidence"},
                "mode": "evidence", "started": "today",
            }, "Maths")
        for x, width, text in positions:
            self.assertLessEqual(x + width, pdf.w - pdf.r_margin + 0.01, text)

    def test_concurrent_processes_keep_every_event(self):
        sid = self.store.create_session("evidence")["id"]
        code = """
import sys, time
from pathlib import Path
from panoptix_app.storage import SessionStore
store = SessionStore(Path(sys.argv[1]))
original = store.load_session
def slow_load(sid):
    session = original(sid)
    time.sleep(0.01)
    return session
store.load_session = slow_load
for i in range(10):
    name = store.next_screenshot_name(sys.argv[2])
    store.add_event(sys.argv[2], {'screenshot': name})
"""
        children = [subprocess.Popen([sys.executable, "-c", code, str(self.root), sid], stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
        try:
            for child in children:
                _, error = child.communicate(timeout=30)
                self.assertEqual(child.returncode, 0, error.decode())
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                    child.communicate()
        events = self.store.load_session(sid)["events"]
        self.assertEqual(len(events), 20)
        self.assertEqual(len({event["screenshot"] for event in events}), 20)

    def test_failed_atomic_write_preserves_previous_json(self):
        path = self.root / "saved.json"
        write_json(path, {"good": True})
        with patch("panoptix_app.persistence.os.replace", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                write_json(path, {"good": False})
        self.assertEqual(json.loads(path.read_text()), {"good": True})

    def test_note_save_and_new_capture_both_survive(self):
        sid = self.evidence()
        note_store = SessionStore(self.root)
        loaded, release, capture_finished = threading.Event(), threading.Event(), threading.Event()
        original = note_store.load_session
        errors = []

        def delayed_load(session_id):
            session = original(session_id)
            loaded.set()
            release.wait(3)
            return session

        def save_note():
            try:
                note_store.update_event(sid, 1, {"staff_note": "Keep this note"})
            except Exception as exc:
                errors.append(exc)

        def capture():
            try:
                self.store.add_event(sid, {"screenshot": "002.png"})
            except Exception as exc:
                errors.append(exc)
            finally:
                capture_finished.set()

        with patch.object(note_store, "load_session", side_effect=delayed_load):
            writer = threading.Thread(target=save_note)
            writer.start()
            self.assertTrue(loaded.wait(2))
            capturer = threading.Thread(target=capture)
            capturer.start()
            capture_finished.wait(0.05)
            release.set()
            writer.join(timeout=3)
            capturer.join(timeout=3)
        self.assertEqual(errors, [])
        events = self.store.load_session(sid)["events"]
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["staff_note"], "Keep this note")

    def test_pause_blocks_click_and_hotkey_capture(self):
        sid = self.recorder.start("evidence")["id"]
        self.recorder.pause()
        for capture in (lambda: self.recorder.capture_click(10, 10), self.recorder.capture_manual_hotkey):
            with self.assertRaisesRegex(RuntimeError, "paused"):
                capture()
        self.assertEqual(self.store.load_session(sid)["events"], [])
        self.recorder.resume()
        self.recorder.capture_click(10, 10)

    def test_capture_failure_stops_worker_and_surfaces_error(self):
        failed = threading.Event()
        def fail(*args):
            failed.set()
            raise OSError("network share offline")
        with patch.object(self.recorder.capture, "capture", side_effect=fail):
            self.recorder.start("observation", settings={"interval_seconds": 0.01})
            self.assertTrue(failed.wait(2))
            self.recorder._observation_thread.join(timeout=2)
        status = self.recorder.status()
        self.assertFalse(status["active"])
        self.assertIn("network share offline", status["capture_error"])
        self.assertFalse(self.recorder._observation_thread.is_alive())
        self.recorder.start("evidence")
        self.assertIsNone(self.recorder.status()["capture_error"])

    def test_deleting_active_session_is_rejected_by_api(self):
        sid = self.recorder.start("evidence")["id"]
        server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(self.root, self.store, self.recorder))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            request = Request(f"http://127.0.0.1:{server.server_port}/api/sessions/{sid}", method="DELETE")
            with self.assertRaises(HTTPError) as error:
                urlopen(request, timeout=3)
            self.assertEqual(error.exception.code, 400)
            error.exception.close()
            self.assertTrue(self.store.load_session(sid))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_stop_recovers_when_session_was_removed_elsewhere(self):
        sid = self.recorder.start("evidence")["id"]
        self.store.delete_session(sid)
        self.recorder.stop()
        self.assertFalse(self.recorder.status()["active"])
        self.recorder.start("evidence")

    def test_retention_keeps_protected_active_session(self):
        session = self.recorder.start("evidence")
        session["started"] = "2020-01-01T00:00:00"
        write_json(self.store.sessions_dir / session["id"] / "session.json", session)
        result = cleanup_old_sessions(self.store, 1, protected_session_id=session["id"])
        self.assertEqual(result["deleted"], [])
        self.assertTrue(self.store.load_session(session["id"]))

    def test_status_still_reports_failure_when_settings_storage_is_offline(self):
        self.recorder.capture_error = "Capture stopped: share offline"
        server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(self.root, self.store, self.recorder))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.object(SettingsStore, "load", side_effect=OSError("share offline")):
                with urlopen(f"http://127.0.0.1:{server.server_port}/api/status", timeout=3) as response:
                    status = json.load(response)
            self.assertFalse(status["active"])
            self.assertIn("share offline", status["capture_error"])
            self.assertIn("share offline", status["storage_error"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_scheduler_respects_manual_start_stop_and_next_window(self):
        settings = SettingsStore(self.root)
        scheduler = BackgroundScheduler(self.recorder, settings)
        sid = self.recorder.start("background", settings={"interval_seconds": 3600})["id"]
        scheduler.evaluate(datetime(2026, 9, 8, 12))
        self.assertEqual(self.recorder.active_session_id, sid)
        self.recorder.stop()
        settings.update({"background_enabled": True, "background_interval_seconds": 3600})
        scheduler.evaluate(datetime(2026, 9, 8, 12))
        self.recorder.stop()
        scheduler.evaluate(datetime(2026, 9, 8, 12, 1))
        self.assertFalse(self.recorder.status()["active"])
        scheduler.evaluate(datetime(2026, 9, 9, 12))
        self.assertTrue(self.recorder.status()["active"])

    def test_source_startup_includes_script(self):
        command = StartupManager(self.root, Path("C:/Python312/python.exe"))._command()
        self.assertIn('panoptix.py" --background', command)

    def test_launcher_waits_for_ready_callback(self):
        order = []
        def run(*args, on_ready, **kwargs):
            order.append("listening")
            on_ready()
        with patch.object(sys, "argv", ["panoptix.py"]), patch.object(panoptix, "is_already_running", return_value=False), patch.object(panoptix, "get_data_root", return_value=self.root), patch.object(panoptix, "run_server", side_effect=run), patch.object(panoptix.webbrowser, "open", side_effect=lambda url: order.append("browser")):
            panoptix.main()
        self.assertEqual(order, ["listening", "browser"])

    def test_stale_event_position_does_not_edit_a_different_screenshot(self):
        sid = self.evidence()
        with self.assertRaises(ValueError):
            self.store.update_event(sid, 1, {"expected_screenshot": "002.png", "staff_note": "wrong image"})
        self.assertNotEqual(self.store.load_session(sid)["events"][0].get("staff_note"), "wrong image")
