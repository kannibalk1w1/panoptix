from __future__ import annotations

from pathlib import Path
import webbrowser

from panoptix_app.server import run_server


def main() -> None:
    root = Path(__file__).resolve().parent / "data"
    url = "http://127.0.0.1:8765"
    try:
        webbrowser.open(url)
    except Exception:
        pass
    run_server(root, port=8765)


if __name__ == "__main__":
    main()
