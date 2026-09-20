# mDIR-P 2.26.30

This release integrates and reviews the 2.26.16–2.26.29 updates: large-folder selection and right-drag improvements, a dedicated Windows Terminal profile, cached Office PDF previews, native administrator delete retries, and shared Recent Folders menus on both panes.

## Review fixes

- Stop administrator deletion after cancellation instead of starting the next permanent-delete batch.
- Preserve completed-item counts when a later administrator batch fails.
- Pass the selected link path to Windows Shell without resolving it to the link target.
- Cancel Office preview requests even while they are waiting for another conversion.
- Prevent delayed startup callbacks from taking keyboard focus away from an open dialog.
- Make recent-folder UI tests wait for startup and menu focus; isolate test logging to avoid locked temporary files on Windows.

## Installation and verification

Close mDIR, extract `mDIR-P-2.26.30.zip`, run `INSTALL_MDIR.bat`, and reopen it. Both panels retain independent hidden-file, thumbnail, and selection controls. See `docs/REVIEW-2.26.30.md` for review scope, regression checks, and remaining manual checks. Office/UAC integration requires validation with the installed Office version and Windows account; mocked tests do not establish those manual results.

---

## mDIR-P 2.26.29

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
