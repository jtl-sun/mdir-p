from __future__ import annotations

import ctypes
import os
from pathlib import Path
from typing import Iterable

from .file_operations import FileOperationResult


class ElevationCancelled(RuntimeError):
    """The user cancelled the Windows UAC prompt."""


class ElevationError(RuntimeError):
    """An elevated Windows Shell delete operation could not be started."""


# Native Windows Shell identifiers.
_CLSID_FILE_OPERATION = "{3AD05575-8857-4850-9277-11B85BDB8E09}"
_IID_IFILE_OPERATION = "{947AAB5F-0A5C-4C13-B4D6-4BF7836FC9F8}"
_IID_ISHELL_ITEM = "{43826D1E-E718-42EE-BC55-A1E261C37BFE}"

# COM / Shell constants used by the elevated IFileOperation broker.
_CLSCTX_LOCAL_SERVER = 0x00000004
_COINIT_APARTMENTTHREADED = 0x00000002
_COINIT_DISABLE_OLE1DDE = 0x00000004
_RPC_E_CHANGED_MODE = 0x80010106
_ERROR_CANCELLED_HRESULT = 0x800704C7

_FOF_SILENT = 0x0004
_FOF_NOCONFIRMATION = 0x0010
_FOF_NOERRORUI = 0x0400
_FOFX_SHOWELEVATIONPROMPT = 0x00040000
_FOFX_RECYCLEONDELETE = 0x00080000
_FOFX_REQUIREELEVATION = 0x10000000
_FOFX_ADDUNDORECORD = 0x20000000

# IFileOperation vtable indexes after IUnknown.
_IFILEOP_SET_OPERATION_FLAGS = 5
_IFILEOP_SET_OWNER_WINDOW = 9
_IFILEOP_DELETE_ITEM = 18
_IFILEOP_PERFORM_OPERATIONS = 21
_IFILEOP_GET_ANY_OPERATIONS_ABORTED = 22
_IUNKNOWN_RELEASE = 2


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class _BIND_OPTS3(ctypes.Structure):
    _fields_ = [
        ("cbStruct", ctypes.c_uint32),
        ("grfFlags", ctypes.c_uint32),
        ("grfMode", ctypes.c_uint32),
        ("dwTickCountDeadline", ctypes.c_uint32),
        ("dwTrackFlags", ctypes.c_uint32),
        ("dwClassContext", ctypes.c_uint32),
        ("locale", ctypes.c_uint32),
        ("pServerInfo", ctypes.c_void_p),
        ("hwnd", ctypes.c_void_p),
    ]


def _guid(value: str) -> _GUID:
    import uuid

    raw = uuid.UUID(value.strip("{}"))
    data = raw.bytes_le
    guid = _GUID()
    guid.Data1 = int.from_bytes(data[0:4], "little")
    guid.Data2 = int.from_bytes(data[4:6], "little")
    guid.Data3 = int.from_bytes(data[6:8], "little")
    guid.Data4[:] = data[8:16]
    return guid


def _hresult_u32(value: int) -> int:
    return int(value) & 0xFFFFFFFF


def _failed_hresult(value: int) -> bool:
    return bool(_hresult_u32(value) & 0x80000000)


def _format_hresult(value: int) -> str:
    return f"0x{_hresult_u32(value):08X}"


def _com_method(pointer: ctypes.c_void_p, index: int, restype, *argtypes):
    """Return one callable COM vtable method for a raw interface pointer."""
    if not pointer or not pointer.value:
        raise ElevationError("Windows Shell returned an empty COM interface")
    vtable_pointer = ctypes.cast(
        pointer,
        ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)),
    )
    address = vtable_pointer.contents[index]
    prototype_factory = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
    prototype = prototype_factory(restype, ctypes.c_void_p, *argtypes)
    return prototype(address)


def _release(pointer: ctypes.c_void_p | None) -> None:
    if not pointer or not pointer.value:
        return
    try:
        release = _com_method(pointer, _IUNKNOWN_RELEASE, ctypes.c_uint32)
        release(pointer)
    except Exception:
        # Release is best-effort during error unwinding.
        pass


def _normalise_owner_hwnd(owner_hwnd: int | None) -> int:
    """Return a usable top-level owner HWND for Windows elevation UI.

    Windows Terminal can expose child/XAML windows while mDIR tracks the
    foreground host.  CoGetObject's BIND_OPTS3.hwnd expects an owner window
    for the UAC/elevation UI, so normalise any supplied handle to its root.
    """
    if os.name != "nt" or not owner_hwnd:
        return 0
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.IsWindow.argtypes = [ctypes.c_void_p]
        user32.IsWindow.restype = ctypes.c_int
        user32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        user32.GetAncestor.restype = ctypes.c_void_p
        hwnd = int(owner_hwnd)
        if not user32.IsWindow(ctypes.c_void_p(hwnd)):
            return 0
        root = int(user32.GetAncestor(ctypes.c_void_p(hwnd), 2) or 0)  # GA_ROOT
        return root or hwnd
    except Exception:
        return int(owner_hwnd or 0)


def _prepare_elevation_owner(owner_hwnd: int | None) -> int:
    """Best-effort foreground preparation before Windows displays UAC.

    The decisive part is passing the HWND to BIND_OPTS3.  Restoring and
    foregrounding the same top-level window immediately beforehand prevents
    Windows from treating the permission UI as an unrelated background task
    that only flashes on the taskbar.
    """
    hwnd = _normalise_owner_hwnd(owner_hwnd)
    if os.name != "nt" or not hwnd:
        return 0
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.IsIconic.argtypes = [ctypes.c_void_p]
        user32.IsIconic.restype = ctypes.c_int
        user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
        user32.ShowWindow.restype = ctypes.c_int
        user32.BringWindowToTop.argtypes = [ctypes.c_void_p]
        user32.BringWindowToTop.restype = ctypes.c_int
        user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
        user32.SetForegroundWindow.restype = ctypes.c_int
        handle = ctypes.c_void_p(hwnd)
        if user32.IsIconic(handle):
            user32.ShowWindow(handle, 9)  # SW_RESTORE
        user32.BringWindowToTop(handle)
        user32.SetForegroundWindow(handle)
    except Exception:
        pass
    return hwnd


def _create_elevated_file_operation(owner_hwnd: int = 0) -> ctypes.c_void_p:
    """Create Microsoft's FileOperation COM broker through the UAC moniker.

    BIND_OPTS3.hwnd is intentionally populated so the Windows consent UI is
    owned by the mDIR/Windows Terminal window instead of appearing as a
    background taskbar notification.
    """
    ole32 = ctypes.WinDLL("ole32", use_last_error=True)
    ole32.CoGetObject.argtypes = [
        ctypes.c_wchar_p,
        ctypes.POINTER(_BIND_OPTS3),
        ctypes.POINTER(_GUID),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    ole32.CoGetObject.restype = ctypes.c_int32

    options = _BIND_OPTS3()
    options.cbStruct = ctypes.sizeof(_BIND_OPTS3)
    options.dwClassContext = _CLSCTX_LOCAL_SERVER
    owner_hwnd = _prepare_elevation_owner(owner_hwnd)
    options.hwnd = owner_hwnd or None

    iid = _guid(_IID_IFILE_OPERATION)
    output = ctypes.c_void_p()
    moniker = f"Elevation:Administrator!new:{_CLSID_FILE_OPERATION}"
    hr = int(
        ole32.CoGetObject(
            moniker,
            ctypes.byref(options),
            ctypes.byref(iid),
            ctypes.byref(output),
        )
    )
    if _hresult_u32(hr) == _ERROR_CANCELLED_HRESULT:
        raise ElevationCancelled(
            "Administrator permission request was cancelled"
        )
    if _failed_hresult(hr) or not output.value:
        raise ElevationError(
            "Windows could not create the Administrator file-operation broker "
            f"({_format_hresult(hr)})"
        )
    return output


def _create_shell_item(path: Path) -> ctypes.c_void_p:
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    shell32.SHCreateItemFromParsingName.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_void_p,
        ctypes.POINTER(_GUID),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    shell32.SHCreateItemFromParsingName.restype = ctypes.c_int32

    iid = _guid(_IID_ISHELL_ITEM)
    output = ctypes.c_void_p()
    hr = int(
        shell32.SHCreateItemFromParsingName(
            os.path.abspath(path),
            None,
            ctypes.byref(iid),
            ctypes.byref(output),
        )
    )
    if _failed_hresult(hr) or not output.value:
        raise ElevationError(
            f"Could not prepare protected item '{path.name}' "
            f"({_format_hresult(hr)})"
        )
    return output


def _operation_flags(*, recycle: bool) -> int:
    flags = (
        _FOF_SILENT
        | _FOF_NOCONFIRMATION
        | _FOF_NOERRORUI
        | _FOFX_SHOWELEVATIONPROMPT
        | _FOFX_REQUIREELEVATION
    )
    if recycle:
        flags |= _FOFX_RECYCLEONDELETE | _FOFX_ADDUNDORECORD
    return flags


def _partition_delete_paths(
    paths: tuple[Path, ...],
    permanent_paths: tuple[Path, ...],
) -> tuple[tuple[Path, ...], tuple[Path, ...], set[str]]:
    permanent_keys = {
        os.path.normcase(os.path.abspath(path)) for path in permanent_paths
    }
    recycle_paths = tuple(
        path
        for path in paths
        if os.path.normcase(os.path.abspath(path)) not in permanent_keys
    )
    permanent_batch = tuple(
        path
        for path in paths
        if os.path.normcase(os.path.abspath(path)) in permanent_keys
    )
    return recycle_paths, permanent_batch, permanent_keys


def _run_native_shell_delete(
    paths: tuple[Path, ...], *, recycle: bool, owner_hwnd: int = 0
) -> bool:
    """Delete one batch via an elevated Windows IFileOperation instance.

    Returns True when Windows reports that the operation was aborted.  The
    caller still checks actual path existence so partial operations are
    represented accurately.
    """
    if not paths:
        return False

    file_operation = _create_elevated_file_operation(owner_hwnd)
    shell_items: list[ctypes.c_void_p] = []
    try:
        flags = _operation_flags(recycle=recycle)
        operation_owner = _normalise_owner_hwnd(owner_hwnd)
        if operation_owner:
            set_owner = _com_method(
                file_operation,
                _IFILEOP_SET_OWNER_WINDOW,
                ctypes.c_int32,
                ctypes.c_void_p,
            )
            hr = int(
                set_owner(
                    file_operation,
                    ctypes.c_void_p(operation_owner),
                )
            )
            if _failed_hresult(hr):
                raise ElevationError(
                    "Windows rejected the mDIR owner window for the "
                    f"Administrator file operation ({_format_hresult(hr)})"
                )

        set_flags = _com_method(
            file_operation,
            _IFILEOP_SET_OPERATION_FLAGS,
            ctypes.c_int32,
            ctypes.c_uint32,
        )
        hr = int(set_flags(file_operation, flags))
        if _failed_hresult(hr):
            raise ElevationError(
                "Windows rejected the Administrator delete settings "
                f"({_format_hresult(hr)})"
            )

        delete_item = _com_method(
            file_operation,
            _IFILEOP_DELETE_ITEM,
            ctypes.c_int32,
            ctypes.c_void_p,
            ctypes.c_void_p,
        )
        for path in paths:
            item = _create_shell_item(path)
            shell_items.append(item)
            hr = int(delete_item(file_operation, item, None))
            if _failed_hresult(hr):
                raise ElevationError(
                    f"Windows could not queue '{path.name}' for deletion "
                    f"({_format_hresult(hr)})"
                )

        perform = _com_method(
            file_operation,
            _IFILEOP_PERFORM_OPERATIONS,
            ctypes.c_int32,
        )
        hr = int(perform(file_operation))
        if _hresult_u32(hr) == _ERROR_CANCELLED_HRESULT:
            raise ElevationCancelled(
                "Administrator permission request was cancelled"
            )
        if _failed_hresult(hr):
            raise ElevationError(
                "Administrator delete operation failed "
                f"({_format_hresult(hr)})"
            )

        aborted = ctypes.c_int(0)
        get_aborted = _com_method(
            file_operation,
            _IFILEOP_GET_ANY_OPERATIONS_ABORTED,
            ctypes.c_int32,
            ctypes.POINTER(ctypes.c_int),
        )
        hr = int(get_aborted(file_operation, ctypes.byref(aborted)))
        if _failed_hresult(hr):
            raise ElevationError(
                "Could not read the Administrator delete result "
                f"({_format_hresult(hr)})"
            )
        return bool(aborted.value)
    finally:
        for item in shell_items:
            _release(item)
        _release(file_operation)


def run_elevated_delete(
    items: Iterable[Path],
    *,
    permanent_items: Iterable[Path] = (),
    owner_hwnd: int = 0,
) -> FileOperationResult:
    """Retry protected deletes with Windows' native elevated Shell broker.

    The implementation deliberately avoids PowerShell and does not elevate the
    mDIR Python process.  Windows itself creates the signed FileOperation COM
    local server through the standard COM elevation moniker, shows UAC, and
    performs only the requested delete operation.
    """
    paths = tuple(Path(item) for item in items)
    permanent_paths = tuple(Path(item) for item in permanent_items)
    if not paths:
        return FileOperationResult(operation="delete", total=0)
    if os.name != "nt":
        raise ElevationError("Administrator retry is only available on Windows")

    recycle_paths, permanent_batch, permanent_keys = _partition_delete_paths(
        paths, permanent_paths
    )

    ole32 = ctypes.WinDLL("ole32", use_last_error=True)
    ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    ole32.CoInitializeEx.restype = ctypes.c_int32
    ole32.CoUninitialize.argtypes = []
    ole32.CoUninitialize.restype = None

    init_hr = int(
        ole32.CoInitializeEx(
            None,
            _COINIT_APARTMENTTHREADED | _COINIT_DISABLE_OLE1DDE,
        )
    )
    init_u32 = _hresult_u32(init_hr)
    initialized_here = not _failed_hresult(init_hr)
    if _failed_hresult(init_hr) and init_u32 != _RPC_E_CHANGED_MODE:
        raise ElevationError(
            f"Could not initialize Windows Shell COM ({_format_hresult(init_hr)})"
        )
    if init_u32 == _RPC_E_CHANGED_MODE:
        raise ElevationError(
            "Administrator delete requires a Windows STA worker thread"
        )

    aborted = False
    failure: ElevationError | ElevationCancelled | None = None
    try:
        # Keep the original mDIR policy: normal files/folders go to the Recycle
        # Bin; only individual files already classified as 10 GiB+ are deleted
        # permanently.  Separate operations are necessary because the recycle
        # policy is configured per IFileOperation instance.
        if recycle_paths:
            aborted = _run_native_shell_delete(
                recycle_paths,
                recycle=True,
                owner_hwnd=owner_hwnd,
            ) or aborted
        if permanent_batch and not aborted:
            aborted = _run_native_shell_delete(
                permanent_batch,
                recycle=False,
                owner_hwnd=owner_hwnd,
            ) or aborted
    except (ElevationError, ElevationCancelled) as exc:
        failure = exc
        aborted = isinstance(exc, ElevationCancelled)
    finally:
        if initialized_here:
            ole32.CoUninitialize()

    result = FileOperationResult(operation="delete", total=len(paths))
    for path in paths:
        if not os.path.lexists(path):
            result.completed += 1
            result.completed_names.append(path.name)
            key = os.path.normcase(os.path.abspath(path))
            if key in permanent_keys:
                result.permanently_deleted += 1
            else:
                result.recycled += 1
        else:
            result.errors.append(
                f"{path.name}: {failure or 'Administrator retry did not remove this item'}"
            )

    if failure is not None and result.completed == 0:
        raise failure
    if aborted and result.completed == 0:
        raise ElevationCancelled("Administrator delete operation was cancelled")
    if aborted:
        result.cancelled = True
    return result
