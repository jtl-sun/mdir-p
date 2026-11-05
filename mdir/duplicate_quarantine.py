"""Safe duplicate quarantine: retain originals, rename collisions, and record moves.

Quarantine uses same-filesystem moves only. Cross-volume moves are rejected
rather than silently copy/delete a potentially large source file.
"""
from __future__ import annotations

import csv
import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

from .duplicate_cleanup import (
    DuplicateRow, _fingerprint_file, _hash_unchanged,
    plan_marked_exact_duplicates,
)
from .duplicate_review import DuplicateReviewStore

QUARANTINE_MARKER = ".mdir-quarantine-folder"


def smart_select_duplicates(
    rows: Iterable[DuplicateRow], store: DuplicateReviewStore,
) -> list[DuplicateRow]:
    """Select all removable Exact copies, retaining at least one per group.

    Explicit KEEP files always win. Otherwise retain a deterministic first
    accessible copy; never treat similar images as exact duplicates.
    """
    groups: dict[str, list[DuplicateRow]] = {}
    for row in rows:
        if row[0].startswith("Exact "):
            groups.setdefault(row[0], []).append(row)
    selected: list[DuplicateRow] = []
    for members in groups.values():
        available = [row for row in members if row[1].is_file()
                     and not row[1].is_symlink()
                     and not store.get(row[1]).changed]
        if len(available) < 2:
            continue
        protected = [row for row in available if store.get(row[1]).status == "keep"]
        if not protected:
            # Selection is only a proposal; the user can change the keeper.
            protected = [min(available, key=lambda row: str(row[1]).casefold())]
        protected_paths = {row[1] for row in protected}
        selected.extend(row for row in available if row[1] not in protected_paths)
    return selected


def next_quarantine_path(directory: Path, original: Path) -> Path:
    """Preserve extensions: name.ext, name-(01).ext, name-(02).ext, ..."""
    direct = directory / original.name
    if not direct.exists() and not direct.is_symlink():
        return direct
    for number in range(1, 100000):
        candidate = directory / f"{original.stem}-({number:02d}){original.suffix}"
        if not candidate.exists() and not candidate.is_symlink():
            return candidate
    raise FileExistsError(f"Too many filename collisions for {original.name}")


def _check_destination(directory: Path, root: Path) -> Path:
    directory = Path(directory).expanduser()
    if not directory.is_absolute():
        raise ValueError("Specify a full destination folder path.")
    if directory.is_symlink():
        raise ValueError("Quarantine folder cannot be a symbolic link.")
    directory.mkdir(parents=True, exist_ok=True)
    if not directory.is_dir():
        raise ValueError("Quarantine destination is not a directory.")
    resolved = directory.resolve(strict=True)
    if resolved == root.resolve(strict=True):
        raise ValueError("Quarantine destination cannot be the search root.")
    return resolved


def move_marked_to_quarantine(
    root: Path,
    rows: Iterable[DuplicateRow],
    chosen: Iterable[DuplicateRow],
    store: DuplicateReviewStore,
    destination: Path,
    *,
    on_progress: Callable[[int, int, Path], None] | None = None,
    cancel_event=None,
) -> tuple[list[DuplicateRow], list[str], Path]:
    """Move verified copies; keep original paths in a durable CSV journal.

    The journal is created before the first move. Each moved entry is recorded
    immediately; if its journal write fails, an attempt is made to undo that
    particular move. Recheck each group after prior moves before proceeding.
    """
    listing = list(rows)
    picked = list(chosen)
    valid, skipped = plan_marked_exact_duplicates(
        listing, ((group, path) for group, path, _ in picked), store
    )
    if skipped or len(valid) != len(picked):
        raise ValueError("Unsafe selection: " + (skipped[0] if skipped else
                         "Some selections cannot be moved."))
    directory = _check_destination(destination, root)
    if not picked:
        raise ValueError("No duplicate files selected.")
    if any(path.resolve(strict=True).is_relative_to(directory)
           for _, path, _ in picked):
        raise ValueError("Selected files already belong to the quarantine folder.")
    if any(path.stat().st_dev != directory.stat().st_dev for _, path, _ in picked):
        raise ValueError(
            "Quarantine must be on the same filesystem as selected files. "
            "Cross-drive moves are not supported by this safe-move version."
        )
    # This marker allows future duplicate scans to skip the quarantine tree.
    (directory / QUARANTINE_MARKER).touch(exist_ok=True)
    journal = directory / ("mdir-quarantine-" +
                datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".csv")
    moved: list[DuplicateRow] = []
    failures: list[str] = []
    remaining = listing.copy()
    with journal.open("x", newline="", encoding="utf-8-sig") as out:
        writer = csv.writer(out)
        writer.writerow(["status", "group", "original_path", "quarantine_path",
                         "bytes", "sha256", "moved_at"])
        out.flush()
        os.fsync(out.fileno())
        for index, row in enumerate(picked, 1):
            if cancel_event is not None and cancel_event.is_set():
                failures.append(f"Stopped; {len(picked) - index + 1} unprocessed.")
                break
            group, source, size = row
            target = None
            try:
                if row not in remaining:
                    raise ValueError("File is no longer in results.")
                decision = store.get(source)
                if decision.status == "keep" or decision.changed:
                    raise ValueError("KEEP or changed file is protected.")
                digest, metadata = _hash_unchanged(source, root)
                if metadata[0] != size:
                    raise ValueError("File size changed since scan.")
                survivors = [
                    other for other_group, other, other_size in remaining
                    if other_group == group and other != source and other_size == size
                    and other.resolve(strict=False) != directory
                ]
                verified = False
                for other in survivors:
                    try:
                        other_digest, other_meta = _hash_unchanged(other, root)
                        if other_meta[0] == size and other_digest == digest:
                            verified = True
                            break
                    except (OSError, ValueError):
                        continue
                if not verified:
                    raise ValueError("No verified matching file remains at the original location.")
                if _fingerprint_file(source, root) != metadata:
                    raise ValueError("Source changed before move.")
                target = next_quarantine_path(directory, source)
                if target.exists() or target.is_symlink():
                    raise FileExistsError(f"Destination already exists: {target}")
                os.rename(source, target)
                try:
                    writer.writerow(["MOVED", group, str(source), str(target),
                                     size, digest,
                                     datetime.now().astimezone().isoformat(timespec="seconds")])
                    out.flush()
                    os.fsync(out.fileno())
                except (OSError, ValueError):
                    # Keep the original recoverable if history recording fails.
                    if not source.exists():
                        os.rename(target, source)
                    raise
                remaining.remove(row)
                moved.append(row)
            except (OSError, ValueError) as exc:
                failures.append(f"{source}: {exc}")
            if on_progress is not None:
                on_progress(index, len(picked), source)
    return moved, failures, journal
