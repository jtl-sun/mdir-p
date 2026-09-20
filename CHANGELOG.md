## 2.26.29

## 2.26.30

Reviewed 2.26.29; corrected administrator-delete cancellation and partial results, selected-link path handling, queued Office-preview cancellation, and late startup dialog focus. Added regression coverage and Windows test isolation. See docs/REVIEW-2.26.30.md.


- Recent Folders now behaves like a normal desktop drop-down: clicking anywhere outside the list closes it immediately and the same click is replayed to the underlying mDIR control, so no second click is required.
- Clicking the same pane's `▼` button while the list is open now simply closes the list instead of reopening it.
- Preserved one-click folder selection, shared MRU history, per-pane navigation, and `Alt+Down`.

# Changelog

## 2.26.28

- Replaced the separate `RF` toolbar buttons with compact `▼` Recent Folders buttons embedded at the far right of each pane's directory path bar.
- A single click now opens the recent-folder list immediately; the picker no longer requires a second click to expand a Select control.
- The Recent Folders picker is now a drop-down-style `OptionList` anchored under the clicked pane's path-bar button and supports single-click selection plus Up/Down/Enter keyboard navigation.
- The shared MRU history and per-pane navigation behavior from 2.26.27 are preserved: choosing a path changes only the pane whose `▼` button was used.
- `Alt+Down` remains available and opens the same drop-down for the active pane.
- Literal Windows paths are rendered without markup interpretation, and returning from the picker restores focus to the file table.


## 2.26.27

- Added an `RF` (Recent Folders) button to both the left and right pane toolbars.
- Both buttons open the same bounded MRU folder history, but the selected path is opened only in the pane whose button was pressed.
- Added `Alt+Down` to open Recent Folders for the active pane.
- Recent folders persist per user in `recent_folders.json` and are written atomically.
- The MRU list records actual successful directory transitions rather than ordinary rescans, so background refreshes do not reorder history.
- Missing/stale paths are removed from the list when an attempted reopen fails.


## 2.26.26

- Attach the Windows UAC/elevation consent UI to mDIR's actual Windows Terminal top-level HWND through `BIND_OPTS3.hwnd`, so the permission prompt opens in front of mDIR instead of only flashing on the taskbar.
- Normalise the tracked terminal handle to its root owner window and restore/foreground it immediately before requesting the native elevated `IFileOperation` broker.
- Forward the owner HWND from the Textual delete flow into the background STA elevation worker without elevating the main mDIR/Python process.
- Preserve the 2.26.25 native COM delete/recycle implementation, Recycle Bin policy, 10 GiB permanent-delete policy, UAC-cancel behavior, and post-operation verification.
- Added regression coverage that verifies the owner HWND is accepted and forwarded through the elevation path.

## 2.26.25

- Replaced the 2.26.24 PowerShell-based Administrator delete broker with Windows' native elevated `IFileOperation` COM broker. This avoids environments where `powershell.exe` itself is blocked by Windows security policy.
- Administrator retry now activates Microsoft's FileOperation COM local server through the standard `Elevation:Administrator!new:{CLSID_FileOperation}` moniker and lets Windows display UAC directly.
- Protected files/folders that use the normal mDIR delete policy are sent to the Recycle Bin with `FOFX_RECYCLEONDELETE`; only items already classified by mDIR as 10 GiB+ individual files are permanently deleted.
- The main mDIR/Python process remains non-elevated and no privileged PowerShell script, temporary command file, or user-writable elevated Python code is executed.
- Preserve the existing confirmation flow, UAC-cancel handling, partial-result reporting, and post-operation existence verification.
- Added regression coverage for native COM elevation identifiers/flags, 16-byte GUID layout, recycle/permanent policy partitioning, and confirmation that the Administrator path no longer contains PowerShell.

## 2.26.24

- Added Total Commander-style Administrator retry for protected deletes. mDIR first attempts the normal safe delete; only access-denied items are offered for UAC elevation.
- Added a short-lived UAC-elevated Windows PowerShell broker that retries only the protected items and preserves the existing Recycle Bin / 10 GiB permanent-delete policy instead of relaunching the whole mDIR process as Administrator.
- Added a dedicated confirmation dialog before elevation and a waiting modal while Windows UAC / the elevated helper is active. Cancelling UAC leaves the protected items untouched.
- Correctly interpret `SHFileOperationW` shell code `0x78` as source access denied / Administrator permission required instead of displaying the misleading text `Windows error 120`.
- Keep ordinary delete errors separate from elevation candidates and report any items that remain denied even after Administrator approval.
- Hash the temporary privileged-delete request and verify it inside the elevated Windows PowerShell broker before processing. The broker does not import Python/mDIR code from the user-writable installation and writes no privileged result file.
- Added regression coverage for access-denied classification, per-item recycle/permanent policy encoding, pre-delete SHA-256 verification, and confirmation that the elevated broker never imports user-writable mDIR/Python code.

## 2.26.23

- Extended the cached Office-to-PDF Preview pipeline to PowerPoint `PPT/PPTX`.
- Added a private persistent Microsoft PowerPoint COM worker using `DispatchEx`; presentations open read-only and without a document window, then export through PowerPoint's own PDF renderer.
- PowerPoint now shares the same path/size/mtime PDF cache, cancellation, 120 ms uncached-selection coalescing, atomic publishing, cache pruning and LibreOffice fallback used by Excel/Word.
- Cached PowerPoint previews bypass Office startup and render immediately through mDIR's existing PDF/PyMuPDF path.
- Retained the previous PPTX text extraction only as a final compatibility fallback when no PDF converter is available; legacy PPT still requires PowerPoint or LibreOffice if conversion fails.
- Added regression coverage for PowerPoint cache publishing/reuse and PDF-first routing.

## 2.26.22

- Replaced the primary Excel Preview renderer with an xViewer-inspired **Office -> cached PDF -> mDIR PDF renderer** pipeline for XLS/XLSX/XLSM/XLTX/XLTM.
- Added the same PDF-first pipeline for Word DOC/DOCX, preserving the real Microsoft Word page layout instead of drawing a text-only approximation.
- Added a private persistent Microsoft Office COM worker using `DispatchEx`; Excel and Word stay warm between previews without attaching to the user's interactive Office sessions.
- Added persistent PDF caching keyed by resolved path, file size, modification time and cache version. Unchanged documents skip Office conversion on repeat Preview.
- Cancel superseded Office conversions as soon as the Preview selection changes, preventing an old workbook/document from blocking the newly selected file.
- Coalesce uncached native Office Preview requests for 120 ms while the cursor is moving, while cached PDFs start almost immediately.
- Retained xViewer's bounded Excel page-setup retry and a private headless LibreOffice fallback when Microsoft Office is absent or fails.
- Added bounded cache pruning (900 PDFs / 3 GiB), PDF integrity checks, atomic cache publishing and rotating conversion diagnostics under LocalAppData.
- Kept the previous Excel grid and DOCX text renderers only as compatibility fallbacks when no PDF converter is available; PowerPoint behavior is unchanged.
- Added `pywin32` to the Windows Preview dependencies and new regression coverage for cache invalidation, cache hits, first-render publishing and cancellation.

## 2.26.21

- Re-identified the far-right blank strip as Windows Terminal host UI space (scrollbar reservation plus profile padding), not a Textual `Screen`/`#panes` width defect.
- Added a dedicated **mDIR** Windows Terminal profile as an official per-user JSON fragment, with `scrollbarState: hidden` and `padding: 0`, so mDIR can use the complete terminal viewport without changing other Terminal profiles.
- Updated the desktop shortcut to launch a new Windows Terminal window with the dedicated `mDIR` profile when `wt.exe` is available; classic/direct Python launch remains the fallback.
- Kept the `m` / `mdir` command aliases unchanged so they can still run inside an existing terminal; those commands intentionally inherit that terminal profile's own scrollbar/padding settings.
- Added regression coverage for the generated profile fragment and installer routing.

## 2.26.20

- Removed the unnecessary far-right root Screen scrollbar gutter by making the fixed mDIR application Screen non-scrollable.
- Explicitly keep `#panes` at full width so the two pane wrappers use the reclaimed terminal column.
- Preserved each FilePane/DataTable's own vertical scrolling; only the outer application-level scrollbar reservation is removed.
- Added regression coverage for the root-screen layout rule.

## 2.26.19

- Reworked list-view right-button drag into a single persistent controller: high-rate MouseMove/B3-Motion events now only publish the latest pointer coordinates and never repaint selection directly.
- The 30 ms drag controller is now the only path that advances selection, samples the native Windows pointer, scrolls at the pane edge, and applies distance-based acceleration. This prevents motion-event floods from starving the timer and causing 5-10 second pauses while the pointer is moving.
- Preserved one-toggle-per-row semantics, skipped-row filling, left/right pane independence, native right-button release detection, and distance-based top/bottom acceleration.
- Added regression coverage proving repeated MouseMove events do not perform selection work and that the controller tick consumes the latest pointer position.

## 2.26.18

- Keep right-button list selection active while the pointer moves by tracking the captured pointer from geometry instead of relying on potentially stale DataTable row metadata.
- Poll the physical Windows pointer during an active right-drag so selection continues when Windows Terminal coalesces or omits B3-Motion events, including while the pointer is below the terminal grid.
- Accelerate edge scrolling according to pointer distance beyond the top/bottom pane boundary, capped at eight rows per 35 ms tick for control.
- Pause scrolling when the pointer leaves the active pane horizontally, resume when it returns, and detect right-button release through Win32 to avoid a stuck drag if the terminal misses MouseUp.
- Added regression coverage for captured-pointer motion and distance-based edge-scroll acceleration.

## 2.26.17

- Accelerated large-directory range selection by updating only rows that enter or leave the active Shift range instead of rebuilding/copying the full marked set on every repeated Shift+PageUp/PageDown.
- Batch list-view right-drag selection so cursor movement, row painting, detail text and selection totals update once per mouse event instead of once per crossed row.
- Increased right-drag edge-scroll responsiveness from a 55 ms to a 35 ms row interval while preserving one-row continuous selection semantics.
- Added regression coverage for incremental repeated page selection and batched list right-drag selection.

## 2.26.16

- Changed each pane's **Invert Selection** button from a red `**` to a two-tone symbol: the first `*` is yellow and the second `*` is white.
- Preserved independent left/right pane invert-selection behavior; only the button presentation changed.
- Added regression coverage for the two-tone invert label and pane independence.

## 2.26.15

- Enable right-button drag selection in both thumbnail panes. Toggle crossed items once per gesture, fill skipped indices during fast movement, and preserve the file list's selection semantics for already-marked items.
- Scroll at the top/bottom edge while dragging. Stop on release, hidden/suspended windows, resize, or listing changes; prevent delayed cursor snapshots from pulling the viewport back during a drag.
- Batch mark updates on the Textual thread using the existing pane selection and cached totals. Reject stale events and exclude the parent row; retain selection when returning to the file list.

## 2.26.14

- Distinguish marked files and folders from ordinary gold directory labels: use white text, a check prefix, and a dark teal background across the marked row. Use a brighter teal cursor and preserve marked backgrounds under mouse hover.
- Give marked thumbnails a matching teal fill and outline, white labels, and a check badge above the image. Unmarked directory labels keep their original color.
- Preserve row hit-test metadata, cached mark updates, bulk selection, and independent pane behavior.

## 2.26.13

- Add right-aligned *a (Select All), *- (Deselect All), and ** (Invert Selection) buttons to both pane toolbars, separated from Th and identified by color and tooltips.
- Apply bulk selection only to the clicked pane's displayed files and folders, excluding the parent row and hidden items unless shown. Reuse the existing marked-item state for thumbnails and file operations.
- Update changed mark cells and cached selection totals in one batch without a directory rescan or cursor movement; reset the previous Shift-selection range. Reject partial/loading listings.
- Restore right-side file view when selecting from Preview; keep AI input untouched until the user returns to files.

## 2.26.12

- Fix native shortcuts stopping after clicking the other pane. Mouse dispatch changes table focus before the active pane, temporarily disabling capture; activating an already-focused table emits no second focus notification. Publish the keyboard context after the complete pane activation.
- Remove per-key context synchronization from the native test helper so tests follow the production event flow. Reproduce the 2.26.11 failure with actual Textual mouse clicks, and cover repeated pane round trips, same-pane clicks, focus-before-activation ordering, Properties dismissal, and Tab switching without repairing state from the test.

## 2.26.11

- Route all configured file-pane shortcuts through one action map. Capture the exact Windows modifier/key combination before terminal translation or terminal actions: Ctrl+H, Ctrl+Shift+M/S/L, Ctrl+Alt+M, Alt+Enter, Ctrl+Shift+F/C/D/W, and the other listed commands.
- Scope native capture to the foreground mDIR file pane. Release capture while dialogs, inputs, other screens, or other applications are active; discard queued commands from an obsolete focus/keymap context. Consume held command repeats without executing twice; allow navigation repeats.
- Make custom shortcuts take precedence over table bindings while keeping dialog/input editing local. Keep F12 available to exit the AI panel and preserve mouse/footer actions.
- Save a typed key when Save is clicked even without Apply; keep invalid drafts open. List and reserve essential navigation keys and reject Windows-reserved combinations.
- Add default-key routing in both panes, every editable-key remapping, native capture lifetime/context, actual Ctrl+H visibility, macro copy recording/playback, workspace restoration, and repeated Alt+Enter Properties regression coverage. Preserve Preview/modal/thumbnail fixes from 2.26.8–2.26.10.

## 2.26.10

- Suspend native Preview before Rename and other stacked screens appear, and restore it after the last screen closes. Keep the pending decode, displayed image, and zoom while suspended.
- Prevent selection refreshes and delayed Preview focus callbacks from reopening the overlay or stealing focus from dialog inputs.
- Replace the Windows Ctrl+F3 polling fallback and time-based suppression with a key-transition observer. One physical press toggles once; held-key repeats and duplicate terminal reports do not toggle again. Other applications' keys are passed through, and custom Preview shortcuts remain Textual bindings.
- Keep mouse/footer actions independent of keyboard deduplication. Retain low-frequency Windows Shift-click recovery.
- Add Rename cancel/confirm, nested dialogs, repeated/default/custom shortcuts, observer lifetime, and native suspend/resume regression coverage.

## 2.26.9

- Fix Preview stuck on Loading after opening thumbnails: bind each ImageTk image to the Preview canvas's Tcl interpreter, independent of which window starts first.
- Always acknowledge decoded results and reschedule result handling, including stale selections and render failures. Close failed image buffers and show a recoverable error instead of blocking all subsequent previews.
- Release Preview toolbar/widgets on their owning thread without global garbage collection of the independent thumbnail interpreter.
- Route Preview's Open button through the shared external-opening path so both Preview and thumbnails hide before launching another application.
- Restore Tab's Preview-to-files transition by dispatching the file table's priority Tab binding through the app's pane-switch action.
- Add real Windows Tcl/canvas/decoder regression tests for both startup orders, PNG/JPEG/PDF/Excel rendering, Fit/1:1/zoom, rapid selection, corrupt files, render failure recovery, and shutdown. Add Preview/thumbnail pane restoration and external-open interaction tests.

## 2.26.8

- Fix Th mouse clicks: register the decorated button handler on MDirApp instead of the plain Python mixin, which Textual does not register for decorated handlers.
- Make Sh/Hi and Ctrl+H independent per pane. Restore keyboard focus to the clicked pane; do not rescan or change the opposite pane.
- Persist per-pane Hidden/System visibility in settings and saved workspaces, with fallback for legacy global settings. Search respects the source pane and reveals hidden results only in the chosen pane.
- Show compact Sh/Hi labels and a tooltip describing the action for that specific pane.
- Add regression tests that send actual mouse clicks and queued native events, including clicks starting the real Tk manager, rather than invoking thumbnail actions directly.

## 2.26.7

- Add independent left/right thumbnail views with Alt+T and per-pane Th buttons.
- Share the existing file cursor, marks, and F5/F6 copy/move engine. Tab switches panes; arrows navigate only the active pane.
- Support left-click selection, right-click/Ctrl-click marking, double-click open, scrolling, and 96–240px thumbnail sizes.
- Use one Tk UI thread for both thumbnail windows and two bounded image workers. Decode only the visible area and one nearby row, with a bounded memory cache and 1GB disk cache keyed by path, nanosecond modification time, file size, and thumbnail size.
- Use Windows foreground/minimize event notifications, owned non-topmost windows, and no-activate mouse handling. Suspend overlays for dialogs, Preview/AI pane use, and external applications without clearing view state.
- Preserve 2.26.5's directory/drive polling, idle pause, and hang watchdog behavior.
- Fix a fast-operation race where a small copy could finish before the progress dialog mounted and leave an empty dialog behind.
- Include Pillow in the base install so thumbnails work without optional Preview dependencies.
- Add automated Textual, cache, large-list virtualization, and Windows native window tests. Extended interactive Windows and overnight soak testing remain release acceptance steps.

## 2.26.5

- Stability build for long-running Windows sessions.
- Reduce native Windows Ctrl+F3 / Shift-click polling from 40 ms to 250 ms.
- Suspend native key/mouse polling while mDIR is unfocused, Windows is idle, or a large file/archive operation is active.
- Reduce directory timestamp polling from 0.75 s to 5 s and drive polling from 10 s to 30 s.
- Reduce the lightweight drive-detection UI timer from 1.5 s to 5 s as well.
- Keep instant catch-up checks when mDIR regains focus, so slower background polling does not make the UI stale.
- Improve the UI hang watchdog: persistent freezes now capture up to four thread dumps, 30 seconds apart, instead of only the first snapshot.
- Harden the directory polling worker so unexpected errors cannot leave a replacement poll running indefinitely.

## 2.26.4

- Pauses automatic directory and drive polling while mDIR is not focused and after five minutes of Windows input idle time, then resumes with one asynchronous catch-up check when the user returns.
- Prevents long idle sessions from repeatedly touching sleeping, removable, or slow drives.
- Makes background drive-scan cleanup resilient to unexpected scan errors so a failed worker cannot leave the scan state stuck.
- Keeps the existing UI hang watchdog log at `%LOCALAPPDATA%\mDIR\mdir-hang.log` for post-freeze diagnosis.

## 2.26.3

- Removed automatic Undo from the product direction because restoring or deleting
  filesystem state after later edits or overwrites can create additional data-loss
  paths. Safety now relies on confirmation, Recycle Bin, conflict checks, and
  atomic/rollback-aware file replacement.
- Block Copy/Move when a directory target is the source itself or is inside the
  source tree, preventing recursive self-copy/self-move operations.
- Harden Safe Sync against destination-inside-source recursion and file/folder
  type conflicts; changed file replacement is staged and atomically published.
- Preserve the previous mIndex when a rebuild is cancelled instead of publishing
  an empty or partial index as completed.
- Stage Copy overwrites and protect Move overwrites with rollback so an operation
  failure does not destroy the previously existing destination.
- Removed stale build/egg-info artifacts from the review package so retired Undo
  implementation code cannot be mistaken for current source.

## 2.26.2

- Matched the Keys button styling to Links, Theme, and Help in the Options
  screen while retaining keyboard focus indication for arrow-key navigation.

## 2.26.1

- Added direct arrow-key navigation between every button in the Options grid.
- Added a Help button that opens the installed `README.md` inside mDIR's
  read-only Viewer.
- Included `README.md` in wheel installations so Help works outside the source
  folder as well as from the ZIP installer.

## 2.26.0

- Replaced the generic `Ctrl+P` command palette and its Maximize, Quit, and
  Screenshot commands with an mDIR-specific `F10 Option` screen.
- Added Options for Keys, Links, and Theme without exposing framework-only
  commands.
- Added persistent key customization for file operations, search, advanced
  tools, sorting, AI, and Preview, with immediate runtime application.
- Kept navigation, opening, selection, and the Options key fixed so an invalid
  customization cannot make the file manager unusable.
- Added duplicate-key and fixed-key collision checks plus selected/all reset.

## 2.25.1

- Use installed Microsoft Word or PowerPoint on Windows to render legacy DOC
  and PPT files before falling back to LibreOffice.
- Open Office documents read-only with macros disabled while preparing Preview,
  without modifying the original file.
- Suppress a late selection event from reopening Preview over the external
  application immediately after a file is opened.

## 2.25.0

- Added the lazy SQLite `mIndex` filename index and exact/visual duplicate
  discovery without changing files.
- Added a persistent Undo Center for safe Copy, Move, Rename, MkDir, Batch
  Rename, and safe-sync operations. Undo refuses to remove files edited later;
  Trash/Recycle Bin deletes and overwrites remain deliberately non-undoable.
- Added named two-pane Workspaces, a Copy/Move Macro recorder, and a reviewed
  macro queue that never overwrites an existing target automatically.
- Added Pause/Resume to background file operations and automatic queuing when
  another file operation is already running.
- Added recursive folder comparison and deletion-free one-way safe sync.
- Added explicit `/file` and `/파일` AI requests that produce a visible plan
  and require approval before any filesystem change.

## 2.24.1

- Close the native Preview overlay before opening a file externally so the
  associated application receives an unobstructed, editable window.

## 2.24.0

- Expanded Preview to images, PDF, Excel, CSV/TSV, text, Markdown, JSON, XML,
  YAML, HTML, Word, and PowerPoint while keeping rendering lazy and bounded.
- Added lightweight DOCX/PPTX text fallback and optional on-demand
  LibreOffice rendering for page-accurate layouts and legacy DOC/PPT files.
- Open files from search results with one click or Enter in the operating
  system's default application; use **Location** to reveal one inside mDIR.
- Added selected-file placeholders to program links so free specialist apps
  can be connected without increasing mDIR's installed weight.
- Kept the AI panel as a core, lazily loaded feature with external provider
  tools remaining optional.

## 2.23.29

- Reuse the existing private Python environment and its installed preview
  dependencies during an update.
- Stop disabling pip's download cache and stop force-reinstalling every
  dependency on each installation.
- Avoid upgrading pip on every run and prefer prebuilt binary packages when a
  dependency really must be installed.

## 2.23.28

- Make right-click the range anchor and Shift+left-click the only range
  endpoint gesture, avoiding a conflict with right-button mark toggling.
- Detect Shift+left-click directly through Windows even when Windows Terminal
  consumes the click and sends no mouse event to mDIR.
- Map the physical click position back to the visible pane and row without
  moving the screen first.

## 2.23.27

- Detect the physical Windows Shift key when Windows Terminal omits the Shift
  modifier from a mouse event.
- Preserve that physical Shift state from MouseDown through Click so range
  selection cannot fall through into normal selection, Open, or Rename.

## 2.23.26

- Save a normal right-clicked row as the anchor for the next Shift range
  selection.
- Select every file and directory between that anchor and a Shift+left-click
  or Shift+right-click endpoint, including both endpoints.
- Keep unmodified right-click toggling and right-button drag selection intact.

## 2.23.25

- Expire a new file's selection click after 0.2 seconds so it cannot later be
  mistaken for the first half of a slow Rename click pair.
- After that selection-only interval, require a fresh pair of clicks on the
  selected file: a fast pair opens it and a slow pair starts Rename.
- Override the terminal's longer native double-click chain when it conflicts
  with the stricter 0.2-second selection rule.

## 2.23.24

- Make the first left click on a different file selection-only and discard any
  Rename timing retained from the previously selected row.
- Use only the second click on the same selected file to decide the action:
  a fast pair opens it, while an intentionally slow pair starts Rename.
- Preserve the direct first-click selection and stable page position added in
  2.23.23.

## 2.23.23

- Anchor a left mouse click to the rendered file row before pane focus can
  scroll an off-screen keyboard cursor back into view.
- Select a file on the newly displayed page with the first click, without an
  intermediate jump to the top or bottom of the previous cursor's page.

## 2.23.22

- Show `▲` or `▼` before the active sort column's Name, Ext, Size, or Modified
  header.
- Update the indicator immediately for header clicks and keyboard sort actions,
  including direction reversal on a repeated sort.
- Preserve centered Ext/Size/Modified headers while displaying the indicator.

## 2.23.21

- Reduce the Ext column's right side by two cells.
- Center the Ext, Size, and Modified headers within their columns while keeping
  Name left-aligned.
- Migrate a saved pre-2.23.21 Ext width exactly once so repeated launches do
  not keep shrinking the column.

## 2.23.20

- Move the two-cell Size/Modified gutter to the beginning of the Modified
  column so it is a true visible gap between the columns, not trailing content
  inside Size cells.
- Widen Modified so its two-cell gutter and complete timestamp remain visible.

## 2.23.19

- Center `<DIR>` markers within the Size column.
- Reserve exactly two blank cells after right-aligned file byte counts so the
  Size and Modified values never run together.

## 2.23.18

- Shorten the file-list `Extension` header to `Ext`.
- Reduce the visual gap before extension values from three cells to two.
- Right-align exact byte counts and `<DIR>` labels in the Size column.
- Preserve the `Ext` header after interactive column resizing.

## 2.23.17

- Show the complete exact byte count in file-list Size columns, with thousands
  separators (for example, `4,590,867`) instead of shortening it to KB/MB/GB.
- Keep directories labeled `<DIR>` and retain human-readable units in summary
  and detail areas where exact list sorting is not being displayed.
- Widen the default Size column so large byte values remain visible.

## 2.23.16

- Stop inserting a real cursor character into filenames during editing, which
  previously shifted all following characters on every blink.
- Use Windows Terminal's steady, zero-width vertical insertion cursor so text
  spacing and selection width remain fixed throughout Rename and every other
  single-line input dialog.
- Pause the simulated cursor blink to avoid unnecessary input repaints.

## 2.23.15

- Show a compact warning immediately before Copy or Move would overwrite an
  existing same-name item.
- Keep both the source and existing destination unchanged when the overwrite
  warning is cancelled.
- Require explicit overwrite approval in the background file-operation engine
  as a second safety layer.

## 2.23.14

- Recalibrate file-list mouse timing: two clicks within 0.75 seconds open the
  item, while an intentional slower second click after 1.00 seconds opens
  Rename.
- Add a short neutral interval between the two actions to prevent a borderline
  click from opening the wrong operation.

## 2.23.13

- Replace full-cell block cursors with a thin vertical insertion bar in every
  single-line input field.
- Apply the same cursor to Rename, MkDir, Copy/Save As, path editing, search,
  archive, shortcut, column-width, and Batch Rename fields.
- Keep drag-selected text visibly highlighted while showing the insertion
  point independently as a narrow bar.

## 2.23.12

- Make the AI Stop button force-kill the entire Codex, PowerShell, Claude,
  Gemini, or Ollama process tree instead of only asking the parent process to
  terminate.
- Create AI providers in an isolated Windows process group (or POSIX session)
  so child commands cannot continue after Stop.
- Run Windows `taskkill /T /F` outside the UI thread, keeping mDIR responsive
  while the provider tree is being terminated.
- Arm force-stop during the short startup race so a process launched just
  after Stop is immediately killed as well.

## 2.23.11

- Close the file-operation progress window immediately when Cancel or Escape
  is pressed, so a delayed Windows delete/recycle call cannot trap the user in
  a modal dialog.
- Let the current non-interruptible Windows filesystem call finish safely in
  its existing background worker while preventing any later selected items
  from starting.
- Keep pane navigation, mouse input, keyboard input, and Quit available after
  a cancellation request.

## 2.23.10

- Send files smaller than 10 GB and selected folders to the Windows Recycle
  Bin instead of deleting them permanently.
- Permanently delete only individual files of 10 GB or larger.
- Replace Delete's filename list with a compact summary of selected counts,
  total file size, Recycle Bin items, and permanent-delete items.
- Never fall back to permanent deletion when Windows cannot recycle an item;
  report the failure and leave that item untouched.

## 2.23.9

- Replace the long filename list in the Move confirmation with a compact
  summary showing selected file count, folder count, total selected-file size,
  and destination directory.
- Reuse the active pane's cached metadata so the Move dialog opens quickly
  even when thousands of files are selected.

## 2.23.8

- Move directory scanning off the UI thread when opening, refreshing, or
  switching large folders, keeping keyboard and mouse input responsive.
- Show the first 250 rows as soon as scanning finishes, then populate the
  remaining rows in responsive batches instead of blocking on one full table.
- Cancel obsolete listing work when the user navigates to another directory
  before the previous large listing completes.

## 2.23.7

- Prevent slightly slow double-clicks from opening Rename when Windows
  Terminal loses the native click-chain value.
- Extend the double-click Open protection window to 1.60 seconds and require
  at least 2.00 seconds before a repeated click can start Rename.

## 2.23.6

- Use the requested safe Batch Rename defaults: name `[N]`, extension `[E]`,
  text deletion OFF, numbering OFF, `_` separator, start/step/digits `1`, and
  regex OFF.
- Keep original names unchanged when Batch Rename first opens; counters are
  appended only after **End number** is deliberately turned ON.

## 2.23.5

- Add one-click Batch Rename options to delete found text and append an
  automatic counter at the end of each filename.
- Keep mouse and keyboard input responsive while automatic refreshes insert
  thousands of rows into a panel.
- Release stale mouse capture, right-drag scrolling, and column-resize state
  when Windows Terminal loses focus.
- Write automatic Python stack diagnostics to
  `%LOCALAPPDATA%\\mDIR\\mdir-hang.log` if the UI event loop is blocked for
  15 seconds, making any remaining intermittent freeze diagnosable.

## 2.23.4

- The MkDir dialog now starts with the selected file or directory name and
  selects the whole value, making it easy to edit into a new directory name.
- The parent-directory (`..`) row continues to open MkDir with an empty name.
- Prevented idle directory and drive polling from accumulating blocked worker
  threads when a network, removable, or sleeping drive stops responding.
- Moved automatic directory rescans and drive-capacity reads off the UI thread
  so delayed filesystem calls cannot block keyboard or mouse input.

## 2.23.3

- Directory paths in both green path bars now always end with a separator,
  such as `D:\\pg\\wk\\PO\\`.
- Kept internal `Path` values unchanged so navigation, sorting, and file
  operations continue to use normalized directory paths.
- Added a small gap and a pale yellow separator between each file list and
  its directory summary/detail information.
- Added regression coverage for Windows-style and native path formatting.

## 2.23.2

- Made every directory segment in the path bar clickable. Clicking `PO` in
  `D:\\pg\\wk\\PO\\...` immediately opens `D:\\pg\\wk\\PO` in that pane.
- Kept drag selection and direct keyboard editing available in the path bar.
- Changed path bars, active-pane borders, and active cursor rows to a clear
  green palette so the selected pane and item are easier to distinguish.
- Added unit and interactive regression coverage for segment navigation.
- Launchers now use Python safe-path mode so an older `mdir` source folder in
  the current directory cannot shadow the newly installed 2.23.2 package.
- The Windows installer now compares the source and installed versions and
  stops with a clear error instead of reporting success on a version mismatch.

## 2.23.1

- Added `INSTALL_MDIR.bat` for double-click installation and updates without
  manually selecting a Python version or entering pip commands.
- The installer uses a private environment under `%LOCALAPPDATA%\mDIR`,
  creates permanent `m` and `mdir` launchers, adds them to the user PATH, and
  creates the mDIR desktop shortcut automatically.
- Clicking any empty area inside the left or right file table now activates
  that pane; a filename or populated cell is no longer required.
- Clicking the path, information, summary, or background area of a file pane
  also activates the corresponding side.
- Right-button selection begins in the clicked pane even when the first press
  lands on empty table space.
- Preserved editable path focus while switching panes with the mouse.
- Added two-direction blank-area mouse activation regression coverage.

## 2.23.0

- Changed the active Windows console and Windows Terminal tab title to `mDIR`
  while the program is running, then restores the previous title on exit.
- Added a multi-resolution mDIR application icon for classic console windows,
  package resources, and shortcuts.
- Added `install_mdir_shortcut.ps1` to create a clearly identifiable mDIR
  desktop shortcut with the bundled icon.
- Added package and regression checks for the icon resource and window title.

## 2.22.1

- Extended same-row double-click recognition to 0.95 seconds for terminals
  that end the native click chain earlier than expected.
- Delayed mouse-triggered Rename until a clearly slower repeated click, from
  1.10 through 3.00 seconds after selecting the same row.
- Kept normal native double-click, `Enter`, and `F2` behavior unchanged.
- Added regression coverage for extended double-click, rename timing bounds,
  expired clicks, and clicks on a different row.

## 2.22.0

- Moved Copy, Move, and permanent Delete filesystem work to a background
  worker so large selections no longer block keyboard input or screen redraws.
- Added a live progress window with completed/total counts, current item, ETA,
  and `Esc`/Cancel support.
- Coalesced progress updates and suspended automatic directory rescans during
  active file operations, then refreshes each affected pane once at the end.
- Replaced per-item path resolution with normalized path comparison to reduce
  filesystem calls in large batches.
- Added real Copy, Move, and Delete regression coverage using 1,005 files,
  plus cancellation and responsive-UI tests.

## 2.21.4

- Fixed Move and Delete confirmation dialogs so pressing `Enter` activates
  `Yes` and completes the requested operation.
- Changed the confirmation dialog's initial focus from `Cancel` to `Yes`.
- Kept `Esc`, `N`, the Cancel button, and the close button as cancel actions.
- Added an end-to-end regression test covering Move and permanent Delete with
  keyboard confirmation.

## 2.21.3

- `Alt+F6` now extracts a ZIP into the opposite pane by default: left to right
  and right to left.
- The extraction destination remains editable in the Extract ZIP window.
- If the opposite pane's directory is unavailable, mDIR safely falls back to
  the directory containing the ZIP.
- The source pane is fixed when the window opens, so changing focus while the
  window is open cannot reverse the extraction direction.
- The pane receiving extracted content is refreshed after completion.

## 2.21.2

- `Alt+F5` now creates a ZIP in the opposite pane by default: left to right
  and right to left.
- The ZIP destination remains editable in the Create ZIP window.
- If the opposite pane's directory is unavailable, mDIR safely falls back to
  the source pane's directory.
- The pane containing the completed ZIP is refreshed and highlights the new
  archive when its destination is currently visible.
- Added regression coverage for both pane directions.

## 2.21.1

- When the suggested ZIP name already exists, `Alt+F5` now proposes the next
  available name, such as `images (2).zip`, instead of failing.
- If an existing ZIP path is entered manually, the Create ZIP window remains
  open and explains that the filename must be changed or overwrite enabled.
- Revalidated explicit overwrite behavior: the old archive is replaced only
  after the new temporary ZIP has been completed successfully.

## 2.21.0

- Audited all application shortcuts and removed the `Ctrl+P` conflict with
  Textual's command palette; item Properties now uses `Alt+Enter`.
- Blocked ZIP output paths inside a selected source folder, preventing a
  temporary archive from accidentally reading and compressing itself.
- Moved ZIP creation, ZIP extraction, and recursive folder-size calculation
  to background workers so long operations no longer freeze pane navigation.
- Added full preflight validation for ZIP file/directory tree conflicts before
  extraction writes any member.
- Rechecked large-directory caching, background search, preview loading,
  selection, batch rename, drive polling, and ZIP security behavior.
- Expanded the automated regression suite and installation/user documentation.

## 2.20.0

### ZIP compression and extraction

- Added `Alt+F5` to compress the active pane's selected files and folders into
  a ZIP archive.
- Added `Alt+F6` to extract one selected ZIP into an editable destination.
- Added Fast, Normal, and Maximum compression levels and explicit overwrite
  choices.
- Preserved directory structure and empty directories during compression.
- ZIP creation is atomic and does not replace an existing archive after a
  failed operation.
- Extraction rejects path traversal, absolute/drive paths, symbolic links,
  invalid ZIP files, and unapproved file collisions.
- Extracted files are written through temporary files before being published.
- Added archive engine and keyboard-dialog regression tests.

## 2.19.0

### Find files

- Added a `Ctrl+F` Find Files window using the active pane as the initial
  search location.
- Added partial-name, wildcard, multiple-pattern, and regular-expression
  filename matching.
- Added file/directory, case-sensitive, hidden/system, recursive-depth, and
  result-limit controls.
- Added optional text-content search for files up to 16 MB with UTF-8,
  UTF-16, and Korean Windows text decoding.
- Search runs in a background worker with live scanned/result counts and a
  safe Stop action.
- Results show name, folder, type, size, and modified time. Opening a result
  returns to the original pane and highlights the matching item.
- Added validation tests for matching rules, recursion depth, hidden entries,
  content search, result limits, cancellation, and the search dialog.

## 2.18.0

### Batch rename

- Added a `Ctrl+F2` Batch Rename window with a current/new-name preview.
- Added name, extension, counter, date, and time tokens.
- Added find/replace, optional regular expressions, and counter controls.
- Opening `F2` with several marked items now uses Batch Rename automatically.
- Added validation for duplicate targets, existing names, forbidden Windows
  characters, and invalid results.
- Renames use a two-phase temporary-name operation and roll back on failure,
  including swap-style renames.

## 2.17.2

### Repository cleanup

- Removed old version-named launchers, build output, caches, and package
  metadata from the GitHub source tree.
- Replaced import-time widget monkey patching with explicit application class
  settings, so behavior no longer depends on import order.
- Consolidated the package version and moved current settings to
  `%USERPROFILE%\.mdir-p.json`; the old `.mdir18.json` file remains readable
  for a seamless upgrade.
- Pinned Textual to the tested 8.2.8 release and added Windows GitHub Actions
  validation.

## 2.17.1

### Selection improvements

- `Shift+Up` and `Shift+Down` now select correctly from the first key press.
- `Shift+Click` selects the complete range between the current anchor and the
  clicked row.
- `Shift+Home`, `Shift+End`, `Shift+Page Up`, and `Shift+Page Down` are
  supported.
- Fast right-button dragging interpolates all crossed rows so intermediate
  items are not skipped when mouse events arrive slowly.
- Holding a right-button drag at the top or bottom edge now scrolls the file
  list automatically and continues selecting rows on following pages.

### Filename display

- The Name column now displays the filename title without repeating the final
  extension.
- The Extension column remains immediately to the right and adds a three-cell
  visual gap for easier scanning.
- Directory names containing dots are preserved unchanged.

### Validation

- MDIR-P package self-check passed.
- All 12 automated tests passed with Textual 8.2.8.
- The `mdir_p-2.17.1-py3-none-any.whl` installation package built
  successfully.
