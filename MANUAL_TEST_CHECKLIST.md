# Panoptix Manual Test Checklist

## 1. Launch

- [ ] Open `dist\Panoptix.exe`.
- [ ] Confirm dashboard opens at `http://127.0.0.1:8765`.
- [ ] Confirm sidebar shows Home, Evidence Capture, Observation Mode, Sessions, Settings.
- [ ] Confirm Home shows the `Background Status` panel.
- [ ] Confirm status pill says `Idle`.

## 2. Settings

- [ ] Go to Settings.
- [ ] Change passive capture window start/end time.
- [ ] Set passive interval to `5`.
- [ ] Toggle `Skip unchanged passive screenshots` on.
- [ ] Set change threshold to `4`.
- [ ] Set manual hotkey to `<ctrl>+<alt>+p`.
- [ ] Toggle manual hotkey on.
- [ ] Toggle Windows startup on.
- [ ] Save settings.
- [ ] Toggle Windows startup off again if you do not want it staying enabled.
- [ ] Set export folder to a real folder you can find easily.
- [ ] Save settings.
- [ ] Refresh the page.
- [ ] Confirm settings persisted.

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
- [ ] Set the daily window to include the current time.
- [ ] Set interval to `5`.
- [ ] Enable change detection.
- [ ] Wait 10-20 seconds.
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
- [ ] Confirm old sessions are deleted.
- [ ] Confirm recent sessions remain.

## 16. Delete Safety

- [ ] Delete one test event.
- [ ] Confirm it disappears.
- [ ] Confirm remaining events reindex properly.
- [ ] Delete one test session.
- [ ] Confirm it disappears from Sessions.
- [ ] Confirm unrelated sessions remain.

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
- [ ] Redaction cannot be undone.
- [ ] Marker changes damage the original image.
- [ ] Tray controls and dashboard disagree.
- [ ] Dashboard shows active recording after stop.
- [ ] Session data disappears after restart.
