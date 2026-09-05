# mDIR-P

**A fast, free dual-pane file manager for Windows.** Classic MDIR speed,
modern previews, safe file operations, and integrated AI —
inside PowerShell and Windows Terminal.

[![Latest release](https://img.shields.io/github/v/release/jtl-sun/mdir-p?label=Windows)](https://github.com/jtl-sun/mdir-p/releases/latest)
[![License: MIT](https://img.shields.io/badge/license-MIT-2ea44f.svg)](LICENSE)
[![Tests](https://github.com/jtl-sun/mdir-p/actions/workflows/ci.yml/badge.svg)](https://github.com/jtl-sun/mdir-p/actions)

> **Free and open source.** Built so Windows users can manage files quickly
> without subscriptions, ads, or account registration.

### Download for Windows

[**Download the latest stable mDIR-P**](https://github.com/jtl-sun/mdir-p/releases/latest)
· [Release notes](https://github.com/jtl-sun/mdir-p/releases)
· [Ubuntu version](https://github.com/jtl-sun/mdir-u)

Extract the ZIP, close any running mDIR window, and double-click
**`INSTALL_MDIR.bat`**. Then start mDIR from the desktop shortcut or type
`m` in a terminal.

![mDIR dual-pane workflow](docs/assets/mdir-demo.gif)

## Dedication

MDIR-P is a tribute to **Choi Jung Han**, the developer of the legendary
DOS-era file manager **MDIR**. His work inspired generations of users to
manage files quickly and efficiently from the keyboard.

## Highlights

- Fast dual-pane file management inspired by MDIR and Total Commander
- Responsive handling of folders containing 20,000 or more image files
- Preview for images, PDF, Excel, Word, PowerPoint, CSV, text, and Markdown
- Mouse-wheel zoom and drag-to-pan in Preview
- Integrated AI terminal with Codex, PowerShell, and Ollama providers
- Copy, move, rename, delete, search, drive selection, and editable paths
- Responsive background Copy, Move, and Delete for batches exceeding 1,000
  items, with live progress and cancellation
- Compact overwrite warning before Copy or Move replaces a same-name item
- Advanced file search with filename patterns, content search, depth and
  hidden/system controls, live progress, cancellation, and clickable results
- Safe batch rename with live preview, tokens, counters, and find/replace
- Built-in ZIP compression and secure ZIP extraction without extra software
- Safe, size-limited text viewing and editing with `F3` and `F4`
- Total Commander-inspired default theme
- Configurable top shortcut bar for files, folders, programs, websites,
  PowerShell commands, and MDIR-P actions
- Windows Terminal and Korean IME support

## Requirements

- Windows 10 or Windows 11
- Python 3.11 or newer
- PowerShell or Windows Terminal

## Installation on Windows

### Easy installation or update (recommended)

1. Click **Code > Download ZIP** on this GitHub page.
2. Extract the downloaded ZIP.
3. Open the extracted `mdir-p-main` folder.
4. Double-click **`INSTALL_MDIR.bat`**.

The installer creates a private environment under `%LOCALAPPDATA%\mDIR`,
installs Preview support, creates permanent `m` and `mdir` commands, adds the
command folder to the user PATH, and places an **mDIR** shortcut on the
desktop. To update later, download the newest ZIP and double-click the same
file again. The installer verifies that the installed version exactly matches
the downloaded source. Personal settings are preserved.

If Windows SmartScreen appears, choose **More info > Run anyway** only after
confirming that the ZIP came from this repository.

### Manual installation from the ZIP

1. Download the repository as a ZIP file and extract it.
2. Open the extracted folder. Confirm that `pyproject.toml` is visible there.
3. Right-click an empty area in the folder and select **Open in Terminal**.
4. Run the following commands in PowerShell:

```powershell
python -m pip install --upgrade pip
python -m pip install --upgrade ".[preview]"
python -m mdir
```

Do not enter an old Wheel filename such as
`mdir_p-2.17.0-py3-none-any.whl`. GitHub source ZIP files normally do not
include a Wheel. Installing `.[preview]` uses the current source version in
the folder.

If `pyproject.toml` is not shown, the terminal is in the wrong folder. Move
into the inner extracted folder first. For example:

```powershell
cd .\mdir-p-main
python -m pip install --upgrade ".[preview]"
```

### Install with Git

```powershell
git clone https://github.com/jtl-sun/mdir-p.git
cd mdir-p
.\INSTALL_MDIR.bat
```

### Optional: Use a virtual environment

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade ".[preview]"
```

The tested Textual version is pinned by `pyproject.toml`, so a fresh install
uses the same UI framework version as the automated tests.

## Upgrade

Download the newest ZIP and double-click `INSTALL_MDIR.bat` again. For a Git
checkout, run:

```powershell
git pull
.\INSTALL_MDIR.bat
```

Personal settings such as shortcuts are stored separately and are not removed.

## Run

After installation, any of these commands starts MDIR-P:

```powershell
m
M
mdir
```

PowerShell command names are case-insensitive, so `m` and `M` run the same
launcher. The longer `mdir` command is provided as an alternative.

Without installation, run:

```powershell
python -m mdir
# or
.\start_mdir_p.ps1
```

## PowerShell Script Policy Error

If PowerShell reports that `start_mdir_p.ps1` or `Activate.ps1` cannot be
loaded because script execution is disabled, the application itself is not
damaged. You can always start it without a PowerShell script:

```powershell
python -m mdir
```

To allow scripts only in the current PowerShell window, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\start_mdir_p.ps1
```

To allow locally created and downloaded scripts for the current Windows user:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
Unblock-File .\start_mdir_p.ps1
.\start_mdir_p.ps1
```

When PowerShell asks for confirmation, enter `Y`. Administrator privileges
are normally not required for `CurrentUser` or `Process` scope.

## Troubleshooting Installation

- **`No matching distribution found` or Wheel file not found:** Do not use an
  old `.whl` filename. Run `python -m pip install --upgrade ".[preview]"` in
  the folder containing `pyproject.toml`.
- **`python` is not recognized:** Install Python 3.11 or newer from
  [python.org](https://www.python.org/downloads/windows/) and enable **Add
  python.exe to PATH** during installation.
- **`m` or `mdir` is not recognized after installation:** Close and reopen
  PowerShell, or run the reliable fallback `python -m mdir`.
- **The old version still opens:** Reinstall only the local mDIR package from
  the new source folder using
  `python -m pip install --no-deps --force-reinstall .`.

## Main Keys

| Key                    | Action                                      |
| ---------------------- | ------------------------------------------- |
| `Tab`, `Left`, `Right` | Switch file pane                            |
| `Enter`                | Open a file or directory                    |
| `Space`                | Mark an item                                |
| `Shift+Up/Down`        | Extend or shrink the marked range           |
| `Shift+Home/End`       | Mark from the anchor to the first/last row  |
| `Shift+Click`          | Mark from the anchor to the clicked row     |
| Right-button drag      | Toggle every crossed row                    |
| `F2`                   | Rename                                      |
| `Ctrl+F2`              | Batch rename selected items                 |
| `F3`                   | View a supported text file                  |
| `F4`                   | Edit a supported text file                  |
| `F5`                   | Copy                                        |
| `F6`                   | Move                                        |
| `Alt+F5`               | Compress selected items to ZIP              |
| `Alt+F6`               | Extract the selected ZIP file               |
| `F7`                   | Create a directory                          |
| `F8`                   | Delete                                      |
| `F9`                   | Select a drive                              |
| `F10`                  | Quit                                        |
| `F12`                  | Toggle the AI terminal                      |
| `Ctrl+F`               | Advanced search                             |
| `Ctrl+Shift+F`         | mIndex indexed filename search              |
| `Ctrl+Shift+D`         | Exact and visually similar duplicates       |
| `Ctrl+Shift+C`         | Compare the two current folders             |
| `Ctrl+Shift+Y`         | Safe sync active pane to opposite pane      |
| `Ctrl+Z`               | Undo Center                                 |
| `Ctrl+Shift+S/L`       | Save/load a named Workspace                 |
| `Ctrl+Shift+M`         | Start/stop Copy/Move Macro recording        |
| `Ctrl+Alt+M`           | Review and play a saved Macro               |
| `Ctrl+F3`              | Toggle Preview                              |
| `Ctrl+G`               | Calculate selected folder size              |
| `Ctrl+H`               | Show or hide hidden/system items            |
| `Ctrl+R`               | Refresh both panes                          |
| `F11`                  | Refresh connected drives                    |
| `Ctrl+N/E/S/D`         | Sort by name/extension/size/modified date   |
| `Ctrl+W`               | Edit column widths                          |
| `Ctrl+Shift+W`         | Reset column widths                         |
| `Shift+F10`            | Open PowerShell in the current folder       |
| `Alt+F1`, `Alt+F2`     | Select the left or right drive              |
| `Ctrl+P`               | Open the command palette and theme selector |
| `Alt+Enter`            | Show properties for the selected item       |

When several items are marked, `F2` opens Batch Rename automatically. The
same tool is always available with `Ctrl+F2`. Its live preview supports `[N]`
(current name), `[E]` (extension), `[C]` (counter), `[YMD]` (modified date),
and `[hms]` (modified time), plus ranges such as `[N1-5]` and literal or
regular-expression replacement.
The **Quick options** row covers the two most common jobs without editing a
pattern: **Delete found text** removes the text entered in Find, and **End
number** appends the configured counter immediately before the extension.
Both options update the preview before any file is changed.
The safe default is `[N]` with **Delete found text: OFF** and **End number:
OFF**, so filenames remain unchanged until an option is deliberately enabled.
The counter defaults to one digit (`1`) when numbering is turned on.
MDIR-P validates duplicate names, existing targets, and invalid Windows names
before making any changes.

## File Management Workflow

- The pane with the bright border is active; file operations use the other
  pane as the default destination.
- Mark several items with `Space`, Shift selection, or right-button drag. If
  nothing is marked, the item under the cursor is used.
- `F5` copies and supports **Save As** for one selected item. `F6` moves and
  shows a compact confirmation with file/folder counts, total selected-file
  size, and destination instead of listing every filename.
- `F8` sends files smaller than 10 GB and folders to the Windows Recycle Bin.
  Individual files of 10 GB or larger are permanently deleted and are counted
  separately in the confirmation dialog.
- Cancel or `Esc` closes a Copy/Move/Delete progress window immediately. If a
  Windows filesystem call is already running, it finishes safely in the
  background, but no additional selected item is processed.
- The AI panel's **Stop** button force-stops the complete provider process tree,
  including child PowerShell commands, instead of allowing a running command
  to continue after a normal terminate request.
- All single-line text fields use a thin vertical insertion cursor rather than
  a full-character block, making mouse-drag text selection easier to read.
- Copy, Move, and Delete run in the background, so the interface remains
  responsive even when more than 1,000 items are selected. The progress
  window updates in batches to avoid unnecessary screen redraws; press `Esc`
  or select **Cancel** to stop after the current top-level item.
- `F8` permanently deletes only after a confirmation window. Windows Recycle
  Bin is not used, so verify the selected names carefully.
- Click a column header to sort and click it again to reverse the order. Drag
  the visible column separator to resize it; widths are saved automatically.
- Click any folder name in the green path bar to jump directly to that level.
  For example, clicking `PO` in `D:\\pg\\wk\\PO\\Orders\\` opens
  `D:\\pg\\wk\\PO\\`. Displayed directory paths always end in a backslash.
  Click the final folder to keep editing the full path, or drag to select
  text. Environment variables such as `%USERPROFILE%` are accepted.
- External file changes and removable-drive changes are detected
  automatically. Use `Ctrl+R` or `F11` when an immediate manual refresh is
  preferred.

## Find Files

Press `Ctrl+F` to open the **Find Files** window. The active pane's current
folder is used as the initial search location.

- Enter a complete or partial filename, or wildcard patterns such as `*.jpg`
  and `report-??.xlsx`.
- Separate several filename patterns with semicolons, for example
  `*.jpg; *.png; *.webp`.
- Enable **Regular expression** for advanced filename matching.
- Search files, directories, or both, with optional case sensitivity.
- Include all subfolders or limit the search to a selected depth.
- Include hidden/system entries when needed.
- Enter **Text contains** to search inside common text files up to 16 MB.
- Set a result limit between 500 and 10,000 items.
- Press **Stop** or `Esc` while searching to cancel safely.
- Select a result and press `Enter`, or click **Open location**, to return to
  the file pane with that item highlighted.

Filename and content searching runs in the background, so the main file
manager remains responsive during large searches. Content search intentionally
skips files larger than 16 MB to avoid reading very large or binary files into
memory.

## ZIP Compression and Extraction

MDIR-P uses Windows-compatible ZIP files and does not require 7-Zip, WinRAR,
or another external archive program.

### Create a ZIP

1. Mark one or more files or folders with `Space`, `Shift`, or the mouse.
2. Press `Alt+F5`.
3. Check or edit the ZIP filename and location. The default destination is
   always the opposite pane: left-pane selections create the ZIP in the right
   pane, and right-pane selections create it in the left pane.
4. Choose Fast, Normal, or Maximum compression.
5. Enable **Overwrite existing ZIP** only when the old archive should be
   replaced, then select **Create ZIP**.

If the suggested ZIP name already exists, mDIR automatically proposes the next
available name, for example `images (2).zip`. If you manually enter an existing
name without enabling overwrite, the window stays open so you can change the
name or approve replacement; the archive operation does not fail or close the
window.

Folder structure and empty folders are preserved. The ZIP is first written to
a temporary file and replaces the destination only after creation succeeds.
Save the ZIP outside any folder that is itself being compressed; this prevents
the temporary archive from being included in its own input.

### Extract a ZIP

1. Select exactly one `.zip` file.
2. Press `Alt+F6`.
3. Check or edit the destination folder. The default destination is always
   the opposite pane: a ZIP selected in the left pane extracts into the right
   pane, and a ZIP selected in the right pane extracts into the left pane.
4. Enable **Overwrite existing files** only when replacement is intended,
   then select **Extract**.

If the opposite pane's directory is unavailable, mDIR safely falls back to
the directory containing the ZIP. The destination remains editable in the
Extract ZIP window.

Extraction blocks unsafe parent paths, absolute paths, drive paths, and
symbolic links inside an archive. Existing files are not overwritten unless
the option is explicitly enabled. RAR, 7Z, TAR, and other formats are not
included in this version.

ZIP creation and extraction run in a background worker. The panes remain
responsive while a large archive is processed, and a second ZIP operation is
prevented until the first one finishes.

## Preview and Text Tools

- `Ctrl+F3` opens Preview for common images, PDF, Excel, CSV, TXT, Markdown,
  JSON, XML, YAML, HTML, Word, and PowerPoint files.
- DOCX and PPTX have a lightweight built-in text fallback. If the free
  LibreOffice application is installed, mDIR uses it only when needed to
  preserve Office page and slide layout. Legacy DOC and PPT preview require
  LibreOffice.
- Image and document preparation is bounded and runs in the background.
  Oversized images are downsampled before terminal rendering.
- `F3` views supported text files up to 3 MiB. `F4` edits supported text files
  up to 8 MiB. Binary and unsupported document formats are refused rather
  than being loaded into memory as text.
- The `.[preview]` installation command in this README installs Pillow,
  PyMuPDF, openpyxl, and xlrd for the full Preview feature set.

## Performance and Safety

- Directory entries are read with one `os.scandir` metadata pass and retained
  in a cache for sorting, selection, summaries, and incremental repainting.
- Large tables are inserted in batches so the interface can draw during
  startup. Searches, Preview rendering, folder-size calculation, drive scans,
  and ZIP work run outside the UI thread.
- Content search is limited to 16 MiB per file; folder-size calculation stops
  after 20,000 files; Preview source images are bounded before rendering.
- Batch rename uses temporary names and rollback. ZIP creation publishes an
  archive only after successful completion, and ZIP extraction validates the
  whole member tree before it writes files.

## Top Shortcut Bar

The shortcut bar sits directly below the title bar. It can open folders in a
chosen file pane, launch files or programs, open websites, run PowerShell
commands, or trigger selected MDIR-P actions.

Click **Edit Links** to open the built-in Link Manager. It supports:

- Editing the name, type, target, pane, and program arguments
- Adding and removing links
- Moving links up or down
- Browsing for a file or folder
- Saving changes directly to the top bar

The Link Manager stores its settings in:

```text
%USERPROFILE%\.mdir-p-shortcuts.json
```

Up to 16 shortcut buttons are displayed. **Reload** remains available when the
JSON file is changed with an external editor.
The supported `type` values are `folder`, `file`, `program`, `web`, `command`,
and `action`.

```json
[
  {
    "label": "Downloads",
    "type": "folder",
    "target": "{home}\\Downloads",
    "pane": "active",
    "args": []
  },
  {
    "label": "Calculator",
    "type": "program",
    "target": "calc.exe",
    "pane": "active",
    "args": []
  },
  {
    "label": "MDIR GitHub",
    "type": "web",
    "target": "https://github.com/jtl-sun/mdir-p",
    "pane": "active",
    "args": []
  },
  {
    "label": "Preview",
    "type": "action",
    "target": "toggle_preview",
    "pane": "active",
    "args": []
  }
]
```

Folder shortcuts accept `active`, `left`, or `right` for `pane`. Available
placeholders are `{home}`, `{project}`, `{current}`, `{left}`, `{right}`,
`{selected}`, `{left_selected}`, and `{right_selected}`. This lets a program
link send the selected file—or files from both panes—to free external tools
such as LibreOffice, Meld, GIMP, or VLC without bundling those applications.
Supported actions are `toggle_ai_terminal`, `toggle_preview`, `search`,
`powershell_here`, `refresh_all`, and `hidden_system`.

## AI and Local Commands

The AI panel is a core mDIR feature and loads only when `F12` is pressed, so it
does not slow normal file browsing. Provider CLIs remain separately installed
tools. Codex uses workspace restrictions by default. PowerShell and local AI modes
can run commands directly on the computer, so use them only when full local
access is intended.

Type an explicit safe file request in the AI panel with `/file` or `/파일`,
for example `/파일 선택한 파일을 오른쪽으로 복사`. mDIR converts the request
into a local plan and shows the operation, files, and destination in a separate
approval dialog. The AI provider never receives permission to bypass this
dialog. Copy/Move/Rename/MkDir are recorded by Undo Center; Delete remains in
the operating-system Recycle Bin and is not automatically restored by mDIR.

## Advanced Lightweight Tools

These tools are loaded only when invoked. `mIndex` uses Python's built-in
SQLite and searches filenames inside the active folder tree; prefix a search
with `!` to rebuild that root. Duplicate Finder hashes only equal-size
candidates and uses Pillow's small perceptual image hash when image support is
installed. Folder comparison is read-only. Safe Sync copies new or changed
items from the active pane to the opposite pane and never deletes destination
items. Named Workspaces remember both folders, the active pane, and hidden-file
visibility. Macros record reviewed Copy/Move batches only—never Delete—and skip
missing sources or existing targets during playback.

## Project Layout

```text
mdir/
|-- app.py          Main application and event routing
|-- core.py         Shared file-manager widgets and operations
|-- base.py         Current dialogs and Windows drive integration
|-- file_operations.py  Background Copy, Move, and Delete engine
|-- file_pane.py    Cached metadata and editable paths
|-- fast_app.py     Large-directory and startup optimizations
|-- ai/             AI providers and conversation panel
|-- preview/        Image, PDF, Office, spreadsheet, and text preview
`-- ui/             Dialogs, search, rename, and text viewer
```

The repository has one supported launcher: `python -m mdir` (also installed as
`m` and `mdir`). Old version-named launchers and generated build directories
are intentionally excluded.

## Validation

```powershell
python -m mdir --check
python -m unittest discover -s tests -v
```

GitHub Actions runs the same self-check, test suite, and wheel build on Windows
for every push and pull request.

The 2.22.0 maintenance audit also verifies 1,005-item Copy, Move, and Delete,
background responsiveness and cancellation, shortcut ownership, selection and
auto-scroll, cached listing/sorting, automatic refresh, batch-rename rollback,
search patterns/content/cancellation, Preview navigation, safe text limits,
shortcut configuration, ZIP round trips, overwrite rules, path traversal,
symbolic links, invalid names, member-tree conflicts, archive self-input, and
left-to-right/right-to-left ZIP destination defaults. It also verifies that
`Enter` confirms Move and permanent Delete dialogs. During an active file
operation, `Esc` requests cancellation after the current top-level item.

MDIR-P is released under the [MIT License](LICENSE).
