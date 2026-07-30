"""Backward-compatible launcher for MDIR-P 2.15.

New installations should use ``python -m mdir``.
"""

from __future__ import annotations

import sys

from mdir.app import MDirApp, self_check
from mdir.window import center_terminal_window


MDirAI215 = MDirApp


def main() -> int:
    if "--check" in sys.argv:
        return self_check()
    center_terminal_window()
    MDirApp().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
