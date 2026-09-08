# Panoptix Manual Test Checklist

## 0. Install

- [ ] Run `dist\Panoptix-Setup-<version>.exe` on the test PC.
- [ ] Accept the SmartScreen `More info` -> `Run anyway` prompt.
- [ ] Confirm the install completes without admin rights.
- [ ] Confirm Panoptix appears in the Start menu.
- [ ] Confirm the desktop shortcut appears if the task was ticked.

## 0b. Desktop Shortcut

- [ ] Confirm the desktop shortcut exists after install.
- [ ] Right-click it, choose Properties, and note the Target path.
- [ ] Confirm a file actually exists at that path.
- [ ] Double-click the shortcut and confirm Panoptix starts.
- [ ] If Windows asks you to locate the file, open Windows Security, go to
      Protection history, and check whether Panoptix.exe was quarantined.
- [ ] Record which install option you chose, `Just me` or `All users`.

## 1. Launch

- [ ] Open Panoptix from the Start menu (or `dist\Panoptix.exe` for an unpackaged build).
- [ ] Confirm dashboard opens at `http://127.0.0.1:8765`.
- [ ] Confirm sidebar shows Home, Evidence Capture, Observation Mode, Sessions, Settings.
- [ ] Confirm Home shows the `Background Status` panel.
- [ ] Confirm status pill says `Idle`.

## 2. Settings

- [ ] Go to Settings.
- [ ] In the weekly timetable, choose different half-hour blocks on different weekdays.
- [ ] Set passive interval to `5`.
- [ ] Toggle `Skip unchanged passive screenshots` on.
- [ ] Set change threshold to `4`.
- [ ] Set manual hotkey to `<ctrl>+<alt>+p`.
- [ ] Toggle manual hotkey on.
- [ ] Toggle Windows startup on.
- [ ] Save settings.
- [ ] Toggle Windows startup off again if you do not want it staying enabled.
- [ ] Set export folder to a real folder you can find easily, using `Browse folder`.
- [ ] Save settings.
- [ ] Refresh the page.
- [ ] Confirm settings persisted.

## 2b. Screenshot Storage Folder

- [ ] Go to Settings.
- [ ] Find the `Screenshot storage folder` card.
- [ ] Confirm `In use now` shows the current folder.
- [ ] Click `Browse folder`.
- [ ] Confirm the Windows folder picker opens.
- [ ] Choose a network folder the admin PC can also reach.
- [ ] Click `Save screenshot folder`.
- [ ] Confirm `In use now` switches to the network folder without restarting.
- [ ] Capture a session.
- [ ] Confirm screenshots appear in the network folder from the admin PC.
- [ ] Start a recording, then try to change the folder.
- [ ] Confirm Panoptix asks you to stop the recording first.
- [ ] Close and reopen Panoptix.
- [ ] Confirm `In use now` still shows the network folder.
- [ ] Disconnect from the network or rename the folder.
- [ ] Restart Panoptix.
- [ ] Confirm Home shows the `Screenshot folder warning` and the app still runs.
- [ ] Restore the folder and restart.
- [ ] Click `Use default folder` to go back to local storage if needed.

## 3. Export Folder Fallback

- [ ] In Settings, set export folder to an invalid or unusable path, such as a path that points to a file instead of a folder.
- [ ] Save settings.
- [ ] Go Home.
- [ ] Confirm `Export folder warning` appears.
- [ ] Set export folder back to a valid folder.
- [ ] Save settings.
- [ ] Confirm warning disappears.

## 4. Evidence Capture

- [ ] Go to Evidence Capture.
- [ ] Fill in CYP initials.
- [ ] Fill in activity.
- [ ] Fill in staff member.
- [ ] Select purpose.
- [ ] Add privacy note.
- [ ] Start capture.
- [ ] Confirm active banner appears.
- [ ] Click around a few times.
- [ ] Confirm screenshot count increases.
- [ ] Stop recording.
- [ ] Confirm session appears in Sessions.

## 4b. Multiple Monitors

Skip this section on a single-screen PC.

- [ ] Confirm Windows is extending the desktop across all screens, not duplicating.
- [ ] Start an evidence capture.
- [ ] Click something on the primary screen.
- [ ] Click something on each secondary screen.
- [ ] Stop the capture and open the session.
- [ ] Confirm every screenshot shows all screens side by side, not just the primary one.
- [ ] Confirm the red click marker sits on the thing you actually clicked, on every screen.
- [ ] Repeat with a screen arranged to the left of, or above, the primary one.
- [ ] Confirm the markers are still in the right place.
- [ ] Export the session and confirm the images in the export match what you saw on screen.

## 5. Evidence Review

- [ ] Open the evidence session.
- [ ] Confirm screenshots load.
- [ ] Add title to a screenshot.
- [ ] Add staff note.
- [ ] Add CYP quote.
- [ ] Add tags.
- [ ] Mark one screenshot as highlight.
- [ ] Untick `Include in export` on one screenshot.
- [ ] Save notes.
- [ ] Leave and reopen the session.
- [ ] Confirm notes persisted.
- [ ] Confirm highlight persisted.
- [ ] Confirm export selection persisted.

## 6. Click Marker Editing

- [ ] Open a click screenshot.
- [ ] Change marker shape to circle.
- [ ] Change marker shape to square.
- [ ] Change marker shape to crosshair.
- [ ] Change marker shape to arrow.
- [ ] Change marker colour.
- [ ] Change marker size.
- [ ] Change marker stroke.
- [ ] Click `Update marker`.
- [ ] Confirm screenshot updates.
- [ ] Confirm marker looks correct.
- [ ] Reopen session.
- [ ] Confirm updated marker persisted.

## 7. Redaction

- [ ] Apply `Top strip`.
- [ ] Apply `Bottom strip`.
- [ ] Apply `Left strip`.
- [ ] Apply `Right strip`.
- [ ] Use `Apply redaction box` with custom X/Y/Width/Height.
- [ ] Confirm black boxes appear.
- [ ] Confirm redaction history appears.
- [ ] Click `Undo redactions`.
- [ ] Confirm original screenshot is restored.

## 8. Review Filters

- [ ] Search by note.
- [ ] Search by quote.
- [ ] Search by tag.
- [ ] Search by screenshot type.
- [ ] Test `All screenshots`.
- [ ] Test `Highlights only`.
- [ ] Test `Selected`.
- [ ] Test `Not selected`.
- [ ] Test `Redacted`.
- [ ] Test `Clicks`.
- [ ] Test `Observations`.
- [ ] Test `Select all`.
- [ ] Test `Select none`.
- [ ] Test `Select highlights`.

## 9. Export Evidence

- [ ] Export HTML/PDF.
- [ ] Confirm files appear in configured export folder.
- [ ] Open HTML export.
- [ ] Confirm notes and images are present.
- [ ] Open PDF export.
- [ ] Confirm PDF is readable.
- [ ] Export evidence pack.
- [ ] Verify evidence pack.
- [ ] Confirm verification passes.
- [ ] Export selected annotated images.
- [ ] Export selected clean images.
- [ ] Export both image versions.
- [ ] Confirm unselected screenshots are excluded.

## 10. Observation Mode

- [ ] Start Observation Mode.
- [ ] Set interval to `5`.
- [ ] Wait for a few screenshots.
- [ ] Pause.
- [ ] Confirm screenshot count stops increasing.
- [ ] Resume.
- [ ] Confirm screenshot count increases again.
- [ ] Stop.
- [ ] Open session.
- [ ] Confirm periodic screenshots are listed.

## 11. Passive Background Capture

- [ ] In Settings, enable scheduled passive capture.
- [ ] Select a timetable block for the current weekday and time.
- [ ] Set interval to `5`.
- [ ] Enable change detection.
- [ ] Wait up to 30 seconds for the scheduler to check the timetable.
- [ ] Confirm Home active banner says `Background Capture`.
- [ ] Confirm screenshots are captured.
- [ ] Leave screen static.
- [ ] Confirm `Skipped unchanged frames` increases.
- [ ] Change something on screen.
- [ ] Confirm a new screenshot is saved.

## 12. Manual Hotkey

- [ ] Enable manual hotkey.
- [ ] Start passive background capture or evidence capture.
- [ ] Press configured hotkey.
- [ ] Confirm screenshot count increases.
- [ ] Open session.
- [ ] Confirm event type is manual hotkey/autonomy capture.

## 13. System Tray

- [ ] Confirm Panoptix tray icon appears.
- [ ] Test tray `Open dashboard`.
- [ ] Test tray `Start passive capture now`.
- [ ] Test tray `Pause`.
- [ ] Test tray `Resume`.
- [ ] Test tray `Manual screenshot`.
- [ ] Test tray `Stop capture`.
- [ ] Confirm dashboard status updates after tray actions.

## 14. Startup

- [ ] Enable `Open Panoptix with Windows startup`.
- [ ] Save settings.
- [ ] Confirm Home/Settings shows Windows startup as requested/installed.
- [ ] Restart Windows when convenient.
- [ ] Confirm Panoptix launches after login.
- [ ] Disable startup if you do not want it permanent.

## 15. Storage And Retention

- [ ] Go to Settings.
- [ ] Confirm Local Storage total appears.
- [ ] Set retention days low only if using test sessions.
- [ ] Click cleanup.
- [ ] Preview the list and confirm old sessions move to Deleted sessions.
- [ ] Confirm recent sessions remain.
- [ ] Confirm Settings reports the MB held by deleted sessions.
- [ ] In Deleted sessions, use **Delete permanently** on one entry and confirm the
      Local Storage total drops by roughly that session's size.
- [ ] Confirm the retention preview lists deleted sessions past the retention
      period under permanent removal, and that confirming frees their space.

## 16. Delete Safety

- [ ] Delete one test event.
- [ ] Confirm it disappears.
- [ ] Confirm remaining events reindex properly.
- [ ] Delete one test session.
- [ ] Confirm it disappears from Sessions.
- [ ] Confirm unrelated sessions remain.
- [ ] Open Deleted sessions and restore the removed session, including its images and notes.
- [ ] Create a folder by hand inside the data folder's `trash` directory and confirm
      Deleted sessions still lists real entries and new recordings still start.

## 17. Restart Persistence

- [ ] Close Panoptix.
- [ ] Reopen Panoptix.
- [ ] Confirm settings persist.
- [ ] Confirm previous sessions persist.
- [ ] Confirm export folder still points where expected.
- [ ] Confirm dashboard status panel still renders properly.

## Bugs To Note

- [ ] Screenshot count does not change when it should.
- [ ] Skipped unchanged frames does not increase on a static screen.
- [ ] Hotkey does not fire.
- [ ] Startup says installed but does not launch.
- [ ] Export goes somewhere unexpected.
- [ ] Screenshots are written somewhere other than the configured screenshot folder.
- [ ] Folder picker does not open or returns the wrong path.
- [ ] Redaction cannot be undone.
- [ ] Marker changes damage the original image.
- [ ] Tray controls and dashboard disagree.
- [ ] Dashboard shows active recording after stop.
- [ ] Session data disappears after restart.

## Regression Checks After The Repository Review

- [ ] Redact a click screenshot, change its marker, and confirm the black boxes remain.
- [ ] Export a default evidence pack and confirm it contains no `_original.png` files.
- [ ] Explicitly include originals and confirm the unredacted-data warning appears.
- [ ] Exclude an event with a distinctive note; confirm that note is absent from image-ZIP metadata.
- [ ] Capture three screenshots, remove the first from the report during recording,
      then capture another. Confirm the retained screenshots have not changed.
- [ ] Edit notes on two screenshots, save one, change filters and navigate away/back.
      Confirm the other draft remains. Confirm export saves both notes.
- [ ] Filter out all selected screenshots, then export annotated images. Confirm
      the selected images still export.
- [ ] Simulate an unwritable export destination and confirm a failure is shown,
      without a success message.
- [ ] Open a PDF containing CYP, activity, staff and purpose; confirm all metadata
      appears inside the page margins.
- [ ] Try deleting the active recording's session; confirm deletion is rejected.
- [ ] Disconnect screenshot storage during capture. Confirm the dashboard shows
      a failure and a new recording can start after storage is restored.
- [ ] Pause evidence capture through the tray; confirm clicks and hotkeys save nothing.
- [ ] Start manual passive capture with scheduling disabled; confirm it stays running
      beyond the scheduler's 30-second poll.
- [ ] Stop a scheduled session during its window; confirm it stays stopped through
      subsequent polls and can start in the next separate scheduled block.
- [ ] Open the app from source with Windows startup enabled; confirm the startup
      command launches `panoptix.py` as well as Python.
- [ ] From two PCs using the updated version and the same network folder, save notes
      while capturing. Confirm notes, events and images are retained correctly.

## Review Shortcuts

- [ ] Export a session, click Open export folder, and confirm the correct folder opens in Explorer.
- [ ] Edit two screenshot notes; confirm the unsaved count is two. Hide one with a
      filter, click Save all notes, and confirm both changes persist after reload.
- [ ] Search sessions by activity and mode. Set the same From and To date and
      confirm sessions from that date are included. Clear filters.
- [ ] Open Zoom / drag to redact; test Fit, 100% and 200%, including scrolling.
      Draw in both directions, clear a selection, then apply one. Confirm the
      correct region is blacked out in Review and the annotated export.
- [ ] Open retention preview and cancel; confirm nothing moved. Open it again and
      confirm; restore a session from Deleted sessions and verify its saved notes,
      original images, redactions and local exports remain intact.

## Weekly Timetable

- [ ] Open Settings and confirm the previous daily schedule is reflected across the week.
- [ ] Clear the grid; drag a rectangle across Monday–Wednesday from 09:00–10:30.
- [ ] Toggle one Tuesday block off using a click, then toggle another with Space.
- [ ] Save, reload, and confirm each weekday's blocks persist independently.
- [ ] Test the weekday preset and Copy Monday to all days, including weekends.
- [ ] Schedule two separated blocks today; confirm capture stops in the gap and
      starts a new session in the next block (allow up to 30 seconds for polling).
- [ ] Schedule adjacent blocks and confirm they share a single recording session.
- [ ] Stop during an active block; confirm automation stays stopped until the next
      separate block. Manual capture should still be available.
- [ ] Confirm an empty timetable does not start automated capture.
