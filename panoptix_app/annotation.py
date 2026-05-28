from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from .storage import SessionStore


DEFAULT_MARKER: dict[str, Any] = {
    "shape": "circle",
    "color": "#ef233c",
    "size": 32,
    "stroke": 3,
}


def normalize_marker(marker: dict[str, Any] | None = None) -> dict[str, Any]:
    merged = {**DEFAULT_MARKER, **(marker or {})}
    merged["size"] = max(6, int(merged["size"]))
    merged["stroke"] = max(1, int(merged["stroke"]))
    if merged["shape"] not in {"circle", "square", "crosshair", "arrow"}:
        merged["shape"] = "circle"
    return merged


def annotate_click(source: Path, output: Path, x: int, y: int, marker: dict[str, Any] | None = None) -> Path:
    marker = normalize_marker(marker)
    output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        working = image.convert("RGB")
    draw = ImageDraw.Draw(working)
    size = marker["size"]
    half = size // 2
    stroke = marker["stroke"]
    color = marker["color"]
    shape = marker["shape"]
    if shape == "square":
        draw.rectangle((x - half, y - half, x + half, y + half), outline=color, width=stroke)
    elif shape == "crosshair":
        draw.line((x - half, y, x + half, y), fill=color, width=stroke)
        draw.line((x, y - half, x, y + half), fill=color, width=stroke)
        draw.ellipse((x - half, y - half, x + half, y + half), outline=color, width=stroke)
    elif shape == "arrow":
        draw.line((x - size, y - size, x, y), fill=color, width=stroke)
        draw.polygon([(x, y), (x - 12, y - 2), (x - 2, y - 12)], fill=color)
    else:
        draw.ellipse((x - half, y - half, x + half, y + half), outline=color, width=stroke)
    working.save(output)
    return output


def update_event_marker(
    root: Path | SessionStore,
    session_id: str,
    event_index: int,
    marker: dict[str, Any] | None = None,
) -> dict[str, Any]:
    store = root if isinstance(root, SessionStore) else SessionStore(Path(root))
    session = store.load_session(session_id)
    event = next((item for item in session["events"] if item.get("index") == event_index), None)
    if event is None:
        raise KeyError(f"Event not found: {event_index}")
    if "x" not in event or "y" not in event:
        raise ValueError("Only click events can have markers")

    screenshot_dir = store.screenshot_dir(session_id)
    source = _source_for_event(screenshot_dir, event)
    output = screenshot_dir / event["screenshot"]
    normalized = normalize_marker(marker)
    annotate_click(source, output, int(event["x"]), int(event["y"]), normalized)
    session = store.update_event(session_id, event_index, {"marker": normalized, "redactions": []})
    return {"session": session, "event": next(item for item in session["events"] if item.get("index") == event_index)}


def _source_for_event(screenshot_dir: Path, event: dict[str, Any]) -> Path:
    candidates = []
    if event.get("original_screenshot"):
        candidates.append(screenshot_dir / event["original_screenshot"])
    if event.get("screenshot"):
        candidates.append(screenshot_dir / "originals" / event["screenshot"])
        candidates.append(screenshot_dir / event["screenshot"])
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(event.get("original_screenshot") or event.get("screenshot") or "screenshot")
