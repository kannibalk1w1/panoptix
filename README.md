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
- Vanilla dashboard served locally.

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
