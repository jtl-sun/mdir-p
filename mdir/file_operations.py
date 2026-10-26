from __future__ import annotations

import os
import ntpath
import shutil
import ctypes
import errno
import stat
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
from time import sleep
from typing import Callable, Iterable, Literal

from .progress import OperationCancelled, ProgressTracker


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


_IS_WINDOWS = os.name == "nt"
_TRANSIENT_COPY_WINERRORS = {2, 3}
_COPY_RETRY_DELAYS = (0.03, 0.08)


def _windows_extended_path(path: os.PathLike[str] | str) -> str:
    """Return an absolute filesystem path that is long-path safe on Windows.

    Prefixing the *root* supplied to shutil.copytree means every child path
    produced during recursive traversal inherits the Win32 extended-path form,
    avoiding MAX_PATH failures deep inside projects such as Unity caches.
    """
    raw = os.fspath(path)
    if not _IS_WINDOWS:
        return os.path.abspath(raw)
    if raw.startswith("\\\\?\\"):
        return raw
    absolute = ntpath.abspath(raw)
    if absolute.startswith("\\\\"):
        return "\\\\?\\UNC\\" + absolute[2:]
    return "\\\\?\\" + absolute


def _path_exists(path: os.PathLike[str] | str) -> bool:
    """Return True for normal entries and broken symbolic links."""
    return os.path.lexists(_windows_extended_path(path))


def _is_directory(path: os.PathLike[str] | str) -> bool:
    fs_path = _windows_extended_path(path)
    return os.path.isdir(fs_path) and not os.path.islink(fs_path)


def _replace_path(source: Path, target: Path) -> None:
    os.replace(_windows_extended_path(source), _windows_extended_path(target))


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
    """Remove an approved path, retrying Windows read-only entries only."""
    fs_path = _windows_extended_path(path)

    def remove_readonly(function, failed_path, exc_info):
        exc = exc_info[1]
        if (not _IS_WINDOWS or not isinstance(exc, PermissionError)
                or os.stat(failed_path, follow_symlinks=False).st_mode & stat.S_IWRITE):
            raise exc
        os.chmod(failed_path, stat.S_IWRITE)
        function(failed_path)

    if os.path.isdir(fs_path) and not os.path.islink(fs_path):
        shutil.rmtree(fs_path, onerror=remove_readonly)
    else:
        try:
            os.unlink(fs_path)
        except PermissionError as exc:
            remove_readonly(os.unlink, fs_path, (type(exc), exc, exc.__traceback__))


def _temporary_sibling(path: Path, kind: str) -> Path:
    """Return a short hidden sibling used for staging or rollback.

    The previous name embedded the full target name plus a 32-character UUID.
    That made already-deep destination trees even deeper during safe staging.
    Keep the same transactional sibling design but use a compact unique name.
    """
    code = {"copy": "c", "backup": "b"}.get(kind, (kind[:1] or "x"))
    while True:
        candidate = path.with_name(f".~m{code}-{uuid.uuid4().hex[:12]}")
        if not _path_exists(candidate):
            return candidate


def _is_retryable_copy_error(exc: BaseException, source: os.PathLike[str] | str) -> bool:
    """Return True only for transient Windows missing-path copy errors."""
    if not _IS_WINDOWS or not isinstance(exc, OSError):
        return False
    winerror = getattr(exc, "winerror", None)
    if winerror not in _TRANSIENT_COPY_WINERRORS:
        return False
    # Retry only while the source still exists.  Never silently skip files that
    # disappeared from a live project while it was being copied.
    return _path_exists(source)


def _copy2_with_retry(
    source: os.PathLike[str] | str,
    target: os.PathLike[str] | str,
    *,
    follow_symlinks: bool = True,
):
    """copy2 with long-path support and two cheap retries for WinError 2/3."""
    source_fs = _windows_extended_path(source)
    target_fs = _windows_extended_path(target)
    for attempt in range(len(_COPY_RETRY_DELAYS) + 1):
        try:
            return shutil.copy2(
                source_fs,
                target_fs,
                follow_symlinks=follow_symlinks,
            )
        except OSError as exc:
            if attempt >= len(_COPY_RETRY_DELAYS) or not _is_retryable_copy_error(
                exc, source_fs
            ):
                raise
            sleep(_COPY_RETRY_DELAYS[attempt])
    raise AssertionError("unreachable")


def _copy_with_progress_and_retry(
    source: os.PathLike[str] | str,
    target: os.PathLike[str] | str,
    tracker: ProgressTracker | None,
) -> str:
    """Copy one file with progress reporting plus transient-error retries.

    Without a tracker this defers to _copy2_with_retry. With a tracker the
    chunked progress copy is retried as a whole; transient WinError 2/3
    failures surface when the file is opened, before progress advances, and
    begin_item resets the per-item counters if a retry does occur.
    """
    if tracker is None:
        return _copy2_with_retry(source, target)
    for attempt in range(len(_COPY_RETRY_DELAYS) + 1):
        try:
            return _copy_with_progress(str(source), str(target), tracker)
        except OSError as exc:
            if attempt >= len(_COPY_RETRY_DELAYS) or not _is_retryable_copy_error(
                exc, source
            ):
                raise
            sleep(_COPY_RETRY_DELAYS[attempt])
    raise AssertionError("unreachable")


def _copy_to_staging(source: Path, target: Path, tracker: ProgressTracker | None = None) -> Path:
    """Finish a copy at a hidden sibling before publishing the target name."""
    staging = _temporary_sibling(target, "copy")
    try:
        source_fs = _windows_extended_path(source)
        staging_fs = _windows_extended_path(staging)
        if _is_directory(source):
            shutil.copytree(
                source_fs,
                staging_fs,
                copy_function=lambda s, d: _copy_with_progress_and_retry(s, d, tracker),
            )
        else:
            _copy_with_progress_and_retry(source_fs, staging_fs, tracker)
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
        _replace_path(target, backup)
    try:
        _replace_path(staging, target)
    except Exception:
        try:
            if _path_exists(target):
                _remove_existing_target(target)
        finally:
            if backup is not None and _path_exists(backup):
                _replace_path(backup, target)
        raise

    if backup is not None and _path_exists(backup):
        try:
            _remove_existing_target(backup)
        except Exception as exc:
            return f"old target backup could not be removed ({backup.name}): {exc}"
    return None


def _move_with_rollback(source: Path, target: Path, tracker: ProgressTracker | None = None) -> str | None:
    """Protect an approved existing target while moving a source over it."""
    backup: Path | None = None
    if _path_exists(target):
        backup = _temporary_sibling(target, "backup")
        _replace_path(target, backup)
    published = False
    try:
        try:
            _replace_path(source, target)
        except OSError as exc:
            if exc.errno != errno.EXDEV and getattr(exc, "winerror", None) != 17:
                raise
            staging = _copy_to_staging(source, target, tracker)
            try:
                _replace_path(staging, target)
            except Exception:
                if _path_exists(staging):
                    _remove_existing_target(staging)
                raise
            published = True
            # Once source cleanup begins, retain the complete destination even
            # if cleanup fails part way through a directory tree.
            _remove_existing_target(source)
        else:
            published = True
    except Exception as exc:
        if published:
            raise OSError(
                f"Destination copy retained at {target}; source cleanup failed: {exc}"
                + (f"; old target retained at {backup}" if backup is not None else "")
            ) from exc
        try:
            if _path_exists(target):
                _remove_existing_target(target)
        finally:
            if backup is not None and _path_exists(backup):
                _replace_path(backup, target)
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


def _estimate_size(path: Path) -> int:
    """Best-effort byte estimate for top-level items, including nested files."""
    try:
        if not path.is_dir() or path.is_symlink():
            return max(0, path.stat().st_size)
        total = 0
        for root, dirs, files in os.walk(path, followlinks=False):
            for name in files:
                try:
                    total += max(0, (Path(root) / name).stat().st_size)
                except OSError:
                    pass
        return total
    except OSError:
        return 0


def _copy_with_progress(source: str, target: str, tracker: ProgressTracker | None) -> str:
    """Copy data in cancellable chunks and preserve file metadata."""
    if tracker is None:
        return shutil.copy2(source, target)
    size = _estimate_size(Path(source))
    tracker.begin_item(str(source), size)
    with open(source, "rb") as src, open(target, "wb") as dst:
        while True:
            tracker.checkpoint()
            block = src.read(1024 * 1024)
            if not block:
                break
            dst.write(block)
            tracker.advance(len(block))
    shutil.copystat(source, target)
    return target


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
    tracker: ProgressTracker | None = None,
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
    if tracker is not None:
        tracker.set_totals(items=len(paths), bytes_total=sum(_estimate_size(p) for p in paths))
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
        item_size = _estimate_size(source) if tracker is not None else 0
        item_start = tracker.snapshot().bytes_done if tracker is not None else 0
        if tracker is not None:
            try:
                tracker.begin_item(str(source), item_size if not source.is_dir() else 0)
            except OperationCancelled:
                result.cancelled = True
                break
        delete_permanently = False
        try:
            if operation == "delete":
                is_directory = _is_directory(source)
                size = 0 if is_directory else int(os.stat(_windows_extended_path(source)).st_size)
                delete_permanently = should_permanently_delete(
                    is_directory=is_directory,
                    size=size,
                )
                if delete_permanently:
                    os.unlink(_windows_extended_path(source))
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
                    if tracker is not None:
                        tracker.complete_item(remaining_bytes=item_size)
                    if progress is not None:
                        progress(index, result.total, display_name)
                    continue
                if (
                    _is_directory(source)
                    and _path_is_within(target, source)
                ):
                    raise ValueError(
                        f"Cannot {operation} a folder into itself or its own subfolder"
                    )
                target_exists = _path_exists(target)
                if target_exists and not overwrite:
                    result.skipped += 1
                    if tracker is not None:
                        tracker.complete_item(remaining_bytes=item_size)
                    if progress is not None:
                        progress(index, result.total, display_name)
                    continue
                warning: str | None = None
                if operation == "copy":
                    staging = _copy_to_staging(source, target, tracker)
                    try:
                        warning = _publish_staging(staging, target)
                    except Exception:
                        if _path_exists(staging):
                            _remove_existing_target(staging)
                        raise
                else:
                    warning = _move_with_rollback(source, target, tracker)
                display_name = target_name
                result.completed_pairs.append((source, target))
                if warning:
                    result.errors.append(f"{source.name}: {warning}")

            result.completed += 1
            result.completed_names.append(display_name)
        except OperationCancelled:
            result.cancelled = True
            break
        except Exception as exc:
            if operation == "delete" and is_access_denied_error(exc):
                result.access_denied_items.append(source)
                if delete_permanently:
                    result.access_denied_permanent_items.append(source)
            else:
                result.errors.append(f"{source.name}: {exc}")

        if tracker is not None:
            transferred = tracker.snapshot().bytes_done - item_start
            tracker.complete_item(remaining_bytes=max(0, item_size - transferred))
        if progress is not None:
            progress(index, result.total, display_name)

    if cancel_event is not None and cancel_event.is_set():
        result.cancelled = True
    if tracker is not None:
        tracker.finish("cancelled" if result.cancelled else "completed")
    return result
