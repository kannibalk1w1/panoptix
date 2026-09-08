from __future__ import annotations

import base64
import csv
import hashlib
import html
import json
import re
from io import StringIO
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED, BadZipFile

from .settings import SettingsStore
from .storage import SessionStore
from .persistence import synchronized, atomic_output


def selected_events(session: dict) -> list[dict]:
    return [event for event in session.get("events", []) if event.get("selected_for_export", True)]


def _local_export_dir(root: Path, session_id: str | None = None) -> Path:
    output_dir = Path(root) / "exports"
    if session_id:
        output_dir = output_dir / session_id
    return output_dir


def _configured_export_dir(configured: str, session_id: str | None = None) -> Path:
    output_dir = _normalize_configured_export_dir(configured)
    if session_id:
        output_dir = output_dir / session_id
    return output_dir


def _normalize_configured_export_dir(configured: str) -> Path:
    output_dir = Path(configured).expanduser()
    if output_dir.is_absolute() or len(output_dir.parts) != 1:
        return output_dir
    known_user_folders = {
        "desktop": "Desktop",
        "documents": "Documents",
        "downloads": "Downloads",
    }
    known_folder = known_user_folders.get(configured.strip().lower())
    if known_folder:
        return Path.home() / known_folder
    return output_dir


def export_destination_status(root: Path, session_id: str | None = None) -> dict:
    configured = SettingsStore(root).load().get("export_directory", "")
    if configured:
        output_dir = _configured_export_dir(configured, session_id)
    else:
        output_dir = _local_export_dir(root, session_id)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        return {
            "path": str(output_dir),
            "configured_directory": configured,
            "requested_path": str(output_dir),
            "using_configured_directory": bool(configured),
            "fallback_used": False,
            "writable": True,
            "warning": "",
        }
    except OSError as exc:
        fallback = _local_export_dir(root, session_id)
        fallback.mkdir(parents=True, exist_ok=True)
        return {
            "path": str(fallback),
            "configured_directory": configured,
            "requested_path": str(output_dir),
            "using_configured_directory": False,
            "fallback_used": True,
            "writable": False,
            "warning": f"Configured export folder is not usable, so Panoptix will use local exports instead: {exc}",
        }


def export_output_dir(root: Path, session_id: str) -> Path:
    return Path(export_destination_status(root, session_id)["path"])


class HtmlExporter:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.store = SessionStore(self.root)

    @synchronized
    def export(self, session_id: str) -> Path:
        session = self.store.load_session(session_id)
        output_dir = export_output_dir(self.root, session_id)
        output = output_dir / "evidence-report.html"
        with atomic_output(output) as temporary:
            temporary.write_text(self._render(session), encoding="utf-8")
        return output

    def _render(self, session: dict) -> str:
        metadata = session.get("metadata", {})
        title = metadata.get("activity") or "Panoptix Evidence Report"
        events = selected_events(session)
        highlights = [event for event in events if event.get("highlight")]
        highlight_cards = "\n".join(self._render_event(session, event) for event in highlights)
        cards = "\n".join(self._render_event(session, event) for event in events)
        metadata_rows = "\n".join(
            f"<dt>{html.escape(str(key).replace('_', ' ').title())}</dt><dd>{html.escape(str(value))}</dd>"
            for key, value in metadata.items()
            if value
        )
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    :root {{ --bg: #101318; --sur: #181d25; --text: #f5f7fa; --muted: #aab3c2; --accent: #4ade80; --danger: #ef233c; }}
    body {{ margin: 0; font-family: Arial, sans-serif; background: var(--bg); color: var(--text); }}
    header {{ padding: 28px 36px; border-bottom: 1px solid #2a313d; }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 28px; }}
    dl {{ display: grid; grid-template-columns: 180px 1fr; gap: 8px 18px; color: var(--muted); }}
    dt {{ font-weight: 700; color: var(--text); }}
    .event {{ background: var(--sur); border: 1px solid #2a313d; border-radius: 8px; margin: 24px 0; overflow: hidden; }}
    .event-content {{ padding: 18px; }}
    .confirmation {{ margin-top: 32px; padding: 18px; border: 1px solid #2a313d; border-radius: 8px; background: var(--sur); }}
    .signature-line {{ margin-top: 28px; border-top: 1px solid var(--muted); padding-top: 8px; color: var(--muted); }}
    img {{ display: block; width: 100%; height: auto; background: #000; }}
    .tags span {{ display: inline-block; margin: 4px 6px 0 0; padding: 4px 8px; background: #233044; border-radius: 999px; color: var(--accent); font-size: 12px; }}
  </style>
</head>
<body>
  <header>
    <h1>{html.escape(title)}</h1>
    <p>Generated by Panoptix. Mode: {html.escape(session.get("mode", ""))}. Started: {html.escape(session.get("started", ""))}</p>
  </header>
  <main>
    <section>
      <h2>Session Metadata</h2>
      <dl>{metadata_rows}</dl>
    </section>
    {self._render_highlight_section(highlight_cards)}
    <section>
      <h2>Evidence</h2>
      {cards}
    </section>
    {self._render_confirmation(metadata)}
  </main>
</body>
</html>
"""

    @staticmethod
    def _render_highlight_section(highlight_cards: str) -> str:
        if not highlight_cards:
            return ""
        return f"""<section>
      <h2>Marked Highlights</h2>
      {highlight_cards}
    </section>"""

    def _render_event(self, session: dict, event: dict) -> str:
        image_src = self._image_data_url(session["id"], event["screenshot"])
        tags = "".join(f"<span>{html.escape(str(tag))}</span>" for tag in event.get("tags", []))
        note = event.get("staff_note") or event.get("note") or ""
        quote = event.get("cyp_quote") or ""
        return f"""<article class="event">
  <img src="{image_src}" alt="Evidence screenshot {event.get('index', '')}">
  <div class="event-content">
    <h3>{event.get('index', '')}. {html.escape(event.get('title') or event.get('type', 'Screenshot').title())}</h3>
    <p><strong>Time:</strong> {html.escape(event.get('timestamp', ''))}</p>
    <p>{html.escape(note)}</p>
    <p><em>{html.escape(quote)}</em></p>
    <div class="tags">{tags}</div>
  </div>
</article>"""

    @staticmethod
    def _render_confirmation(metadata: dict) -> str:
        staff = metadata.get("staff") or "Staff member"
        purpose = metadata.get("purpose") or "evidence"
        return f"""<section class="confirmation">
      <h2>Staff Confirmation</h2>
      <p>I confirm this local Panoptix export is an accurate selection of evidence for {html.escape(str(purpose))}.</p>
      <p class="signature-line">{html.escape(str(staff))} / Date</p>
    </section>"""

    def _image_data_url(self, session_id: str, filename: str) -> str:
        path = self.root / "sessions" / session_id / "screenshots" / filename
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{encoded}"


class PdfExporter:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.store = SessionStore(self.root)

    @synchronized
    def export(self, session_id: str) -> Path:
        try:
            from fpdf import FPDF
        except ImportError as exc:
            raise RuntimeError("fpdf2 is not installed; PDF export is unavailable") from exc

        session = self.store.load_session(session_id)
        output_dir = export_output_dir(self.root, session_id)
        output = output_dir / "evidence-report.pdf"
        metadata = session.get("metadata", {})
        title = metadata.get("activity") or "Panoptix Evidence Report"

        pdf = FPDF(unit="mm", format="A4")
        pdf.set_compression(False)
        pdf.set_auto_page_break(auto=True, margin=14)
        self._add_summary_page(pdf, session, title)
        if session.get("mode") == "observation":
            self._add_observation_pages(pdf, session)
        else:
            for event in selected_events(session):
                self._add_event_page(pdf, session, event, title)
        self._add_footers(pdf)
        with atomic_output(output) as temporary:
            pdf.output(str(temporary))
        return output

    def _add_summary_page(self, pdf, session: dict, title: str) -> None:
        metadata = session.get("metadata", {})
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 18)
        pdf.cell(0, 10, self._clean(title))
        pdf.ln(10)
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 8, f"Generated by Panoptix | Mode: {session.get('mode', '')}")
        pdf.ln(8)
        pdf.cell(0, 8, f"Started: {session.get('started', '')}")
        pdf.ln(8)
        if session.get("stopped"):
            pdf.cell(0, 8, f"Stopped: {session.get('stopped')}")
            pdf.ln(8)
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "Session metadata")
        pdf.ln(8)
        pdf.set_font("Helvetica", "", 11)
        page_width = pdf.w - pdf.l_margin - pdf.r_margin
        for key, value in metadata.items():
            if value:
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(page_width, 7, f"{key.replace('_', ' ').title()}: {self._clean(str(value))}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(6)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "Staff Confirmation")
        pdf.ln(8)
        pdf.set_font("Helvetica", "", 11)
        purpose = metadata.get("purpose") or "evidence"
        staff = metadata.get("staff") or "Staff member"
        pdf.multi_cell(page_width, 7, self._clean(f"I confirm this local Panoptix export is an accurate selection of evidence for {purpose}."))
        pdf.ln(12)
        pdf.cell(80, 7, self._clean(str(staff)))
        pdf.cell(30, 7, "Date")

    def _add_event_page(self, pdf, session: dict, event: dict, title: str) -> None:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        heading = event.get("title") or event.get("type", "Screenshot").title()
        page_width = pdf.w - pdf.l_margin - pdf.r_margin
        pdf.multi_cell(page_width, 8, self._clean(f"{event.get('index', '')}. {heading}"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, self._clean(event.get("timestamp", "")))
        pdf.ln(6)
        image_path = self.root / "sessions" / session["id"] / "screenshots" / event["screenshot"]
        if image_path.exists():
            self._add_image(pdf, image_path)
        pdf.ln(4)
        pdf.set_font("Helvetica", "", 11)
        for label, key in (("Staff note", "staff_note"), ("CYP quote", "cyp_quote")):
            value = event.get(key)
            if value:
                pdf.set_font("Helvetica", "B", 11)
                pdf.cell(0, 6, label)
                pdf.ln(6)
                pdf.set_font("Helvetica", "", 11)
                pdf.multi_cell(page_width, 6, self._clean(str(value)), new_x="LMARGIN", new_y="NEXT")
        tags = event.get("tags") or []
        if tags:
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(page_width, 6, self._clean("Tags: " + ", ".join(str(tag) for tag in tags)), new_x="LMARGIN", new_y="NEXT")
        if event.get("highlight"):
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 6, "Marked as highlight")
            pdf.ln(6)

    def _add_observation_pages(self, pdf, session: dict) -> None:
        events = selected_events(session)
        highlighted = [event for event in events if event.get("highlight")]
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "Highlights")
        pdf.ln(10)
        pdf.set_font("Helvetica", "", 11)
        if not highlighted:
            pdf.multi_cell(pdf.w - pdf.l_margin - pdf.r_margin, 7, "No screenshots were marked as highlights.")
        else:
            for event in highlighted:
                self._add_contact_sheet_item(pdf, session, event, include_note=True)

        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "Observation Timeline")
        pdf.ln(10)
        pdf.set_font("Helvetica", "", 10)
        for event in events:
            if pdf.get_y() > 250:
                pdf.add_page()
                pdf.set_font("Helvetica", "B", 16)
                pdf.cell(0, 10, "Observation Timeline")
                pdf.ln(10)
                pdf.set_font("Helvetica", "", 10)
            self._add_contact_sheet_item(pdf, session, event, include_note=False)

    def _add_contact_sheet_item(self, pdf, session: dict, event: dict, include_note: bool) -> None:
        x = pdf.get_x()
        y = pdf.get_y()
        image_path = self.root / "sessions" / session["id"] / "screenshots" / event["screenshot"]
        if image_path.exists():
            self._add_thumbnail(pdf, image_path, x, y)
        pdf.set_xy(x + 48, y)
        title = event.get("title") or event.get("type", "Screenshot").title()
        marker = " [highlight]" if event.get("highlight") else ""
        pdf.set_font("Helvetica", "B", 10)
        pdf.multi_cell(130, 5, self._clean(f"{event.get('index', '')}. {title}{marker}"))
        pdf.set_x(x + 48)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(130, 5, self._clean(event.get("timestamp", "")))
        if include_note and event.get("staff_note"):
            pdf.set_x(x + 48)
            pdf.multi_cell(130, 5, self._clean(str(event["staff_note"])))
        pdf.set_y(max(pdf.get_y(), y + 34))
        pdf.ln(3)

    @staticmethod
    def _add_thumbnail(pdf, image_path: Path, x: float, y: float) -> None:
        try:
            pdf.image(str(image_path), x=x, y=y, w=42, h=30)
        except Exception:
            pdf.set_xy(x, y)
            pdf.set_font("Helvetica", "I", 8)
            pdf.multi_cell(42, 5, f"Image unavailable: {image_path.name}")
            pdf.set_xy(x, y)

    @staticmethod
    def _add_image(pdf, image_path: Path) -> None:
        try:
            from PIL import Image
        except ImportError:
            return
        try:
            with Image.open(image_path) as image:
                width_px, height_px = image.size
            page_width = pdf.w - pdf.l_margin - pdf.r_margin
            max_height = 145
            ratio = height_px / width_px if width_px else 1
            width = page_width
            height = width * ratio
            if height > max_height:
                height = max_height
                width = height / ratio if ratio else page_width
            pdf.image(str(image_path), w=width, h=height)
        except Exception:
            pdf.set_font("Helvetica", "I", 10)
            pdf.cell(0, 6, f"Screenshot could not be embedded: {image_path.name}")
            pdf.ln(6)

    @staticmethod
    def _clean(value: str) -> str:
        return value.encode("latin-1", errors="replace").decode("latin-1")

    @staticmethod
    def _add_footers(pdf) -> None:
        page_count = pdf.page_no()
        for page in range(1, page_count + 1):
            pdf.page = page
            pdf.set_y(-12)
            pdf.set_font("Helvetica", "", 8)
            pdf.cell(0, 6, f"Generated by Panoptix | Page {page} of {page_count}", align="C")


class SessionExporter:
    def __init__(self, root: Path):
        self.root = Path(root)

    @synchronized
    def export(self, session_id: str) -> dict[str, Path]:
        return {
            "html": HtmlExporter(self.root).export(session_id),
            "pdf": PdfExporter(self.root).export(session_id),
        }


class ImageZipExporter:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.store = SessionStore(self.root)

    @synchronized
    def export(self, session_id: str, variant: str = "annotated") -> Path:
        if variant not in {"annotated", "original", "both"}:
            raise ValueError("Unknown image export variant")
        session = self.store.load_session(session_id)
        output_dir = export_output_dir(self.root, session_id)
        output = output_dir / f"selected-images-{variant}.zip"
        events = selected_events(session)
        if not events:
            raise ValueError("Select at least one screenshot before exporting")
        with atomic_output(output) as temporary, ZipFile(temporary, "w", ZIP_DEFLATED) as archive:
            archive.writestr("metadata.json", json.dumps({"session": {**session, "events": events}, "events": events}, indent=2))
            for event in events:
                for suffix, source in self._sources(session_id, event, variant):
                    archive.write(source, self._archive_name(session_id, event, suffix))
        return output

    def _sources(self, session_id: str, event: dict, variant: str) -> list[tuple[str, Path]]:
        screenshot_dir = self.root / "sessions" / session_id / "screenshots"
        annotated = screenshot_dir / event["screenshot"]
        original = self._original_source(screenshot_dir, event) or annotated
        if variant == "original":
            return [("original", original)]
        if variant == "both":
            return [("original", original), ("annotated", annotated)]
        return [("annotated", annotated)]

    @staticmethod
    def _original_source(screenshot_dir: Path, event: dict) -> Path | None:
        candidates = []
        if event.get("original_screenshot"):
            candidates.append(screenshot_dir / event["original_screenshot"])
        if event.get("screenshot"):
            candidates.append(screenshot_dir / "originals" / event["screenshot"])
        return next((candidate for candidate in candidates if candidate.exists()), None)

    @staticmethod
    def _archive_name(session_id: str, event: dict, suffix: str) -> str:
        return f"Panoptix_{session_id}_{int(event['index']):03d}_{suffix}.png"


class EvidencePackExporter:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.store = SessionStore(self.root)

    @synchronized
    def export(self, session_id: str, include_originals: bool = False) -> Path:
        session = self.store.load_session(session_id)
        output_dir = export_output_dir(self.root, session_id)
        output = output_dir / "evidence-pack.zip"
        events = selected_events(session)
        if not events:
            raise ValueError("Select at least one screenshot before exporting")
        report_paths = SessionExporter(self.root).export(session_id)
        image_exporter = ImageZipExporter(self.root)
        files: list[dict] = []

        with atomic_output(output) as temporary, ZipFile(temporary, "w", ZIP_DEFLATED) as archive:
            self._write_file(archive, files, report_paths["html"], "reports/evidence-report.html")
            self._write_file(archive, files, report_paths["pdf"], "reports/evidence-report.pdf")
            for event in events:
                for suffix, source in image_exporter._sources(session_id, event, "both" if include_originals else "annotated"):
                    self._write_file(
                        archive,
                        files,
                        source,
                        f"images/{image_exporter._archive_name(session_id, event, suffix)}",
                        event_index=event.get("index"),
                        variant=suffix,
                    )
            csv_data = self._csv(events, files).encode("utf-8")
            archive.writestr("manifest.csv", csv_data)
            files.append({"path": "manifest.csv", "size_bytes": len(csv_data), "sha256": hashlib.sha256(csv_data).hexdigest()})
            manifest = {"session": {**session, "events": events}, "events": events, "files": files, "includes_originals": include_originals}
            archive.writestr("manifest.json", json.dumps(manifest, indent=2))
        return output

    @staticmethod
    def _write_file(
        archive: ZipFile,
        manifest_files: list[dict],
        source: Path,
        archive_path: str,
        event_index: int | None = None,
        variant: str | None = None,
    ) -> None:
        data = source.read_bytes()
        archive.writestr(archive_path, data)
        manifest_files.append(
            {
                "path": archive_path,
                "size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "event_index": event_index,
                "variant": variant,
            }
        )

    @staticmethod
    def _csv(events: list[dict], files: list[dict]) -> str:
        output = StringIO()
        fieldnames = [
            "index",
            "title",
            "timestamp",
            "type",
            "highlight",
            "tags",
            "screenshot",
            "original_screenshot",
            "files",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for event in events:
            row = dict(event)
            row["tags"] = "; ".join(str(tag) for tag in event.get("tags", []))
            event_files = [item for item in files if item.get("event_index") == event.get("index")]
            row["files"] = "; ".join(
                f"{item['path']} sha256={item['sha256']} size={item['size_bytes']}" for item in event_files
            )
            writer.writerow(row)
        return output.getvalue()


class EvidencePackVerifier:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.store = SessionStore(self.root)

    @synchronized
    def verify(self, session_id: str) -> dict:
        self.store.load_session(session_id)
        pack_path = export_output_dir(self.root, session_id) / "evidence-pack.zip"
        failures = []
        checked = 0
        try:
            with ZipFile(pack_path) as archive:
                manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
                self._validate_manifest(manifest, session_id, archive.namelist())
                files = manifest["files"]
                checked = len(files)
                archive_names = archive.namelist()
                for item in files:
                    failure = self._verify_file(archive, item, archive_names)
                    if failure:
                        failures.append(failure)
        except FileNotFoundError:
            failures.append({"path": str(pack_path), "reason": "pack_missing"})
        except (BadZipFile, KeyError, ValueError, TypeError) as exc:
            failures.append({"path": str(pack_path), "reason": type(exc).__name__})

        return {
            "ok": not failures,
            "checked": checked,
            "failure_count": len(failures),
            "failures": failures,
        }

    @staticmethod
    def _validate_manifest(manifest: dict, session_id: str, archive_names: list[str]) -> None:
        if not isinstance(manifest, dict):
            raise ValueError("Invalid manifest")
        session, events, files = manifest.get("session"), manifest.get("events"), manifest.get("files")
        if not isinstance(session, dict) or session.get("id") != session_id:
            raise ValueError("Manifest session does not match")
        if not isinstance(events, list) or not events or session.get("events") != events:
            raise ValueError("Manifest must contain the selected events")
        if not isinstance(files, list) or not files:
            raise ValueError("Manifest has no files")
        paths = []
        for item in files:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                raise ValueError("Invalid file entry")
            if not isinstance(item.get("size_bytes"), int) or item["size_bytes"] < 0:
                raise ValueError("Invalid file size")
            if not isinstance(item.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
                raise ValueError("Invalid checksum")
            paths.append(item["path"])
        required = {"reports/evidence-report.html", "reports/evidence-report.pdf"}
        indexes = set()
        for event in events:
            if not isinstance(event, dict) or not isinstance(event.get("index"), int) or event["index"] in indexes:
                raise ValueError("Invalid or duplicate event index")
            indexes.add(event["index"])
            required.add(f"images/{ImageZipExporter._archive_name(session_id, event, 'annotated')}")
            if manifest.get("includes_originals"):
                required.add(f"images/{ImageZipExporter._archive_name(session_id, event, 'original')}")
        if len(paths) != len(set(paths)) or not required.issubset(paths):
            raise ValueError("Manifest is incomplete or has duplicate paths")
        if archive_names.count("manifest.json") != 1 or archive_names.count("manifest.csv") != 1:
            raise ValueError("Missing or duplicate manifest")
        # Older packs did not checksum CSV; continue verifying those packs.
        if set(archive_names) != set(paths) | {"manifest.json", "manifest.csv"}:
            raise ValueError("Archive contents do not match the manifest")

    @staticmethod
    def _verify_file(archive: ZipFile, item: dict, archive_names: list[str]) -> dict | None:
        path = item["path"]
        if archive_names.count(path) > 1:
            return {"path": path, "reason": "duplicate_path"}
        try:
            data = archive.read(path)
        except KeyError:
            return {"path": path, "reason": "missing"}
        actual_size = len(data)
        actual_sha256 = hashlib.sha256(data).hexdigest()
        reasons = []
        if actual_size != item.get("size_bytes"):
            reasons.append("size_mismatch")
        if actual_sha256 != item.get("sha256"):
            reasons.append("sha256_mismatch")
        if not reasons:
            return None
        return {
            "path": path,
            "reason": ",".join(reasons),
            "expected_size": item.get("size_bytes"),
            "actual_size": actual_size,
            "expected_sha256": item.get("sha256"),
            "actual_sha256": actual_sha256,
        }
