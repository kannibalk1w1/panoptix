from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panoptix import is_already_running


class LauncherTests(unittest.TestCase):
    def test_detects_a_running_instance(self):
        server = HTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            self.assertTrue(is_already_running("127.0.0.1", server.server_address[1]))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertFalse(is_already_running("127.0.0.1", server.server_address[1]))


if __name__ == "__main__":
    unittest.main()
