from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def open_with_default_app(path: Path) -> None:
    """Open a file with the desktop's registered application."""
    if os.name == "nt":
        os.startfile(str(path))
        return
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
        return
    opener = shutil.which("xdg-open")
    if opener:
        subprocess.Popen([opener, str(path)])
        return
    gio = shutil.which("gio")
    if gio:
        subprocess.Popen([gio, "open", str(path)])
        return
    raise OSError("No desktop opener was found (install xdg-utils).")
