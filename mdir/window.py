from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes
from pathlib import Path


DEFAULT_WINDOW_WIDTH = 1480
DEFAULT_WINDOW_HEIGHT = 850
WINDOW_WORK_AREA_MARGIN = 32
WINDOW_RESIZE_SETTLE_SECONDS = 0.015
APP_WINDOW_TITLE = "mDIR"
WM_SETICON = 0x0080
ICON_SMALL = 0
ICON_BIG = 1
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
_APP_ICON_HANDLES: list[int] = []


def terminal_icon_path() -> Path:
    """Return the packaged multi-resolution mDIR icon."""
    return Path(__file__).resolve().parent / "assets" / "mdir.ico"


def set_terminal_title(title: str = APP_WINDOW_TITLE) -> str | None:
    """Set the active console/Windows Terminal tab title on Windows."""
    if os.name != "nt":
        return None
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.GetConsoleTitleW.argtypes = [wintypes.LPWSTR, wintypes.DWORD]
        kernel32.GetConsoleTitleW.restype = wintypes.DWORD
        kernel32.SetConsoleTitleW.argtypes = [wintypes.LPCWSTR]
        kernel32.SetConsoleTitleW.restype = wintypes.BOOL
        buffer = ctypes.create_unicode_buffer(1024)
        length = kernel32.GetConsoleTitleW(buffer, len(buffer))
        previous = buffer.value if length else ""
        if not kernel32.SetConsoleTitleW(title):
            return None
        return previous
    except (AttributeError, OSError):
        return None


def restore_terminal_title(previous_title: str | None) -> None:
    """Restore the title that was visible before mDIR started."""
    if os.name != "nt" or previous_title is None:
        return
    try:
        ctypes.windll.kernel32.SetConsoleTitleW(previous_title)
    except (AttributeError, OSError):
        pass


def set_terminal_icon(icon_path: Path | None = None) -> bool:
    """Apply the mDIR icon to a classic Windows console window."""
    if os.name != "nt":
        return False
    path = icon_path or terminal_icon_path()
    if not path.is_file():
        return False
    try:
        user32 = _configure_user32()
        window = user32.GetForegroundWindow()
        if not window:
            return False
        class_name_buffer = ctypes.create_unicode_buffer(256)
        if not user32.GetClassNameW(
            window,
            class_name_buffer,
            len(class_name_buffer),
        ):
            return False
        if class_name_buffer.value != "ConsoleWindowClass":
            return False

        user32.LoadImageW.argtypes = [
            wintypes.HINSTANCE,
            wintypes.LPCWSTR,
            wintypes.UINT,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        user32.LoadImageW.restype = wintypes.HANDLE
        user32.SendMessageW.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        user32.SendMessageW.restype = wintypes.LPARAM

        loaded: list[int] = []
        for icon_kind, size in ((ICON_SMALL, 16), (ICON_BIG, 32)):
            handle = user32.LoadImageW(
                None,
                str(path),
                IMAGE_ICON,
                size,
                size,
                LR_LOADFROMFILE,
            )
            if handle:
                loaded.append(int(handle))
                user32.SendMessageW(window, WM_SETICON, icon_kind, int(handle))
        _APP_ICON_HANDLES.extend(loaded)
        return bool(loaded)
    except (AttributeError, OSError):
        return False


def set_terminal_identity() -> str | None:
    """Apply the mDIR title and the supported terminal-window icon."""
    previous_title = set_terminal_title()
    set_terminal_icon()
    return previous_title


def centered_window_bounds(
    work_left: int,
    work_top: int,
    work_right: int,
    work_bottom: int,
    requested_width: int = DEFAULT_WINDOW_WIDTH,
    requested_height: int = DEFAULT_WINDOW_HEIGHT,
    margin: int = WINDOW_WORK_AREA_MARGIN,
) -> tuple[int, int, int, int]:
    """Return a centered window rectangle fitted inside a monitor work area."""
    work_width = max(1, work_right - work_left)
    work_height = max(1, work_bottom - work_top)
    available_width = max(1, work_width - min(margin, work_width - 1))
    available_height = max(1, work_height - min(margin, work_height - 1))
    width = min(max(1, requested_width), available_width)
    height = min(max(1, requested_height), available_height)
    left = work_left + (work_width - width) // 2
    top = work_top + (work_height - height) // 2
    return left, top, width, height


class _MonitorInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


def _configure_user32():
    """Configure the Win32 signatures used by the terminal window helpers."""
    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetClassNameW.argtypes = [
        wintypes.HWND,
        wintypes.LPWSTR,
        ctypes.c_int,
    ]
    user32.GetClassNameW.restype = ctypes.c_int
    user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.MonitorFromWindow.restype = wintypes.HMONITOR
    user32.GetMonitorInfoW.argtypes = [
        wintypes.HMONITOR,
        ctypes.POINTER(_MonitorInfo),
    ]
    user32.GetMonitorInfoW.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.IsZoomed.argtypes = [wintypes.HWND]
    user32.IsZoomed.restype = wintypes.BOOL
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL
    return user32


def _position_terminal_window(
    width: int = DEFAULT_WINDOW_WIDTH,
    height: int = DEFAULT_WINDOW_HEIGHT,
) -> bool:
    """Resize and center the foreground terminal without hiding it."""
    if os.name != "nt":
        return False

    user32 = _configure_user32()
    window = user32.GetForegroundWindow()
    if not window:
        return False

    class_name_buffer = ctypes.create_unicode_buffer(256)
    if not user32.GetClassNameW(
        window,
        class_name_buffer,
        len(class_name_buffer),
    ):
        return False

    class_name = class_name_buffer.value
    is_terminal = (
        "CASCADIA" in class_name.upper()
        or class_name == "ConsoleWindowClass"
    )
    if not is_terminal:
        return False

    monitor = user32.MonitorFromWindow(window, 2)
    if not monitor:
        return False

    monitor_info = _MonitorInfo()
    monitor_info.cbSize = ctypes.sizeof(_MonitorInfo)
    if not user32.GetMonitorInfoW(monitor, ctypes.byref(monitor_info)):
        return False

    work = monitor_info.rcWork
    left, top, fitted_width, fitted_height = centered_window_bounds(
        work.left,
        work.top,
        work.right,
        work.bottom,
        width,
        height,
    )

    # Avoid an unnecessary restore animation for an already normal window.
    if user32.IsZoomed(window):
        user32.ShowWindow(window, 9)

    no_z_order = 0x0004
    no_activate = 0x0010
    return bool(
        user32.SetWindowPos(
            window,
            None,
            left,
            top,
            fitted_width,
            fitted_height,
            no_z_order | no_activate,
        )
    )


def center_terminal_window(
    width: int = DEFAULT_WINDOW_WIDTH,
    height: int = DEFAULT_WINDOW_HEIGHT,
) -> bool:
    """Resize and center the terminal, then let its character grid settle."""
    positioned = _position_terminal_window(width, height)
    if positioned:
        # Let Windows Terminal propagate its pixel resize to the ConPTY grid
        # before Textual reads the initial row and column count.
        time.sleep(WINDOW_RESIZE_SETTLE_SECONDS)
    return positioned
