"""Create an isolated Windows Terminal profile for mDIR.

The profile hides the host scrollbar and removes terminal padding so the
Textual dual-pane surface can use the entire terminal viewport.  It is written
as an official Windows Terminal JSON fragment and does not rewrite the user's
settings.json or alter any other profile.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile

PROFILE_NAME = "mDIR"
PROFILE_GUID = "{21932e3f-3ec6-51af-9a86-d1cbdc638265}"


def quoted_command(path: str | os.PathLike[str]) -> str:
    """Return a Windows command line that starts the installed mDIR module."""
    return f'"{Path(path)}" -P -m mdir'


def fragment_payload(
    python_path: str | os.PathLike[str],
    *,
    icon_path: str | os.PathLike[str] | None = None,
    starting_directory: str | os.PathLike[str] | None = None,
) -> dict[str, object]:
    """Build the dedicated mDIR Windows Terminal fragment payload."""
    profile: dict[str, object] = {
        "name": PROFILE_NAME,
        "guid": PROFILE_GUID,
        "commandline": quoted_command(python_path),
        # This host scrollbar/padding is outside Textual's renderable grid.
        "scrollbarState": "hidden",
        "padding": "0",
        "suppressApplicationTitle": False,
    }
    if starting_directory:
        profile["startingDirectory"] = str(starting_directory)
    if icon_path:
        profile["icon"] = str(icon_path)
    return {"profiles": [profile]}


def write_fragment(
    path: Path,
    python_path: str | os.PathLike[str],
    *,
    icon_path: str | os.PathLike[str] | None = None,
    starting_directory: str | os.PathLike[str] | None = None,
) -> None:
    """Atomically write the profile fragment as UTF-8 without a BOM."""
    payload = fragment_payload(
        python_path,
        icon_path=icon_path,
        starting_directory=starting_directory,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, ensure_ascii=False, indent=4) + "\n").encode(
        "utf-8"
    )
    with tempfile.NamedTemporaryFile(
        prefix="mdir-profile-",
        suffix=".json",
        dir=path.parent,
        delete=False,
    ) as pending:
        pending.write(encoded)
        pending_path = Path(pending.name)
    try:
        os.replace(pending_path, path)
    finally:
        pending_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--python", required=True, dest="python_path")
    parser.add_argument("--icon", dest="icon_path")
    parser.add_argument("--starting-directory", dest="starting_directory")
    args = parser.parse_args()
    write_fragment(
        args.output,
        args.python_path,
        icon_path=args.icon_path,
        starting_directory=args.starting_directory,
    )
    print(f"Windows Terminal profile written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
