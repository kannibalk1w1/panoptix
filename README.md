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
- Evidence pack ZIP export and verification with HTML, PDF, selected annotated screenshots, CSV manifest, JSON manifest, file sizes, and SHA-256 checksums. Unredacted originals require an explicit export choice.
- Configurable export folder for reports and evidence packs.
- Configurable screenshot storage folder with a native Windows folder browser, so sessions and screenshots can live on a shared network folder.
- Persistent settings for observation interval, retention days, storage warning, and default evidence purpose.
- Local storage usage display and warning threshold.
- Retention preview and recoverable removal of sessions older than the configured retention period.
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

Browser regression tests run against an isolated local server with synthetic
screenshots, without starting global mouse or keyboard hooks:

```powershell
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python -m unittest tests.browser_review -v
```

Set `PANOPTIX_TEST_BROWSER` to a Chromium executable to use an existing browser
installation. The Windows build workflow runs both test suites before packaging.

## Review And Export Safety

- Changing a click marker preserves all applied redactions.
- Evidence packs include only selected annotated images by default. Including
  unredacted originals requires ticking the separate checkbox and confirming the
  warning. Original-image ZIP exports show the same warning.
- Existing exports are not modified when you redact a screenshot or upgrade the
  app. Regenerate reports and packs when their contents need to change.
- Notes and export selections being edited survive filtering and navigation in
  the same browser tab. Save a note to persist it; exporting saves pending notes
  and selections for that session. Closing or reloading the tab warns if drafts
  remain. Drafts are not saved across browser crashes.
- Pack verification checks manifest structure, required contents, sizes and
  checksums. It checks internal consistency, not authorship or a digital signature.

## Review Shortcuts And Recovery

- **Open export folder** in Review opens the session's export destination in the
  desktop file manager. It follows the configured export folder.
- **Save all notes** saves pending notes, tags, highlights and export selections
  for the current session, including screenshots hidden by filters. The unsaved
  indicator counts screenshots with pending edits.
- **Sessions** supports activity/mode/ID search and inclusive From/To dates.
  Filters stay set while navigating; use **Clear filters** to see everything.
- **Zoom / drag to redact** opens a larger screenshot viewer. Choose Fit or a zoom
  percentage, drag a rectangle in either direction, inspect the selection and
  choose **Apply redaction**. Zoomed images can be scrolled. Coordinate-based
  redaction remains available in Review.
- **Preview retention cleanup** in Settings lists the sessions that would be
  removed. Confirming moves only those still-eligible sessions to **Deleted
  sessions**, which is also accessible from the Sessions page.
- Session removal keeps saved notes, screenshots and local exports under the
  current data folder's `trash` directory. **Restore** returns them to Sessions
  without overwriting an existing session. Deleted sessions still occupy disk
  space and are not automatically purged. Exports in separately configured
  folders are not moved. Unsaved browser drafts are not part of a deleted backup.

## Recording And Storage

- Pause blocks automatic screenshots, click screenshots and manual hotkey captures.
- A capture failure stops that recording and reports the error on the dashboard.
  Resolve the problem and start a new recording to continue.
- Stop the current recording before deleting its session or switching folders.
  Retention cleanup also protects the locally active recording.
- Manually starting background capture runs independently of the schedule.
  Stopping a scheduled session suppresses it for that block; the next separate
  block can start normally. Disabling scheduling and allowing the scheduler to
  observe it before re-enabling also clears the suppression.
- Session and settings updates use a shared file lock and atomic JSON replacement.
  Every PC writing to the same folder should use this version; older versions do
  not participate in locking. Shared-drive behavior still needs testing on the
  deployment's Windows/network filesystem.

## Weekly Capture Timetable

In Settings, enable automated capture and edit the **Weekly recording timetable**.
Each column is a weekday (Monday–Sunday), and each row is a half-hour period.
Orange blocks record; dark blocks do not. Click to toggle a block, or drag a
rectangle to switch a range of times/days on or off. Keyboard users can Tab to a
block and press Space or Enter. Scroll within the grid to reach all 24 hours.

Use **Weekdays 09:00–15:30**, **Copy Monday to all days**, or **Clear all** as starting
points. Press **Save settings** to apply the timetable. Capture interval and
unchanged-frame detection still apply to all recording blocks.

Schedules repeat weekly using the capture computer's local clock. A 09:00 block
covers 09:00 up to, but not including, 09:30. Adjacent blocks stay in one session,
including across midnight. Gaps stop capture. The scheduler checks every 30
seconds, so starts/stops or saved changes can take up to one polling interval to
be observed. Stop suppresses the current continuous block until the next distinct
block. An entirely selected week has no gaps; after stopping it, disable the
schedule, let the scheduler observe that, then re-enable it to restart automation.
Manual capture remains independent of the timetable.

Existing daily start/end settings continue working unchanged until settings are
saved in the new editor. Their grid preview covers the same hours every day,
rounding partial half-hours outwards. Saving replaces the daily schedule with
the selected weekly blocks. An empty timetable schedules no capture.
