# Panoptix

Local AP evidence capture tool.

## Run

```powershell
python C:\Users\Public\panoptix\panoptix.py
```

Then open:

```text
http://127.0.0.1:8765
```

## Current MVP

- Evidence Capture session metadata.
- Click-event capture API with screenshot storage and click coordinates.
- Observation Mode with automatic periodic screenshots.
- Session list.
- Self-contained HTML export.
- Formal PDF export.
- Persistent settings for observation interval, retention days, storage warning, and default evidence purpose.
- Local storage usage display and warning threshold.
- Retention cleanup for deleting sessions older than the configured retention period.
- Vanilla dashboard served locally.

Evidence Capture starts a global mouse hook when `pynput` is installed. If dependencies are missing, the dashboard stays usable and reports manual fallback mode.

The current capture layer falls back to placeholder PNGs if screenshot dependencies are not installed.

## Optional Dependencies

Install real screenshot support with:

```powershell
pip install -r C:\Users\Public\panoptix\requirements.txt
```

## Test

```powershell
python -m unittest discover -s C:\Users\Public\panoptix\tests -v
```
