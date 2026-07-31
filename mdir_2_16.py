"""Backward-compatible launcher for MDIR-P 2.16.

New installations should use ``python -m mdir`` or the ``m`` command.
"""

from __future__ import annotations

from mdir.__main__ import main


if __name__ == "__main__":
    raise SystemExit(main())
