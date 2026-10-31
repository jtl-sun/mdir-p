# mDIR-P 2.26.48

- Rename the standard theme to **mDir theme (basic)** and make it the default for new installations/missing settings.
- Present all 24 themes in the requested non-alphabetical order in the existing searchable F10 > Theme palette.
- Preserve existing theme preference and migrate historical names automatically.
- Retain active/inactive pane contrast, thumbnail shortcuts and file-manager functions.

# mDIR-P 2.26.47

- Rename the historical `old_M_tema` display theme to **Old-MDIR**, including persisted-setting backward compatibility.
- Distinguish working and passive panes consistently in Old-MDIR, Norton Commander and Textual Light: dimmer passive text and backgrounds, contrasting active selection and borders.
- Retain modern mDir active #191919/inactive #292929 backgrounds, vintage color palettes and existing file operations.
- Preserve Ctrl+T thumbnail shortcut, Alt+A-Z drive switching and personal configuration.

# mDIR-P 2.26.46

- Fix inverted active/inactive pane brightness in the standard dark mDir theme: active #191919, inactive #292929.
- Apply the difference to the full file-list surface, focused DataTable rows, information area, and footer strip; active focus border and selected-row contrast stay intact.
- Scope new colors to the mDir dark theme so DOS Original/Norton and other themes remain unchanged.
- Move Thumbnail/List shortcut to Ctrl+T (from Ctrl+Alt+T); Alt+T remains T: drive.
- Preserve user settings, file operations and all Alt+A-Z drive shortcuts.

# mDIR-P 2.26.45

- All Alt+A through Alt+Z now switch the **active** pane to the corresponding available Windows drive (including T:).
- Fix keyboard inconsistency: register these shortcuts in both Textual bindings and Windows native keyboard routing.
- Move Thumbnail/List from Alt+T to Ctrl+Alt+T to avoid a conflict; Th button remains available.
- Keep F9 Zip/Unzip, Alt+F9 drive picker, file management operations and personal settings.

# mDIR-P 2.26.44

- Alt+C/D/S and other non-reserved Alt+drive letters directly switch the active Windows pane to that drive's root; Alt+T remains reserved for thumbnails.
- F9 now shows **Zip/Unzip** and automatically chooses compression for selected files/folders or extraction for a single selected ZIP.
- Create ZIP and Extract ZIP reuse existing safe progress/cancel/overwrite dialogs; destination defaults to the opposite pane.
- Existing Drive picker moves to Alt+F9. Alt+F1/F2 pane pickers, Alt+F5/Alt+F6 archive shortcuts remain.
- Previous saved Drive=F9 custom keymaps migrate while retaining unrelated remappings.
- ZIP-only built-in archive support; unsupported RAR/7z/TAR extraction reports a clear message.

# mDIR-P 2.26.43

- F6 RenMov pre-fills the original filename or folder name for one selected item, appended to the opposite pane's destination path.
- Multiple selections pre-fill only the destination directory.
- A single folder with an existing same-named target is treated as a collision, never silently nested one level deeper.
- Existing F2, Space and Backspace shortcuts and overwrite confirmation remain unchanged.

# mDIR-P 2.26.42

- Hide Parent, Space Mark and F2 Rename from the function-key footer, keeping all three shortcuts functional.
- F6 is now **RenMov**, a combined name/destination prompt for rename or move.
- Default to opposite pane for moves; accept a filename for in-place rename or a complete path for move+rename.
- Preserve overwrite warnings, prevent directory self-moves and reject missing parent directories.
- Keep full-width equal-size footer cells, both DOS skins, settings and previews.

# mDIR-P 2.26.41

Active pane now stands out more clearly via a brighter cursor and cyan outline. Function-key buttons occupy equal widths across the full-width footer, with centered labels. Mouse targets retain their three-row height and safety padding; narrow windows scroll. Existing themes, keyboard shortcuts and file operations are preserved.

---

# mDIR-P 2.26.40 (verified skin-switch release)\n\nThis release incorporates the final skin activation and regression fixes tested on the main branch. It supersedes v2.26.39, which was published from an intermediate commit. The original default green path bar and the built-in Light Theme are preserved; the retro-specific path and pane CSS activates only when the relevant skin is selected.

## mDir Original and Norton Commander skins

- **old_M_tema** now closely follows the original DOS Mdir: pure black file areas, coral/red directory names, red highlight with black text, BAT yellow, COM cyan, EXE green, ZIP magenta, gray path bar, and cyan borders/footer.
- **Norton Commander** is a new selectable skin with royal-blue dual panes, cyan frames, yellow headers, bright cyan selection with dark text, and classic teal function-key hints.
- Fixed the left/inactive-pane selection readability problem across *all* themes. Selected filename, extension, size and date segments now receive consistent, high-contrast foreground/background colors, even if their filenames have extension-specific Rich markup.
- Reuses existing mDIR-P functionality, keyboard mappings, options, persisted theme preference, file operations and personal shortcuts. No separate font or program is required.

Select **F10 -> Theme** and choose **old_M_tema** or **Norton Commander**. The original **mDir theme** remains the default for new installations. Personal link configuration is not included in releases.

Install: close mDIR, extract `mDIR-P-2.26.40.zip`, run `INSTALL_MDIR.bat`, and restart.

---

# mDIR-P 2.26.38

## Config is now visible in the mDIR installation folder

Personal top-bar links are now stored at:

`%LOCALAPPDATA%\mDIR\Config\shortcuts.json`

This is the same persistent mDIR installation root that contains the installed `venv`, `bin`, and icon, so the file is much easier to find and back up.

### Link Manager improvements

**Edit Links** now displays the exact JSON path and provides **Open Config Folder**. The Windows installer also prints the Config folder and Link settings path after a successful install.

### Safe migration

When the new file does not yet exist, mDIR checks the 2.26.37 location first:

`%LOCALAPPDATA%\mDIR-P\Config\shortcuts.json`

and then the older:

`%USERPROFILE%\.mdir-p-shortcuts.json`

A valid shortcut list is copied into the install-root Config folder. Existing `%LOCALAPPDATA%\mDIR\Config\shortcuts.json` is never overwritten, and older files are left in place as backups.

### GitHub privacy remains enforced

Personal shortcut JSON is still excluded from Git and official Releases. CI rejects known private shortcut paths if they are accidentally tracked, and release ZIPs are built with `git archive HEAD`.

Install: close mDIR, extract `mDIR-P-2.26.38.zip`, run `INSTALL_MDIR.bat`, and restart. After installation, **Edit Links -> Open Config Folder** opens the backup location directly.

---

# mDIR-P 2.26.37

## Personal links stay personal

mDIR-P now keeps the top shortcut bar configuration in a dedicated per-user location:

`%LOCALAPPDATA%\mDIR-P\Config\shortcuts.json`

This file is outside the program source and outside the GitHub repository. Updating mDIR therefore does not require re-entering links, and another user who downloads the public Release receives only the portable built-in defaults.

### Automatic migration

If an existing `%USERPROFILE%\.mdir-p-shortcuts.json` is found and the new config does not yet exist, mDIR copies the validated links into the new location automatically. The old file is left in place as a backup.

### Release privacy

Personal shortcut/config filenames are explicitly ignored by Git. The official source ZIP is produced with `git archive HEAD`, which packages only committed files; local untracked JSON settings cannot enter the Release.

The `MDIR_P_SHORTCUTS` environment variable remains available for advanced users who intentionally want a custom shortcut JSON location.

Install: close mDIR, extract `mDIR-P-2.26.37.zip`, run `INSTALL_MDIR.bat`, and restart. Existing personal links should appear automatically.

---

# mDIR-P 2.26.36

## old_M_tema

This release adds a retro `old_M_tema` to the existing Theme selector. It is inspired by the classic DOS Mdir III color language but keeps the current mDIR-P layout and all 2.26.35 behavior intact. The default theme is unchanged.

- Black file workspace with cyan/teal interface bars.
- Red active-row cursor for an unmistakable DOS-style focus point.
- EXE green, COM cyan, BAT/CMD yellow, and PowerShell PS1 magenta.
- AI/File, Preview, Search, dialogs and thumbnail chrome continue to follow the selected theme through the existing theme pipeline.
- Select it with **F10 -> Theme -> old_M_tema**. The chosen theme is saved per user and restored on the next launch.

## Version identity

mDIR-P will continue in the **V2.xx.xx** series rather than moving to V3.x. This keeps the modern project visually and historically distinct from Choi Jung-han's classic Mdir III 3.x line while acknowledging its inspiration.

Install: close mDIR, extract `mDIR-P-2.26.36.zip`, run `INSTALL_MDIR.bat`, and restart. Verify `2.26.36` in the title.

---

# mDIR-P 2.26.35

Background now keeps a small, movable desktop progress window visible while the main mDIR interface remains usable. The window displays filename, percentage, bytes, speed, ETA and item count, with Pause/Resume, Cancel and Foreground buttons. The close button returns to foreground progress. Ctrl+Alt+P also restores foreground progress. Completion closes the mini window automatically.

The mini window stays on top so it remains visible while navigating mDIR. Existing additional Copy/Move requests are queued, as before. This update does not add simultaneous transfer workers.

Windows requires Python's standard Tkinter component (included in normal python.org installations). If the window cannot start, foreground progress is restored. No extra pip dependency is needed.

Validation: 29 targeted regression tests passed on Windows, including actual Copy/Move workers, a live mini-window process, pause/resume/foreground commands, main pane switching and completion cleanup. The desktop window and Pause/Resume button were also inspected interactively using example progress data.

Install: close mDIR, extract mDIR-P-2.26.35.zip, run INSTALL_MDIR.bat and restart. Verify 2.26.35 in the title.

---

# mDIR-P 2.26.34

## Copy / Move Background and source cleanup

- Progress byte counts, speed and ETA no longer fail due to a Textual internal name collision.
- Background resumes a paused operation and closes its progress view. Ctrl+Alt+P reopens the running operation.
- Dismissed progress screens are detached so later updates and completion do not target an obsolete screen.
- Read-only files in an approved overwrite backup or moved source are made writable only when Windows rejects their removal. Locked files and ACL denials still report errors.
- Same-volume Move uses rename. Cross-volume Move copies into staging, publishes the complete destination, then removes the source. If source cleanup fails, the complete destination is retained and the failure is reported.

Close mDIR, extract this release to a new folder, run INSTALL_MDIR.bat, and restart mDIR. Check version 2.26.34 in the title.

The supplied second screenshot says Copy (9 completed, 9 errors), so it does not establish that a Move was dispatched. Its backup-removal WinError 5 is consistent with read-only files. This release tests both Copy and Move paths; it does not delete old source or .~mb-* folders from prior operations.

Validation: 33 targeted tests on Windows/Python 3.12/Textual 8.2.8, including real background Copy/Move workers. Cross-volume behavior is forced with EXDEV in tests; the user's E:/F: drives were not modified.

---

# mDIR-P 2.26.33

## More comfortable footer mouse controls

- Made the existing bottom function-key command bar **three terminal rows high** so mouse clicks work across the entire button height, not just the text line.
- Reserved **one blank row below the buttons**, keeping the mouse targets farther from the Windows taskbar / Ubuntu dock.
- Retained the existing button labels, colors, order, keyboard shortcuts and file operations.
- No new settings or menus. The layout change is deliberately minimal.

Close and reopen mDIR after updating. On Windows install the `mDIR-P-2.26.33.zip` release as usual; on Ubuntu use the corresponding DEB or source installer. The display remains dependent on the terminal's cell height and window size.

---

# mDIR-P 2.26.32

This update fixes accidental multi-row toggling from a single right click while preserving continuous Total Commander-style right-button drag selection.

## Right-click selection stability

- A stationary right click now toggles exactly one row.
- The right-drag controller remains idle until real pointer movement is detected.
- Textual click coordinates and native Windows pointer coordinates keep separate movement origins, preventing Windows Terminal grid-rounding differences from looking like movement.
- Edge scrolling does not start on MouseDown; it becomes active only after drag movement starts.
- Fast real drags still commit the final MouseUp row before the gesture closes.

## Preserved behavior

The 30 ms coalesced drag controller, one-toggle-per-row rule, skipped-row filling, distance-based edge acceleration, large-folder selection optimizations, Office PDF Preview, Recent Folders, native administrator delete, and the long-path Copy/Move support described below remain intact.

## Validation

Regression coverage now includes a stationary right-click case where native pointer sampling intentionally reports a neighbouring row. The selected or deselected state must remain limited to the clicked row. Actual Windows Terminal mouse behavior should still be confirmed manually.

## Long-path-safe file operations

- Copy/Move internally use Windows extended-length filesystem paths (`\\?\...`, including UNC handling) so deep children inherit long-path support during recursive operations.
- Safe staging and rollback names are now compact (`.~mc-*` / `.~mb-*`) instead of repeating the full destination name plus a 32-character UUID.
- Transient Windows `WinError 2/3` file-copy failures get at most two short retries, and only while the source still exists. Files that disappear from a live project are reported rather than silently omitted.
- The existing progress UI throttling remains in place, so normal copies do not gain extra repaint work.

## Preserved 2.26.30 fixes

Administrator-delete cancellation/partial-result handling, selected-link shell paths, queued Office Preview cancellation, late startup dialog focus protection, Recent Folders, Office PDF Preview, and native UAC delete behavior remain intact.

## Validation

The long-path helper/retry tests and the existing non-UI advanced file-operation tests pass in the build environment. Windows extended-path behavior still requires final manual confirmation on Windows with an actually deep project tree.

---

# mDIR-P 2.26.31

Unified progress reporting for file operations. Copy, Move, Delete, ZIP creation and extraction share a progress tracker and two-level progress dialog with live item/overall progress, processed bytes, average transfer speed, and ETA. File search shares the reporting model and shows actual scanned and matched counts without an invented percentage.

- Added Pause/Resume, Cancel and Background controls; `Ctrl+Alt+P` reopens an active background operation.
- Added chunk-level progress and cooperative cancellation for large transfers and ZIP operations.
- Preserved existing Copy/Move/Delete semantics, overwrite prompts, Trash/Recycle Bin handling and platform shortcuts.
- Added regression tests for progress, ZIP integrity, and cancellation.
- OS-managed Recycle Bin and some metadata-only moves cannot be interrupted mid-call.
- Test on a removable drive before applying to important data; no automatic rollback is promised for every OS-level error.

Download the mDIR-P 2.26.31 archive, close mDIR, extract it and run `INSTALL_MDIR.bat`. Personal settings are preserved.

---

# mDIR-P 2.26.30

Reviewed 2.26.29 and corrected administrator-delete cancellation/partial results, selected-link path handling, queued Office-preview cancellation, and late startup dialog focus.

---

# mDIR-P 2.26.29

Recent Folders is now a true click-through drop-down. While the list is open, one click anywhere outside it closes the list and immediately performs the action at the clicked location. The same `▼` button toggles the list closed without reopening it.

## mDIR-P 2.26.28

### One-click Recent Folders drop-down

- The `RF` text buttons introduced in 2.26.27 have been replaced by compact **`▼`** buttons at the far right of each pane's green directory path bar.
- Clicking `▼` once opens the recent-folder list immediately; there is no second Select/drop-down click.
- The list is anchored under the clicked path-bar button and shows the current folder with a check mark.
- Clicking a folder opens it immediately in that pane only. Up/Down + Enter also work.
- Left and right panes continue to share the same bounded MRU history while remaining independent navigation targets.
- `Alt+Down` still opens Recent Folders for the active pane.

### Upgrade

Close mDIR, extract `mDIR-P-2.26.28.zip`, run `INSTALL_MDIR.bat`, and reopen mDIR. Confirm that each pane shows a `▼` at the right end of its path bar and that one click opens the folder list directly.

---

## mDIR-P 2.26.27

### Recent Folders for both panes

- Each pane toolbar now includes an **RF** button for Recent Folders.
- The history is shared, newest-first, and bounded to 40 folders.
- Choosing a folder from the left RF button changes only the left pane; the right RF button changes only the right pane.
- `Alt+Down` opens the same list for the currently active pane.
- Folder history is persisted atomically under the mDIR-P per-user data folder.
- Ordinary background rescans do not reorder the list; only successful directory transitions are recorded.
- If a saved folder no longer exists, a failed reopen removes that stale entry.

### Upgrade

Close mDIR, extract `mDIR-P-2.26.27.zip`, run `INSTALL_MDIR.bat`, and reopen mDIR. Visit several folders in either pane, then use the **RF** button on each side to confirm that only the clicked pane navigates.

---

## mDIR-P 2.26.26

This update fixes the Windows Administrator/UAC prompt appearing only as a flashing taskbar item instead of opening in front of mDIR.

### UAC is now owned by the mDIR window

- mDIR forwards its real Windows Terminal top-level window handle into the native COM elevation request through `BIND_OPTS3.hwnd`.
- Immediately before requesting elevation, the terminal owner is restored and brought to the foreground on a best-effort basis.
- Windows can therefore associate the consent UI with the mDIR window instead of treating it as an unrelated background task.
- The native `IFileOperation` broker introduced in 2.26.25 remains unchanged; PowerShell is still not used and the main mDIR/Python process remains non-elevated.

### Delete safety is unchanged

- Protected normal files/folders still use the Recycle Bin.
- Only individual files already classified by mDIR as 10 GiB or larger use the existing permanent-delete policy.
- Cancelling UAC leaves the protected items untouched.

### Install and test

Close mDIR, extract `mDIR-P-2.26.26.zip`, run `INSTALL_MDIR.bat`, and reopen mDIR. Retry a protected item under `Program Files`. After **Continue (Admin)**, the Windows permission prompt should appear in front of mDIR rather than flashing only on the taskbar.

---

## mDIR-P 2.26.25

This update fixes Administrator delete retry on Windows systems where `powershell.exe` is blocked by security policy.

### Native Windows elevation instead of PowerShell

- The 2.26.24 elevated PowerShell broker has been removed from the Administrator delete path.
- After the existing mDIR confirmation, Windows now creates its own elevated FileOperation COM broker through the standard COM elevation moniker and displays UAC directly.
- The mDIR/Python process itself stays non-elevated. No privileged PowerShell command, temporary script, or elevated user-writable Python module is executed.

### Delete policy is unchanged

- Protected files/folders that normally belong in the Recycle Bin are still recycled, using Windows `IFileOperation` with `FOFX_RECYCLEONDELETE`.
- Only individual files already classified by mDIR as 10 GiB or larger keep the existing permanent-delete policy.
- Cancelling UAC leaves protected items in place. Partial success is checked against the actual filesystem and reported back in mDIR.

### Why this change was needed

On some Windows installations, security policy can allow UAC but block `powershell.exe` from starting with elevated rights. In that case 2.26.24 displayed a Windows message saying the specified device/path/file could not be accessed. 2.26.25 no longer depends on PowerShell for Administrator delete.

### Install

Close mDIR, extract `mDIR-P-2.26.25.zip`, run `INSTALL_MDIR.bat`, and reopen mDIR. Test the same protected `Program Files` item again; after **Continue (Admin)**, Windows UAC should be followed directly by the native Shell delete/recycle operation.

---

## mDIR-P 2.26.24

This update adds a Windows UAC elevation path for protected deletes, similar to Total Commander.

### Administrator retry only when needed

- `F8` still starts with the normal mDIR delete path. Small files/folders go to the Windows Recycle Bin and files 10 GiB or larger keep the existing permanent-delete policy.
- If Windows denies access to selected items (for example under `Program Files`), mDIR separates only those failed items and asks whether to retry them with Administrator permission.
- Choosing **Continue (Admin)** opens the normal Windows UAC prompt. The rest of mDIR is not relaunched as Administrator; a short-lived trusted Windows PowerShell broker receives only the protected paths.
- Cancelling the UAC prompt leaves those items untouched and returns to mDIR.

### Safer error handling

- The `SHFileOperationW` return value `0x78` is now shown as **Administrator permission is required** instead of the misleading `Windows error 120`.
- Other delete failures remain normal errors and are not automatically elevated.
- If an item still cannot be removed after elevation, mDIR reports that separately.
- The temporary elevated request is SHA-256 verified by the Administrator broker before any path is processed; the elevated process does not import Python/mDIR code from the user-writable installation.

### Install

Close mDIR, extract `mDIR-P-2.26.24.zip`, run `INSTALL_MDIR.bat`, and reopen mDIR. When deleting a protected item, accept the Windows UAC prompt only when you intend to remove that item.

---

## mDIR-P 2.26.23

This update extends the 2.26.22 PDF-first Office Preview design to PowerPoint.

### PowerPoint through PDF

- `PPT/PPTX` files are opened by a private Microsoft PowerPoint `DispatchEx` worker and exported with PowerPoint's own PDF engine.
- Presentations open read-only and without a presentation window, so mDIR does not attach to or modify the user's interactive PowerPoint session.
- The resulting PDF is rendered by the same mDIR PDF Preview path used for normal PDFs, preserving slide size, master layout, fonts, images and page geometry much better than text reconstruction.

### Speed

- PowerPoint stays warm in the private Office worker between previews.
- Converted presentations use the same LocalAppData cache keyed by path, size and modification time. An unchanged presentation normally reopens directly from the cached PDF.
- Fast cursor movement coalesces uncached Office requests, and changing selection cancels a superseded conversion.
- LibreOffice remains the headless fallback if Microsoft PowerPoint is unavailable or fails.

### Compatibility

- The old PPTX text extraction remains only as a last fallback when no PDF converter is available.
- Legacy `.ppt` requires Microsoft PowerPoint or LibreOffice when PDF conversion cannot be completed.

### Install

Close mDIR, extract `mDIR-P-2.26.23.zip`, run `INSTALL_MDIR.bat`, and reopen mDIR. No additional dependency is required beyond the `pywin32` Preview dependency already introduced in 2.26.22.

---

## mDIR-P 2.26.22

This update changes Excel and Word Preview to the same PDF-first concept used by xViewer, with extra caching and cancellation for mDIR's rapid file navigation.

### Excel and Word are rendered through PDF

- Excel `XLS/XLSX/XLSM/XLTX/XLTM` files are opened read-only by a private hidden Microsoft Excel COM worker and exported with Excel's own PDF engine.
- Word `DOC/DOCX` files use a private hidden Microsoft Word COM worker and Word's own PDF export.
- mDIR then renders the resulting PDF through the existing PyMuPDF/Poppler Preview path, so layout, fonts, cell placement, page setup and Word pagination are much closer to the original Office document than the old reconstructed preview.

### Speed strategy

- The private Office worker remains alive between previews, avoiding Excel/Word startup for every file.
- Converted PDFs are cached under the user's LocalAppData using the source path, size and modification time. Selecting an unchanged file again normally bypasses Office completely.
- Selecting another file cancels the previous non-cached Office conversion so a slow workbook cannot hold the Preview queue.
- Uncached native Office selections use a short 120 ms coalescing window so rapid cursor movement converts only the newest file; cached PDFs bypass that delay.
- Excel page setup uses the xViewer-style fit-to-page path, with one bounded retry using the workbook's original layout if page setup is the slow stage.
- LibreOffice is the private headless fallback when Microsoft Office is unavailable.

### Compatibility and safety

- Office automation uses `DispatchEx`, never the user's currently open Excel or Word process. Files are opened read-only, updates/macros/events are disabled where applicable, and hidden Office processes have real process handles so timeout/cancel cleanup cannot target a reused PID.
- Cache files are validated as complete PDFs and published atomically only after successful conversion. The cache is pruned to at most 900 files or 3 GiB.
- If no PDF converter is available, Excel falls back to the previous bounded grid renderer and DOCX falls back to the previous bounded text view. Legacy DOC still requires Word or LibreOffice.
- PowerPoint Preview is unchanged in this release.

### Install

Close mDIR, extract `mDIR-P-2.26.22.zip`, and run `INSTALL_MDIR.bat`. The Preview install now includes `pywin32` on Windows. Microsoft Office is used when installed; LibreOffice remains optional fallback software.

---

## mDIR-P 2.26.21

This update corrects the diagnosis of the remaining far-right blank strip seen in Windows Terminal.

### Actual cause

- The strip is outside Textual's renderable character grid. The screenshot shows the Header, both panes, and Footer all ending at the same x-coordinate before the strip.
- Windows Terminal reserves that host-side area for its profile scrollbar and padding. mDIR CSS cannot paint into it.
- The 2.26.20 `Screen { overflow: hidden; }` rule remains harmless, but it could not remove host UI outside the terminal grid.

### Dedicated mDIR Windows Terminal profile

- `INSTALL_MDIR.bat` now installs an official per-user Windows Terminal JSON fragment named **mDIR**.
- Only this mDIR profile uses `scrollbarState: hidden` and `padding: 0`; PowerShell, Command Prompt, Ubuntu, and other profiles are not modified.
- The desktop shortcut launches mDIR through `wt.exe -w -1 new-tab -p "mDIR"` when Windows Terminal is available.
- If Windows Terminal is unavailable, the shortcut falls back to launching the private mDIR Python environment directly.
- The `m` and `mdir` aliases remain direct commands inside the current terminal and therefore inherit that terminal profile's appearance.

### Install

Close mDIR, extract `mDIR-P-2.26.21.zip`, run `INSTALL_MDIR.bat`, then launch mDIR from the refreshed **desktop shortcut**. A newly opened mDIR Windows Terminal window should no longer reserve the host scrollbar/padding strip on the right.

---

## mDIR-P 2.26.20

This update removes the unused vertical gutter that could appear at the far right of the mDIR window.

### Full-width dual-pane layout

- The main Textual `Screen` is now explicitly non-scrollable because mDIR is a fixed dashboard layout rather than a vertically scrolling document.
- Textual therefore no longer reserves an application-level vertical scrollbar column at the far right.
- `#panes` explicitly uses the full available width, so the left/right panes extend into the reclaimed space.
- The file lists still keep their own DataTable scrollbars, so normal file-list scrolling is unchanged.

### Preserved behavior

- Right-button continuous drag selection and acceleration from 2.26.19 are retained.
- Large-directory selection batching from 2.26.17 is retained.
- Left/right pane independence and the two-tone Invert Selection buttons are retained.

### Install

Close mDIR, extract `mDIR-P-2.26.20.zip`, run `INSTALL_MDIR.bat`, and reopen mDIR. Python 3.11 or newer is required.

---

## mDIR-P 2.26.19

This update removes the remaining pause during continuous right-button drag selection in large folders.

### Continuous drag controller

- Right-button selection is no longer executed directly from every Windows Terminal `MouseMove` / `B3-Motion` event. Those events now only store the newest pointer position.
- One persistent controller runs every 30 ms and is solely responsible for advancing selection, sampling the physical Windows pointer, edge scrolling, and acceleration.
- Coalescing motion events prevents a fast stream of mouse messages from filling the Textual event queue and delaying the selection timer for several seconds.
- The drag therefore continues while the pointer is moving or stationary, instead of pausing during motion and catching up after the mouse stops.

### Edge acceleration

- Moving below or above the pane still accelerates by distance, up to the existing capped step.
- Moving horizontally outside the active pane pauses scrolling without destroying the gesture; returning resumes it.

### Preserved behavior

- Each crossed row toggles at most once per gesture.
- Fast motion fills skipped rows.
- Left/right panes stay independent.
- List and thumbnail modes continue to share the FilePane selection set.
- The 2.26.18 native pointer/release tracking, 2.26.17 large-directory batching, and 2.26.16 two-tone Invert Selection buttons are retained.

### Install

Close mDIR, extract `mDIR-P-2.26.19.zip`, run `INSTALL_MDIR.bat`, and reopen mDIR. Python 3.11 or newer is required.

---

## mDIR-P 2.26.18

This update makes right-button drag selection behave more like Total Commander when crossing long file lists.

### Continuous right-drag selection

- Moving the mouse while holding the right button no longer depends only on DataTable hover metadata. The current pointer geometry is used so the row under the moving pointer continues to be selected.
- While the gesture is active, Windows mDIR also samples the physical pointer position every 35 ms. This keeps the drag alive when Windows Terminal skips or combines B3-Motion events.
- Moving below the pane accelerates auto-scroll: the farther the pointer is below the bottom edge, the more rows are advanced per timer tick. The same behavior applies above the top edge.
- Horizontal movement outside the active pane pauses the scroll without discarding the gesture; returning to the pane resumes selection.
- Native right-button release detection prevents a stale captured drag if Windows Terminal does not deliver the final MouseUp event.

### Preserved behavior

- Each crossed row still toggles at most once per right-drag gesture.
- Fast motion fills skipped rows.
- Left/right panes remain independent and continue to share FilePane marks with thumbnail mode and F5/F6/F8 operations.
- The 2.26.17 large-directory batching optimizations and 2.26.16 two-tone Invert Selection buttons are retained.

### Install

Close mDIR, extract `mDIR-P-2.26.18.zip`, run `INSTALL_MDIR.bat`, and reopen mDIR. Python 3.11 or newer is required.

---

## mDIR-P 2.26.17

This performance update targets large-folder selection, especially repeated page-range selection and right-button drag selection.

### Faster selection

- Repeated **Shift+PageDown / Shift+PageUp** now updates only rows entering or leaving the range. It no longer rebuilds the complete selected range and copies the full marked set on each page step.
- File-list **right-button drag** batches all rows crossed by one mouse event and performs one cursor/details/summary refresh for the batch.
- Edge auto-scroll during right-drag now advances at a 35 ms interval instead of 55 ms, while still selecting continuously one row at a time.
- Selection remains owned by FilePane and stays shared with thumbnail mode and all existing F5/F6/F8 operations. Left/right pane independence is unchanged.

### Stability

- The change is intentionally limited to selection-state updates and repaint scheduling; directory scanning, copy/move/delete engines, thumbnail selection authority, and preview logic are not replaced.
- New regression tests cover repeated range paging and batched right-drag behavior in large cached listings.

### Install

Close mDIR, extract `mDIR-P-2.26.17.zip`, run `INSTALL_MDIR.bat`, and reopen mDIR. Python 3.11 or newer is required.

---

## mDIR-P 2.26.15

- Independent left/right thumbnail views and hidden-file controls.
- Right-aligned Select All, Deselect All and Invert Selection buttons on both panes.
- Teal selected-item backgrounds, white text and check marks, distinct from folder colors.
- Right-button drag selection: toggle each crossed item once per gesture, including fast movement and edge scrolling.
- Preserve selection when switching back to the file list and reuse existing copy/move actions.

Also includes preview loading/lifecycle fixes, modal visibility fixes and Windows Terminal shortcut/focus fixes since 2.26.5.

### Windows
Close mDIR, extract `mDIR-P-2.26.15.zip`, run `INSTALL_MDIR.bat`, and reopen mDIR. Python 3.11 or newer is required.

Release assets are built from the merged commit only after CI tests and package checks pass. Checksums are in `SHA256SUMS.txt`.
