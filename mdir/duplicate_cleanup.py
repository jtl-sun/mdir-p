"""Conservative single-file cleanup of already verified exact-duplicate groups.

Only the Windows Recycle Bin may receive a confirmed selected file.
Never permanently delete, process visually similar results, or remove the
last verified copy. All paths and content are verified again before recycle.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Callable, Iterable

from .file_operations import send_to_recycle_bin
from .duplicate_review import DuplicateReviewStore

DuplicateRow = tuple[str, Path, int]


def _fingerprint_file(path: Path, root: Path) -> tuple[int, int, int, int]:
    """Reject symlinks, directories and paths outside the chosen search root."""
    if path.is_symlink():
        raise ValueError(f"Symbolic links cannot be recycled here: {path}")
    if not path.is_file():
        raise ValueError(f"File unavailable or no longer regular: {path}")
    if not path.resolve(strict=True).is_relative_to(root.resolve(strict=True)):
        raise ValueError(f"File is outside the scanned folder: {path}")
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, stat.st_dev, stat.st_ino


def _hash_unchanged(path: Path, root: Path) -> tuple[str, tuple[int, int, int, int]]:
    before = _fingerprint_file(path, root)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    if _fingerprint_file(path, root) != before:
        raise ValueError(f"File changed during verification: {path}")
    return digest.hexdigest(), before


def recycle_selected_exact_duplicate(
    root: Path,
    rows: Iterable[DuplicateRow],
    selected: DuplicateRow,
    store: DuplicateReviewStore,
    *,
    recycle: Callable[[Path], None] | None = None,
) -> Path:
    """Recycle one explicitly selected exact duplicate after re-verification.

    Caller must separately obtain user confirmation. For regular runtime use
    the Windows Recycle Bin is required; no Unix permanent-delete fallback.
    A test can inject a simulated recycle callable.
    Returns the surviving matching file path on success.
    """
    group, path, scanned_size = selected
    if not group.startswith("Exact "):
        raise ValueError("Only byte-identical Exact groups support deletion.")
    if path == root or path == root.parent:
        raise ValueError("Cannot delete the search root.")
    decision = store.get(path)
    if decision.status == "keep" or decision.changed:
        raise ValueError("KEEP or changed files are protected. Review them first.")
    peers = [
        candidate
        for candidate_group, candidate, candidate_size in rows
        if candidate_group == group and candidate != path
        and candidate_size == scanned_size
    ]
    if not peers:
        raise ValueError("No other listed copy remains in this Exact group.")
    selected_hash, selected_meta = _hash_unchanged(path, root)
    if selected_meta[0] != scanned_size:
        raise ValueError("Selected file size changed since the duplicate scan.")

    surviving: Path | None = None
    for other in peers:
        try:
            other_hash, other_meta = _hash_unchanged(other, root)
            if other_meta[0] == scanned_size and other_hash == selected_hash:
                surviving = other
                break
        except (OSError, ValueError):
            continue
    if surviving is None:
        raise ValueError(
            "No remaining byte-identical copy could be re-verified. "
            "Nothing was recycled."
        )
    if _fingerprint_file(path, root) != selected_meta:
        raise ValueError("Selected file changed after verification.")

    if recycle is None:
        if os.name != "nt":
            raise OSError("Recycle operation is available only on Windows.")
        recycle = send_to_recycle_bin
    recycle(path)
    return surviving
