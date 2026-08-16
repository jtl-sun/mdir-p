from __future__ import annotations

import sys

from .app import MDirApp, self_check
from .window import (
    center_terminal_window,
    restore_terminal_title,
    set_terminal_identity,
)


def main() -> int:
    if "--check" in sys.argv:
        return self_check()
    previous_title = set_terminal_identity()
    try:
        center_terminal_window()
        MDirApp().run()
    finally:
        restore_terminal_title(previous_title)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
