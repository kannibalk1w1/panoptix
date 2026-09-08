from pathlib import Path
import os
import subprocess
import sys


def open_folder(path: Path) -> None:
    path = Path(path).resolve()
    if not path.is_dir():
        raise FileNotFoundError("The export folder does not exist")
    if sys.platform == "win32":
        os.startfile(str(path))
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
