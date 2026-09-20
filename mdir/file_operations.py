from __future__ import annotations

import os
import shutil
import ctypes
import errno
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
from time import sleep
from typing import Callable, Iterable, Literal


FileOperation = Literal["copy", "move", "delete"]
ProgressCallback = Callable[[int, int, str], None]
PERMANENT_DELETE_THRESHOLD_BYTES = 10 * 1024**3


@dataclass
class FileOperationResult:
    """Summary returned after a copy, move, or delete batch."""

    operation: FileOperation
    total: int
    completed: int = 0
    skipped: int = 0
    cancelled: bool = False
    recycled: int = 0
    permanently_deleted: int = 0
    completed_names: list[str] = field(default_factory=list)
    completed_pairs: list[tuple[Path, Path]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    access_denied_items: list[Path] = field(default_factory=list)
    access_denied_permanent_items: list[Path] = field(default_factory=list)


def _same_path(first: Path, second: Path) -> bool:
    """Compare paths without a filesystem round-trip for every selected item."""
    return os.path.normcase(os.path.abspath(first)) == os.path.normcase(
        os.path.abspath(second)
    )


def _path_exists(path: Path) -> bool:
    """Return True for normal entries and broken symbolic links."""
    return os.path.lexists(path)


def _path_is_within(path: Path, parent: Path) -> bool:
    """Return whether path resolves inside parent (including parent itself)."""
    candidate = os.path.normcase(os.path.realpath(os.path.abspath(path)))
    root = os.path.normcase(os.path.realpath(os.path.abspath(parent)))
    try:
        return os.path.commonpath((candidate, root)) == root
    except ValueError:
        return False


def destination_conflicts(
    items: Iterable[Path],
    destination: Path,
    *,
    new_name: str | None = None,
) -> list[Path]:
    """Return existing top-level targets that would be overwritten."""
    paths = tuple(Path(item) for item in items)
    conflicts: list[Path] = []
    for source in paths:
        target_name = (
            new_name if len(paths) == 1 and new_name else source.name
        )
        target = Path(destination) / target_name
        if not _same_path(source, target) and _path_exists(target):
            conflicts.append(target)
    return conflicts


def _remove_existing_target(path: Path) -> None:
    """Remove one explicitly approved overwrite target."""
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def _temporary_sibling(path: Path, kind: str) -> Path:
    """Return a unique hidden sibling path used for staging or rollback."""
    while True:
        candidate = path.with_name(
            f".{path.name}.mdir-{kind}-{uuid.uuid4().hex}"
        )
        if not _path_exists(candidate):
            return candidate


def _copy_to_staging(source: Path, target: Path) -> Path:
    """Finish a copy at a hidden sibling before publishing the target name."""
    staging = _temporary_sibling(target, "copy")
    try:
        if source.is_dir() and not source.is_symlink():
            shutil.copytree(source, staging)
        else:
            shutil.copy2(source, staging)
        return staging
    except Exception:
        if _path_exists(staging):
            _remove_existing_target(staging)
        raise


def _publish_staging(staging: Path, target: Path) -> str | None:
    """Publish a staged copy and roll back the old target if publishing fails."""
    backup: Path | None = None
    if _path_exists(target):
        backup = _temporary_sibling(target, "backup")
        target.replace(backup)
    try:
        staging.replace(target)
    except Exception:
        try:
            if _path_exists(target):
                _remove_existing_target(target)
        finally:
            if backup is not None and _path_exists(backup):
                backup.replace(target)
        raise

    if backup is not None and _path_exists(backup):
        try:
            _remove_existing_target(backup)
        except Exception as exc:
            return f"old target backup could not be removed ({backup.name}): {exc}"
    return None


def _move_with_rollback(source: Path, target: Path) -> str | None:
    """Protect an approved existing target while moving a source over it."""
    backup: Path | None = None
    if _path_exists(target):
        backup = _temporary_sibling(target, "backup")
        target.replace(backup)
    try:
        shutil.move(str(source), str(target))
    except Exception:
        try:
            if _path_exists(target):
                _remove_existing_target(target)
        finally:
            if backup is not None and _path_exists(backup):
                backup.replace(target)
        raise

    if backup is not None and _path_exists(backup):
        try:
            _remove_existing_target(backup)
        except Exception as exc:
            return f"old target backup could not be removed ({backup.name}): {exc}"
    return None


def should_permanently_delete(*, is_directory: bool, size: int) -> bool:
    """Only individual files of 10 GiB or larger bypass the Recycle Bin."""
    return not is_directory and size >= PERMANENT_DELETE_THRESHOLD_BYTES


class RecycleBinError(OSError):
    """Failure returned by the legacy Windows Shell recycle operation."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = int(code)


_SHFILEOP_ERROR_MESSAGES = {
    0x71: "Source and destination refer to the same file",
    0x72: "Multiple source paths were supplied for one destination",
    0x73: "Rename operation specified multiple source files",
    0x74: "Source is a root directory and cannot be moved or renamed",
    0x75: "Operation was cancelled",
    0x76: "Destination is inside the source tree",
    0x78: "Administrator permission is required to access the source",
    0x79: "Path is too deep",
    0x7C: "Source or destination path is invalid",
    0x81: "File name is too long",
    0xB7: "Destination is read-only",
}


def recycle_bin_error_message(code: int, *, aborted: bool = False) -> str:
    """Translate SHFileOperation return codes without treating them as Win32 errors."""
    if aborted and not code:
        return "Recycle Bin operation was cancelled"
    detail = _SHFILEOP_ERROR_MESSAGES.get(int(code))
    if detail:
        return detail
    return f"Recycle Bin operation failed (shell code 0x{int(code):02X})"


def is_access_denied_error(exc: BaseException) -> bool:
    """Return True when a delete failure can reasonably be retried with UAC."""
    if isinstance(exc, RecycleBinError):
        return exc.code == 0x78
    if isinstance(exc, PermissionError):
        return True
    if isinstance(exc, OSError):
        winerror = getattr(exc, "winerror", None)
        if winerror in {5, 1314}:  # ACCESS_DENIED / PRIVILEGE_NOT_HELD
            return True
        if getattr(exc, "errno", None) in {errno.EACCES, errno.EPERM}:
            return True
    return False


def send_to_recycle_bin(path: Path) -> None:
    """Move one Windows filesystem item to the Recycle Bin.

    A recycle failure is reported to the caller instead of silently falling
    back to permanent deletion.  On non-Windows systems, deletion retains the
    previous permanent behavior for development and automated testing.
    """
    if os.name != "nt":
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
        return

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", ctypes.c_void_p),
            ("wFunc", ctypes.c_uint),
            ("pFrom", ctypes.c_wchar_p),
            ("pTo", ctypes.c_wchar_p),
            ("fFlags", ctypes.c_ushort),
            # Win32 BOOL is four bytes (not ctypes.c_bool's one byte).
            ("fAnyOperationsAborted", ctypes.c_int),
            ("hNameMappings", ctypes.c_void_p),
            ("lpszProgressTitle", ctypes.c_wchar_p),
        ]

    source = str(path.resolve(strict=False)) + "\0\0"
    operation = SHFILEOPSTRUCTW()
    operation.wFunc = 3  # FO_DELETE
    operation.pFrom = source
    operation.fFlags = 0x0040 | 0x0010 | 0x0004 | 0x0400
    result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(operation))
    if result or operation.fAnyOperationsAborted:
        detail = recycle_bin_error_message(
            int(result),
            aborted=bool(operation.fAnyOperationsAborted),
        )
        raise RecycleBinError(
            int(result),
            f"Could not move item to Recycle Bin ({detail})",
        )


def run_file_operation(
    operation: FileOperation,
    items: Iterable[Path],
    destination: Path | None = None,
    *,
    new_name: str | None = None,
    overwrite: bool = False,
    cancel_event: Event | None = None,
    pause_event: Event | None = None,
    progress: ProgressCallback | None = None,
) -> FileOperationResult:
    """Run a batch file operation without touching any UI objects.

    The caller is expected to run this function in a worker thread.  Progress
    is reported after each top-level item; UI callers should coalesce those
    notifications before repainting.
    """
    paths = tuple(Path(item) for item in items)
    if pause_event is None and cancel_event is not None:
        pause_event = getattr(cancel_event, "mdir_pause_event", None)
    result = FileOperationResult(operation=operation, total=len(paths))
    if operation in {"copy", "move"} and destination is None:
        raise ValueError(f"{operation} requires a destination")

    for index, source in enumerate(paths, start=1):
        while pause_event is not None and pause_event.is_set():
            if cancel_event is not None and cancel_event.is_set():
                break
            sleep(0.05)
        if cancel_event is not None and cancel_event.is_set():
            result.cancelled = True
            break

        display_name = source.name
        delete_permanently = False
        try:
            if operation == "delete":
                is_directory = source.is_dir() and not source.is_symlink()
                size = 0 if is_directory else int(source.stat().st_size)
                delete_permanently = should_permanently_delete(
                    is_directory=is_directory,
                    size=size,
                )
                if delete_permanently:
                    source.unlink()
                    result.permanently_deleted += 1
                else:
                    send_to_recycle_bin(source)
                    result.recycled += 1
            else:
                assert destination is not None
                target_name = (
                    new_name
                    if len(paths) == 1 and new_name
                    else source.name
                )
                target = destination / target_name
                if _same_path(source, target):
                    result.skipped += 1
                    if progress is not None:
                        progress(index, result.total, display_name)
                    continue
                if (
                    source.is_dir()
                    and not source.is_symlink()
                    and _path_is_within(target, source)
                ):
                    raise ValueError(
                        f"Cannot {operation} a folder into itself or its own subfolder"
                    )
                target_exists = _path_exists(target)
                if target_exists and not overwrite:
                    result.skipped += 1
                    if progress is not None:
                        progress(index, result.total, display_name)
                    continue
                warning: str | None = None
                if operation == "copy":
                    staging = _copy_to_staging(source, target)
                    try:
                        warning = _publish_staging(staging, target)
                    except Exception:
                        if _path_exists(staging):
                            _remove_existing_target(staging)
                        raise
                else:
                    warning = _move_with_rollback(source, target)
                display_name = target_name
                result.completed_pairs.append((source, target))
                if warning:
                    result.errors.append(f"{source.name}: {warning}")

            result.completed += 1
            result.completed_names.append(display_name)
        except Exception as exc:
            if operation == "delete" and is_access_denied_error(exc):
                result.access_denied_items.append(source)
                if delete_permanently:
                    result.access_denied_permanent_items.append(source)
            else:
                result.errors.append(f"{source.name}: {exc}")

        if progress is not None:
            progress(index, result.total, display_name)

    if cancel_event is not None and cancel_event.is_set():
        result.cancelled = True
    return result
