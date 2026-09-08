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
- Scheduled passive background capture with Windows startup, tray controls, manual hotkey capture, and unchanged-frame skipping.
- Session list.
- Review workflow with search, filters, notes, tags, highlights, selected export flags, redactions, and click marker styling.
- Self-contained HTML export.
- Formal PDF export.
- Evidence pack ZIP export and verification with HTML, PDF, selected clean/annotated screenshots, CSV manifest, JSON manifest, file sizes, and SHA-256 checksums.
- Configurable export folder for reports and evidence packs.
- Configurable screenshot storage folder with a native Windows folder browser, so sessions and screenshots can live on a shared network folder.
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

## Screenshot Storage Folder

Settings has a `Screenshot storage folder` card. `Browse folder` opens the normal
Windows folder picker, so the folder can be a local path or a network share such as
`\\server\share\panoptix-evidence`. Sessions, screenshots and `settings.json` are all
written there.

Notes:

- The chosen folder is remembered in `%LOCALAPPDATA%\Panoptix\config.json`, so it survives upgrades.
- The new folder takes effect immediately; no restart is needed. Stop any active recording first.
- Existing sessions stay where they are. Copy them into the new folder if they are still needed.
- If the folder is unreachable at startup, Panoptix falls back to local storage and shows a warning on Home instead of failing to start.
- Precedence is `PANOPTIX_DATA_DIR` environment variable, then the configured folder, then `%LOCALAPPDATA%\Panoptix\data`.

## Build Windows EXE And Installer

Run on a Windows machine; PyInstaller cannot cross-compile from Linux or macOS.

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Public\panoptix\scripts\build_windows.ps1 -Version 0.1.0
```

The script installs the build and runtime dependencies, writes `dist\Panoptix.exe`,
and then builds `dist\Panoptix-Setup-0.1.0.exe` when Inno Setup is available:

```powershell
winget install JRSoftware.InnoSetup
```

Useful switches: `-SkipDependencies` to leave the current environment alone and
`-SkipInstaller` to build only the executable.

The installer is per user by default so a tester without admin rights can install it,
and offers an all-users install when run as an administrator. It is unsigned, so
Windows SmartScreen shows a `More info` -> `Run anyway` prompt on first launch.
Uninstalling leaves captured evidence in place.

## Test

```powershell
python -m unittest discover -s C:\Users\Public\panoptix\tests -v
```
