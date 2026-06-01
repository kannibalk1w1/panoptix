from __future__ import annotations

import argparse
from pathlib import Path
import webbrowser

from panoptix_app.app_paths import get_data_root
from panoptix_app.server import run_server


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--background", action="store_true")
    args = parser.parse_args()
    root = get_data_root()
    url = "http://127.0.0.1:8765"
    if not args.background:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    run_server(root, port=8765)


if __name__ == "__main__":
    main()
