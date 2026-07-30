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

| Key | Action |
| --- | --- |
| `Tab`, `Left`, `Right` | Switch file pane |
| `Enter` | Open a file or directory |
| `Space` | Mark an item |
| `F2` | Rename |
| `F3` | View a supported text file |
| `F4` | Edit a supported text file |
| `F5` | Copy |
| `F6` | Move |
| `F7` | Create a directory |
| `F8` | Delete |
| `F9` | Select a drive |
| `F10` | Quit |
| `F12` | Toggle the AI terminal |
| `Ctrl+F` | Advanced search |
| `Ctrl+F3` | Toggle Preview |
| `Ctrl+P` | Open the command palette and theme selector |

## AI and Local Commands

Codex uses workspace restrictions by default. PowerShell and local AI modes
can run commands directly on the computer, so use them only when full local
access is intended.

## Project Layout

```text
mdir/
|-- app.py          Main application and event routing
|-- core.py         Core file-manager widgets and operations
|-- file_pane.py    Cached metadata and editable paths
|-- fast_app.py     Large-directory and startup optimizations
|-- ai/             AI providers and conversation panel
|-- preview/        Image, PDF, and Excel preview
`-- ui/             Dialogs, search, rename, and text viewer
```

## Validation

```powershell
python -m mdir --check
python -m unittest discover -s tests -v
```

MDIR-P is released under the [MIT License](LICENSE).
