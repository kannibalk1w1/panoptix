from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from .annotation import annotate_click
from .storage import SessionStore


def redact_event_screenshot(
    root: Path | SessionStore,
    session_id: str,
    event_index: int,
    rect: dict[str, int] | None = None,
    preset: str | None = None,
) -> dict[str, Any]:
    store = root if isinstance(root, SessionStore) else SessionStore(Path(root))
    session = store.load_session(session_id)
    event = next((item for item in session["events"] if item.get("index") == event_index), None)
    if event is None:
        raise KeyError(f"Event not found: {event_index}")

    screenshot_dir = store.screenshot_dir(session_id)
    image_path = screenshot_dir / event["screenshot"]
    if not image_path.exists():
        raise FileNotFoundError(image_path)

    backup_dir = screenshot_dir / "originals"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / image_path.name
    if not backup_path.exists():
        shutil.copy2(image_path, backup_path)

    with Image.open(image_path) as image:
        working = image.convert("RGB")
        box = _resolve_box(working.size, rect, preset)
        ImageDraw.Draw(working).rectangle(box, fill=(0, 0, 0))
        working.save(image_path)

    redaction = {
        "type": "black_box",
        "preset": preset or "manual",
        "x": box[0],
        "y": box[1],
        "width": box[2] - box[0],
        "height": box[3] - box[1],
    }
    event.setdefault("redactions", []).append(redaction)
    session = store.update_event(session_id, event_index, {"redactions": event["redactions"]})
    return {"session": session, "event": next(item for item in session["events"] if item.get("index") == event_index)}


def _resolve_box(size: tuple[int, int], rect: dict[str, int] | None, preset: str | None) -> tuple[int, int, int, int]:
    width, height = size
    if preset == "top_strip":
        strip_height = max(1, int(height * 0.14))
        return (0, 0, width, strip_height)
    if rect is None:
        raise ValueError("Redaction requires rect or preset")
    x = max(0, int(rect["x"]))
    y = max(0, int(rect["y"]))
    redaction_width = max(1, int(rect["width"]))
    redaction_height = max(1, int(rect["height"]))
    return (x, y, min(width, x + redaction_width), min(height, y + redaction_height))


def restore_original_screenshot(root: Path | SessionStore, session_id: str, event_index: int) -> dict[str, Any]:
    store = root if isinstance(root, SessionStore) else SessionStore(Path(root))
    session = store.load_session(session_id)
    event = next((item for item in session["events"] if item.get("index") == event_index), None)
    if event is None:
        raise KeyError(f"Event not found: {event_index}")
    screenshot_dir = store.screenshot_dir(session_id)
    image_path = screenshot_dir / event["screenshot"]
    backup_path = screenshot_dir / "originals" / event["screenshot"]
    if not backup_path.exists():
        raise FileNotFoundError(backup_path)
    if "x" in event and "y" in event:
        annotate_click(backup_path, image_path, int(event["x"]), int(event["y"]), event.get("marker"))
    else:
        shutil.copy2(backup_path, image_path)
    session = store.update_event(session_id, event_index, {"redactions": []})
    return {"session": session, "event": next(item for item in session["events"] if item.get("index") == event_index)}
