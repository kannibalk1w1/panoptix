from __future__ import annotations

import argparse
import socket
import webbrowser
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from panoptix_app.app_paths import get_data_root
from panoptix_app.server import run_server


HOST = "127.0.0.1"
PORT = 8765


def is_already_running(host: str = HOST, port: int = PORT) -> bool:
    with socket.socket() as probe:
        probe.settimeout(0.5)
        return probe.connect_ex((host, port)) == 0


def send_action(action: str, host: str = HOST, port: int = PORT) -> None:
    routes = {"caption": "/api/capture-note/prompt", "clip": "/api/clips/start", "capture": "/api/capture/manual"}
    request = Request(f"http://{host}:{port}{routes[action]}", data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=30) as response:
            result = json.load(response)
        if result.get("capture_note", {}).get("error"):
            raise RuntimeError(result["capture_note"]["error"])
    except HTTPError as exc:
        try:
            message = json.load(exc).get("error")
        except (ValueError, OSError):
            message = str(exc)
        raise RuntimeError(message) from exc
    except URLError as exc:
        raise RuntimeError("Start Panoptix before using a capture shortcut") from exc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--background", action="store_true")
    actions = parser.add_mutually_exclusive_group()
    for action in ("caption", "clip", "capture"):
        actions.add_argument(f"--{action}", action="store_true", help=f"Send the {action} action to the running Panoptix instance")
    args = parser.parse_args()
    for action in ("caption", "clip", "capture"):
        if getattr(args, action):
            try:
                send_action(action)
            except RuntimeError as exc:
                print(str(exc), file=sys.stderr)
                raise SystemExit(1) from exc
            return
    url = f"http://{HOST}:{PORT}"
    def open_dashboard() -> None:
        if args.background:
            return
        try:
            webbrowser.open(url)
        except Exception:
            pass
    if is_already_running():
        open_dashboard()
        return
    run_server(get_data_root(), host=HOST, port=PORT, on_ready=open_dashboard)


if __name__ == "__main__":
    main()
