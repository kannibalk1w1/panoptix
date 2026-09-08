from __future__ import annotations

import argparse
import socket
import webbrowser

from panoptix_app.app_paths import get_data_root
from panoptix_app.server import run_server


HOST = "127.0.0.1"
PORT = 8765


def is_already_running(host: str = HOST, port: int = PORT) -> bool:
    with socket.socket() as probe:
        probe.settimeout(0.5)
        return probe.connect_ex((host, port)) == 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--background", action="store_true")
    args = parser.parse_args()
    url = f"http://{HOST}:{PORT}"
    if not args.background:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    if is_already_running():
        return
    run_server(get_data_root(), host=HOST, port=PORT)


if __name__ == "__main__":
    main()
