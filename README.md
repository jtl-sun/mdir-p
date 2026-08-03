# MDIR-P

**MDIR for PowerShell. MDIR Plus.**

MDIR-P is a fast, keyboard-friendly dual-pane file manager for Windows
PowerShell and Windows Terminal. It brings the direct workflow of classic
DOS file managers to a modern interface with optional AI and document
preview features.

## Dedication

MDIR-P is a tribute to **Choi Jung Han**, the developer of the legendary
DOS-era file manager **MDIR**. His work inspired generations of users to
manage files quickly and efficiently from the keyboard.

## Highlights

- Fast dual-pane file management inspired by MDIR and Total Commander
- Responsive handling of folders containing 20,000 or more image files
- High-resolution preview for images, PDF documents, and Excel workbooks
- Mouse-wheel zoom and drag-to-pan in Preview
- Optional AI terminal with Codex, PowerShell, and Ollama providers
- Copy, move, rename, delete, search, drive selection, and editable paths
- Safe, size-limited text viewing and editing with `F3` and `F4`
- Total Commander-inspired default theme
- Configurable top shortcut bar for files, folders, programs, websites,
  PowerShell commands, and MDIR-P actions
- Windows Terminal and Korean IME support

## Requirements

- Windows 10 or Windows 11
- Python 3.11 or newer
- PowerShell or Windows Terminal

## Install

```powershell
git clone https://github.com/jtl-sun/mdir-p.git
cd mdir-p
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[preview]"
```

The tested Textual version is pinned by `pyproject.toml`, so a fresh install
uses the same UI framework version as the automated tests.

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
| `F3`                   | View a supported text file                  |
| `F4`                   | Edit a supported text file                  |
| `F5`                   | Copy                                        |
| `F6`                   | Move                                        |
| `F7`                   | Create a directory                          |
| `F8`                   | Delete                                      |
| `F9`                   | Select a drive                              |
| `F10`                  | Quit                                        |
| `F12`                  | Toggle the AI terminal                      |
| `Ctrl+F`               | Advanced search                             |
| `Ctrl+F3`              | Toggle Preview                              |
| `Ctrl+P`               | Open the command palette and theme selector |

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
placeholders are `{home}`, `{project}`, `{current}`, `{left}`, and `{right}`.
Supported actions are `toggle_ai_terminal`, `toggle_preview`, `search`,
`powershell_here`, `refresh_all`, and `hidden_system`.

## AI and Local Commands

Codex uses workspace restrictions by default. PowerShell and local AI modes
can run commands directly on the computer, so use them only when full local
access is intended.

## Project Layout

```text
mdir/
|-- app.py          Main application and event routing
|-- core.py         Shared file-manager widgets and operations
|-- base.py         Current dialogs and Windows drive integration
|-- file_pane.py    Cached metadata and editable paths
|-- fast_app.py     Large-directory and startup optimizations
|-- ai/             AI providers and conversation panel
|-- preview/        Image, PDF, and Excel preview
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

MDIR-P is released under the [MIT License](LICENSE).
