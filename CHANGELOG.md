# Changelog

## 2.23.0

- Added a direct **Delete** toggle to Batch Rename so matching text can be
  removed without entering replacement text.
- Added a direct **Append number** toggle with separator, start, step, and
  digit controls for adding sequential numbers at the end of filenames.
- Changed the quick Batch Rename defaults to preserve the original name,
  delete matched text, and append a three-digit counter such as `_001`.
- Limited find/delete and find/replace to the filename stem so extensions are
  preserved unless they are deliberately changed with the extension pattern.

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
