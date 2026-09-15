"""Windows keyboard message loop with scoped shortcut capture support."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import threading
from textual.message import Message


class PreviewShortcut(Message):
    pass


class PreviewKeyState:
    def __init__(self):
        self.f3_down = False
        self.modifiers = set()

    def observe(self, key: int, down: bool, foreground: bool) -> bool:
        if key in (0xA2, 0xA3, 0xA0, 0xA1, 0xA4, 0xA5, 0x5B, 0x5C):
            if down:
                self.modifiers.add(key)
            else:
                self.modifiers.discard(key)
        control_only = bool(self.modifiers & {0xA2, 0xA3}) and not bool(
            self.modifiers - {0xA2, 0xA3})
        return self.update(key, down, control_only, foreground)

    def update(self, key: int, down: bool, control: bool, foreground: bool) -> bool:
        if key != 0x72:
            return False
        first_down = down and not self.f3_down
        self.f3_down = down
        return first_down and control and foreground


class PreviewHotkey:
    """Observe F3, or delegate capture to a subclass's scoped key matcher."""
    def __init__(self, terminal_hwnd: int, notify):
        self.terminal_hwnd = terminal_hwnd
        self.notify = notify
        self.thread = None
        self.thread_id = 0
        self.ready = threading.Event()
        self.stop = threading.Event()
        self.active = False
        self.error = ''

    def start(self) -> bool:
        if os.name != 'nt' or not self.terminal_hwnd:
            return False
        self.thread = threading.Thread(target=self._run, name='MDIR-Shortcut-Key', daemon=True)
        self.thread.start()
        self.ready.wait(1)
        return self.active

    def shutdown(self) -> bool:
        self.stop.set()
        if self.thread_id:
            ctypes.windll.user32.PostThreadMessageW(self.thread_id, 0x12, 0, 0)
        if self.thread:
            self.thread.join(2)
        return self.thread is None or not self.thread.is_alive()

    def _run(self):
        # Keep ctypes signatures private; Preview's mouse hook runs concurrently.
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        hook = None
        callback = None
        try:
            self.thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
            message = wintypes.MSG()
            user32.PeekMessageW(ctypes.byref(message), None, 0, 0, 0)
            state = PreviewKeyState()
            proc_type = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

            class KeyData(ctypes.Structure):
                _fields_ = [('vkCode', wintypes.DWORD), ('scanCode', wintypes.DWORD),
                            ('flags', wintypes.DWORD), ('time', wintypes.DWORD),
                            ('dwExtraInfo', ctypes.c_size_t)]

            user32.CallNextHookEx.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
            user32.CallNextHookEx.restype = ctypes.c_ssize_t
            user32.GetForegroundWindow.restype = wintypes.HWND
            user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
            user32.GetAsyncKeyState.restype = ctypes.c_short
            # Seed held modifiers before installing the callback. Thereafter
            # use transitions: async key state is not yet updated in the hook.
            state.modifiers = {key for key in (0xA2, 0xA3, 0xA0, 0xA1, 0xA4, 0xA5, 0x5B, 0x5C)
                               if user32.GetAsyncKeyState(key) & 0x8000}
            matcher = getattr(self, 'matcher', None)
            if matcher is not None:
                matcher.modifiers = set(state.modifiers)

            @proc_type
            def callback(code, kind, data):
                try:
                    if code >= 0 and kind in (0x100, 0x104, 0x101, 0x105):
                        key = ctypes.cast(data, ctypes.POINTER(KeyData)).contents.vkCode
                        foreground = int(user32.GetForegroundWindow() or 0) == self.terminal_hwnd
                        if matcher is not None:
                            capture = matcher.feed(key, kind in (0x100, 0x104), foreground)
                            if capture.key is not None:
                                self.notify(capture.key, capture.epoch)
                            if capture.consume:
                                return 1  # Do not let Terminal run a conflicting action.
                        elif state.observe(key, kind in (0x100, 0x104), foreground):
                            self.notify()
                except Exception:
                    pass
                return user32.CallNextHookEx(None, code, kind, data)

            user32.SetWindowsHookExW.argtypes = [ctypes.c_int, proc_type, wintypes.HINSTANCE, wintypes.DWORD]
            user32.SetWindowsHookExW.restype = wintypes.HANDLE
            user32.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
            module = ctypes.windll.kernel32.GetModuleHandleW
            module.argtypes = [wintypes.LPCWSTR]
            module.restype = wintypes.HMODULE
            hook = user32.SetWindowsHookExW(13, callback, module(None), 0)
            if not hook:
                raise OSError('Windows shortcut monitor could not start')
            self.active = True
            self.ready.set()
            while not self.stop.is_set() and user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(message))
                user32.DispatchMessageW(ctypes.byref(message))
        except Exception as exc:
            self.error = str(exc)
        finally:
            self.active = False
            if hook:
                user32.UnhookWindowsHookEx(hook)
            self.thread_id = 0
            self.ready.set()
