"""Cooperating processes share a file lock; readers only see complete writes."""
from __future__ import annotations

from contextlib import contextmanager
from functools import wraps
import json
import os
from pathlib import Path
import tempfile
import threading
import time


_registry_guard = threading.Lock()
_locks: dict[str, tuple[threading.RLock, threading.local]] = {}


@contextmanager
def data_lock(root: Path):
    root = Path(root).resolve()
    key = str(root)
    with _registry_guard:
        lock, local = _locks.setdefault(key, (threading.RLock(), threading.local()))
    with lock:
        if getattr(local, "held", False):
            yield
            return
        root.mkdir(parents=True, exist_ok=True)
        with (root / ".panoptix.lock").open("a+b") as handle:
            if os.name == "nt":
                import msvcrt

                if handle.seek(0, os.SEEK_END) == 0:
                    handle.write(b"\0")
                    handle.flush()
                deadline = time.monotonic() + 30
                while True:
                    handle.seek(0)
                    try:
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                        break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise TimeoutError("The evidence folder is busy; try again shortly.")
                        time.sleep(0.05)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            local.held = True
            try:
                yield
            finally:
                local.held = False
                if os.name == "nt":
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def synchronized(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with data_lock(self.root):
            return method(self, *args, **kwargs)
    return wrapped


@contextmanager
def atomic_output(path: Path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".panoptix-", suffix=path.suffix, dir=path.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        yield temporary
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_json(path: Path, value) -> None:
    with atomic_output(path) as temporary:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
