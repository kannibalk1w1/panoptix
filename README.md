# Panoptix

Local AP evidence capture tool.

## Download

Windows builds are attached to each release on the
[Releases page](https://github.com/kannibalk1w1/panoptix/releases/latest):

- **Panoptix-Setup-<version>.exe** — installer, adds shortcuts and optional startup.
- **[Panoptix.exe](https://github.com/kannibalk1w1/panoptix/releases/latest/download/Panoptix.exe)** — single file, no install.

Windows downloads are for 64-bit Windows. The binaries are unsigned, so SmartScreen warns on first run;
choose **More info** then **Run anyway**. Each release lists SHA-256 checksums.

## CachyOS / Arch Linux (KDE Plasma)

Native x86_64 Linux downloads are attached to Linux-enabled releases:

- `panoptix-<version>-1-x86_64.pkg.tar.zst`: install using
  `sudo pacman -U ./panoptix-<version>-1-x86_64.pkg.tar.zst`, then launch Panoptix
  from the application menu or run `panoptix`.
- `panoptix-<version>-linux-x86_64.tar.gz`: extract, install system dependencies
  `sudo pacman -S --needed spectacle kdialog xdg-utils python-pyqt6`, then run `./panoptix`
  inside the extracted folder. Keep the `_internal` folder alongside the binary.

On KDE Wayland, screenshots use Spectacle rather than Xwayland. Caption and folder
prompts use KDialog. Spectacle startup and PNG encoding limit the achievable frame
rate; the configured rate remains a target. Timings are saved with the frames.
Data defaults to `~/.local/share/panoptix` and configuration to
`~/.config/panoptix`; XDG overrides and PANOPTIX_DATA_DIR/PANOPTIX_CONFIG_DIR are
supported. Start at login uses a standard XDG autostart desktop entry.

In **Plasma Settings → Keyboard → Shortcuts**, add these commands with your chosen
key combinations (keep Panoptix running):

| Command | Suggested shortcut | Action |
| --- | --- | --- |
| `panoptix --caption` | Ctrl+Alt+N | Caption the next capture |
| `panoptix --clip` | Ctrl+Alt+R | Record a timed clip |
| `panoptix --capture` | Ctrl+Alt+P | Manual screenshot in an active session |

These desktop shortcuts apply on Wayland instead of the pynput hotkey settings.
The portable archive requires an absolute path to its `panoptix` executable in
shortcut commands.

### Capture on click under KDE Wayland

Install the optional `panoptix-kwin-click` package matching your **exact KWin
version**, then enable **Panoptix click capture** under **System Settings →
Window Management → Desktop Effects**. Start an Evidence Capture session in
Panoptix; the dashboard reports whether the click bridge is connected. It can
take about one second for a newly started session to reach the extension.

The extension observes left-button presses in KWin and asynchronously forwards
positions to Panoptix on localhost, only while the session is active. It does not
intercept clicks or request access to raw keyboard/input devices. Panoptix checks
pause, session identity and caption-popup state again before collecting an image.
Markers account for desktop scaling and monitors left/above the primary screen.

KWin plugin interfaces can change between updates. The optional package pins its
KWin dependency; rebuild it for a new KWin before upgrading. Source is included
in the portable archive under `kwin-click-source`, and in the installed app under
`/usr/share/panoptix/kwin-click-source`. To compile from the repository on CachyOS:

```bash
sudo pacman -S --needed base-devel cmake ninja extra-cmake-modules kwin vulkan-headers
bash scripts/build_kwin.sh 2.2.0
sudo pacman -U dist/panoptix-kwin-click-*.pkg.tar.zst
```

The extension is optional and disabled by default. X11 sessions continue using
the regular global mouse/keyboard hooks.

### Build Linux packages from source

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt pyinstaller
PANOPTIX_BUILD_PYTHON=.venv/bin/python bash scripts/build_linux.sh 2.2.0
```

This writes a portable archive and native Arch package to `dist`. Use
`--archive-only` as the second argument when `makepkg` is unavailable. Build on
CachyOS/Arch for its current libraries, or use the Linux GitHub Actions workflow.
Other Wayland compositors are not supported by the KDE capture backend.

## Run

From source:

```powershell
python C:\Users\Public\panoptix\panoptix.py
```

Then open:

```text
http://127.0.0.1:8765
```

## Close And Quit

Closing the browser dashboard leaves Panoptix running for background capture.
Use **Quit Panoptix** in the tray menu or dashboard sidebar to exit the application,
stop capture and finish any in-progress clip. The tray icon is hidden during
shutdown. You can also run `panoptix --quit` on Linux (or `Panoptix.exe --quit` on
Windows). Linux uses a native Qt/KDE tray icon with a right-click menu, including Quit.
The native Arch package installs python-pyqt6 for this integration.

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
- Retention preview and recoverable removal of sessions older than the configured retention period, with permanent deletion once a removed session is itself past that period.
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
  removed and the deleted sessions that would be permanently purged. Confirming
  moves only those still-eligible sessions to **Deleted sessions**, which is also
  accessible from the Sessions page.
- Session removal keeps saved notes, screenshots and local exports under the
  current data folder's `trash` directory. **Restore** returns them to Sessions
  without overwriting an existing session. Exports in separately configured
  folders are not moved. Unsaved browser drafts are not part of a deleted backup.
- Deleted sessions keep using disk until they are purged. Settings reports how
  much they hold, **Delete permanently** removes one, **Permanently delete all**
  empties the list, and retention cleanup purges any deleted more than the
  retention period ago. Purging cannot be undone. A session whose `session.json`
  is missing cannot be restored but can still be purged.

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

## LMS Content Capture Mode

Choose **LMS Content Capture** beside Evidence Capture and Observation Mode.
Enter a lesson title, course/module, author and learning objective/context. Choose
clip duration, target frame rate and GIF output for this lesson. Screenshot and
clip shortcuts continue to work, using these lesson settings.

Manual screenshots are the default. Enable **Automatically capture left clicks**
when you want a screenshot for each action; KDE Wayland uses the existing KWin
click extension. There is no automatic interval capture in LMS mode.

The active lesson screen provides **Caption next capture**, **Capture screenshot**,
**Record clip**, **Open lesson clips folder**, and **Finish and review**. Captions
apply once, and the lesson context remains attached to the session. Pausing or
finishing the lesson finishes its current clip. Resume to collect more content.

Screenshots appear in Sessions/Review and the existing HTML/PDF and image exports.
Lesson clips are grouped under `clips/<session-id>/<clip-id>/`, retaining GIFs,
original PNG frames and metadata including the course, lesson, context and caption.
Review also has an **Open lesson clips folder** button. Clip files remain separate
from screenshot report/evidence-pack exports and session retention cleanup.

## Caption The Next Capture

Enable **Settings → Caption next capture → Enable caption popup hotkey**, then
save. **Ctrl+Alt+N** opens a native caption prompt over the application
you are using. Enter a title/instruction such as **Open file** and, optionally,
a context note explaining what the capture is for. Press **Enter** from the
title field (or click **Save for next capture**), then perform the action.
KDE uses separate title and multiline context prompts; cancelling either keeps
the original pending caption.
**Escape** or **Cancel** closes the popup without changing any pending caption.
The context field supports multiple lines; use the Save button to confirm it.

The text attaches once to the next click screenshot in an active Evidence
Capture session, manual screenshot, or newly started clip. It does not take a
screenshot itself. Automatic interval screenshots leave the caption pending.
While the popup is open, screenshot capture waits and clicks inside the popup
are ignored. Close/finish an active clip before opening the popup.

Screenshot titles and notes appear in Review and the existing HTML/PDF reports.
Clip titles and notes are stored in `clip.json`; originals remain available for
adding visual overlays later. On Home, **Caption next capture** opens the same
popup, the pending text is shown, and **Clear pending caption** discards it.
Pending captions last until consumed, cleared, the storage folder changes, or
Panoptix exits. A failed screenshot save leaves the caption pending for retry.

## LMS Screen Clips

On **Home**, use **Record clip**, or enable **Settings → LMS screen clips →
Enable clip hotkey** and save. The default shortcut is **Ctrl+Alt+R**. Panoptix
must be running; no evidence session needs to be active. The clip records the
next 30 seconds by default, then stops automatically. **Finish clip early** on
Home stops capture and exports what has been recorded. Repeated shortcut presses
while recording or exporting are ignored.

Settings lets you choose a duration from 1–120 seconds, a target frame rate from
1–30 fps (default 5), and whether to also create a looping GIF. Capture covers all
monitors without audio. Slow screen capture or storage may produce fewer frames;
the GIF uses the actual frame timestamps so playback keeps the captured timing.

**Open clips folder** on Home opens `clips` inside the configured screenshot
storage folder. Each timestamped clip folder contains:

- `frames/frame_000000.png`, etc.: full-resolution originals for overlays/editing.
- `clip.json`: requested settings, elapsed duration and per-frame timestamps.
- `clip.gif`: optional looping preview, resized to fit within 960 × 960 pixels.

PNGs remain available if GIF export fails. GIFs have a 256-colour palette per
frame; use the original PNGs when editing or when full image quality matters.
Clips are separate from evidence sessions, review annotations and evidence
exports. They count toward storage usage but are not removed by session retention
cleanup; remove unwanted clip folders manually. Wait for a clip to finish
exporting before changing the screenshot storage folder.

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
