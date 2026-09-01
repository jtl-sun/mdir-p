# Changelog

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
