"""One Tk event loop owns both independent no-activate thumbnail windows."""
from __future__ import annotations

import ctypes
import math
import os
import threading
import time
from collections import OrderedDict
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

from textual.message import Message

from .preview.native import PaneLayout, calculate_pane_rectangle, windows_terminal_grid_rectangle
from .thumbnail import IMAGE_EXTENSIONS, SIZES, ThumbnailItem, ThumbnailLoader, grid_columns, visible_indices
from .selection_style import MARK_BACKGROUND, MARK_FOREGROUND, MARK_BORDER, CURSOR_BACKGROUND, MARK_PREFIX


@dataclass(frozen=True)
class PaneState:
    side: str
    directory: Path
    revision: tuple
    items: tuple[ThumbnailItem, ...]
    current: int
    marked: frozenset[Path]
    size: int
    active: bool
    layout: PaneLayout
    palette: tuple[str, str, str, str]
    suspended: bool = False


class ThumbnailEvent(Message):
    def __init__(self, side: str, action: str, *, revision=(), index=0, value=0):
        super().__init__()
        self.side, self.action = side, action
        self.revision, self.index, self.value = revision, index, value


def should_show(terminal: int, foreground: int, suspended: bool, minimized: bool) -> bool:
    return bool(terminal and terminal == foreground and not suspended and not minimized)


class ThumbnailManager:
    def __init__(self, app, terminal_hwnd: int):
        self.app, self.terminal_hwnd = app, terminal_hwnd
        self.lock = threading.Lock()
        self.states: dict[str, PaneState] = {}
        self.stop = threading.Event()
        self.thread = None
        self.error = ''
        self._hide_until = 0.0
        self.hidden = threading.Event()
        self.stopped = threading.Event()

    def start(self) -> bool:
        if os.name != 'nt' or not self.terminal_hwnd:
            self.error = 'Thumbnail view requires a Windows terminal window.'
            return False
        if self.thread and self.thread.is_alive():
            return True
        self.thread = threading.Thread(target=self._run, name='mdir-thumbnail-ui', daemon=True)
        self.thread.start()
        return True

    def publish(self, states: dict[str, PaneState]) -> None:
        with self.lock:
            self.states = dict(states)

    def suspend_external(self) -> None:
        with self.lock:
            self._hide_until = time.monotonic() + 0.6
            self.hidden.clear()
        # A bounded handshake hides the overlays before launching the external app.
        self.hidden.wait(0.25)

    def emit(self, event: ThumbnailEvent) -> None:
        self.app.post_message(event)  # Thread-safe and nonblocking; never call Textual widgets here.

    def shutdown(self, timeout: float = 2.0) -> bool:
        self.stop.set()
        if self.thread:
            self.thread.join(timeout)
        return not self.thread or not self.thread.is_alive()

    def _run(self) -> None:
        root = loader = None
        windows = {}
        memory = OrderedDict()
        hooks = []
        try:
            import tkinter as tk
            from PIL import ImageTk

            root = tk.Tk()
            root.withdraw()
            loader = ThumbnailLoader()
            user32 = ctypes.windll.user32
            user32.GetForegroundWindow.restype = wintypes.HWND
            foreground = int(user32.GetForegroundWindow() or 0)
            minimized = bool(user32.IsIconic(wintypes.HWND(self.terminal_hwnd)))
            event_proc = ctypes.WINFUNCTYPE(None, wintypes.HANDLE, wintypes.DWORD,
                                           wintypes.HWND, ctypes.c_long, ctypes.c_long,
                                           wintypes.DWORD, wintypes.DWORD)

            @event_proc
            def focus_changed(hook, event, hwnd, object_id, child_id, thread_id, timestamp):
                nonlocal foreground, minimized
                if event == 3:  # EVENT_SYSTEM_FOREGROUND
                    foreground = int(hwnd or 0)
                    minimized = bool(user32.IsIconic(wintypes.HWND(self.terminal_hwnd)))
                elif int(hwnd or 0) == self.terminal_hwnd:
                    minimized = event == 0x16  # MINIMIZESTART / MINIMIZEEND

            user32.SetWinEventHook.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE,
                                               event_proc, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD]
            user32.SetWinEventHook.restype = wintypes.HANDLE
            for first, last in ((3, 3), (0x16, 0x17)):
                hook = user32.SetWinEventHook(first, last, None, focus_changed, 0, 0, 0)
                if not hook:
                    raise OSError('Windows foreground event monitoring is unavailable')
                hooks.append(hook)

            def tick():
                if self.stop.is_set():
                    root.quit()
                    return
                with self.lock:
                    states = dict(self.states)
                    hide_until = self._hide_until
                visible = should_show(self.terminal_hwnd, foreground, time.monotonic() < hide_until, minimized)
                grid = windows_terminal_grid_rectangle(self.terminal_hwnd) if visible and states else None
                for side in tuple(windows):
                    if side not in states:
                        windows.pop(side).destroy()
                        loader.request(side, ())
                results = loader.take_results()
                for key, image in results.items():
                    memory[key] = image
                while len(memory) > 192:
                    _, old = memory.popitem(last=False)
                    if old is not None:
                        old.close()
                for side, state in states.items():
                    window = windows.get(side)
                    if window is None:
                        window = windows[side] = ThumbnailWindow(root, self, side, loader, memory, ImageTk)
                    window.update_state(state)
                    if visible and grid is not None and not state.suspended:
                        window.show_at(calculate_pane_rectangle(grid, state.layout))
                        if results:
                            window.dirty = True
                        window.draw()
                    else:
                        window.hide()
                        loader.request(side, ())
                if not any(window.visible for window in windows.values()):
                    self.hidden.set()
                root.after(100 if states else 250, guarded_tick)

            def guarded_tick():
                try:
                    tick()
                except Exception as exc:
                    self.error = f'{type(exc).__name__}: {exc}'
                    self.emit(ThumbnailEvent('', 'error'))
                    root.quit()

            root.after(0, guarded_tick)
            root.mainloop()
        except Exception as exc:
            self.error = f'{type(exc).__name__}: {exc}'
            self.emit(ThumbnailEvent('', 'error'))
        finally:
            for hook in hooks:
                ctypes.windll.user32.UnhookWinEvent(wintypes.HANDLE(hook))
            for window in windows.values():
                window.destroy()
            windows.clear()
            if loader:
                loader.shutdown()
            for image in memory.values():
                if image is not None:
                    image.close()
            memory.clear()
            if root:
                root.destroy()
            # Destroy callbacks and release Tcl wrappers on their owner thread.
            # Do not call global gc.collect here: Preview owns a different Tcl thread.
            root = None
            self.stopped.set()


class ThumbnailWindow:
    def __init__(self, root, manager, side, loader, memory, image_tk):
        import tkinter as tk
        from tkinter import font

        self.manager, self.side = manager, side
        self.loader, self.memory, self.image_tk = loader, memory, image_tk
        self.state = None
        self.visible, self.dirty = False, True
        self.rectangle = None
        self.columns, self.page_rows = 1, 1
        self.photos = {}
        self._right_drag_revision = None
        self._right_drag_seen = set()
        self._right_drag_last = None
        self._right_drag_pointer = None
        self._right_drag_timer = None
        self._wndproc = None
        self.window = tk.Toplevel(root)
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.label_font = font.Font(root=self.window, family='Segoe UI', size=9)
        self.toolbar = tk.Frame(self.window)
        self.toolbar.pack(fill='x')
        self.title = tk.Label(self.toolbar, anchor='w')
        self.title.pack(side='left', fill='x', expand=True)
        self.buttons = []
        for label, action, value in (('-', 'size', -1), ('+', 'size', 1), ('List', 'close', 0)):
            button = tk.Button(self.toolbar, text=label, takefocus=False, command=lambda a=action, v=value: self.send(a, value=v))
            button.pack(side='left')
            self.buttons.append(button)
        self.body = tk.Frame(self.window)
        self.body.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(self.body, highlightthickness=2, takefocus=False, yscrollincrement=24)
        self.scrollbar = tk.Scrollbar(self.body, orient='vertical', command=self.scroll)
        self.scrollbar.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind('<Configure>', self.resized)
        self.canvas.bind('<Button-1>', lambda e: self.click(e, 'mark' if e.state & 4 else 'select'))
        self.canvas.bind('<Button-3>', self.right_drag_start)
        self.canvas.bind('<B3-Motion>', self.right_drag_move)
        self.canvas.bind('<ButtonRelease-3>', self.right_drag_end)
        self.canvas.bind('<Double-Button-1>', lambda e: self.click(e, 'open'))
        self.canvas.bind('<MouseWheel>', self.wheel)
        self.window.update_idletasks()
        self.hwnd = self._apply_windows_styles()

    def _apply_windows_styles(self):
        if os.name != 'nt':
            return 0
        user32 = ctypes.windll.user32
        user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.GetAncestor.restype = wintypes.HWND
        hwnd = int(user32.GetAncestor(wintypes.HWND(self.window.winfo_id()), 2))
        get_long = user32.GetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8 else user32.GetWindowLongW
        set_long = user32.SetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8 else user32.SetWindowLongW
        for function in (get_long, set_long):
            function.restype = ctypes.c_ssize_t
        get_long.argtypes = [wintypes.HWND, ctypes.c_int]
        set_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
        style = get_long(hwnd, -20)
        set_long(hwnd, -20, style | 0x08000000 | 0x80)  # NOACTIVATE | TOOLWINDOW
        if self.manager.terminal_hwnd:
            set_long(hwnd, -8, self.manager.terminal_hwnd)  # Owner; never TOPMOST.
        callback = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        previous = get_long(hwnd, -4)
        user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.CallWindowProcW.restype = ctypes.c_ssize_t

        @callback
        def wndproc(handle, message, wparam, lparam):
            if message == 0x21:  # WM_MOUSEACTIVATE: accept mouse without stealing terminal keys.
                return 3
            return user32.CallWindowProcW(previous, handle, message, wparam, lparam)

        self._wndproc, self._previous_proc = wndproc, previous
        set_long(hwnd, -4, ctypes.cast(wndproc, ctypes.c_void_p).value)
        return hwnd

    def send(self, action, *, index=0, value=0):
        if self.state:
            self.manager.emit(ThumbnailEvent(self.side, action, revision=self.state.revision, index=index, value=value))

    def update_state(self, state):
        old = self.state
        changed = old is None or old.revision != state.revision or old.size != state.size
        current_changed = old is None or old.current != state.current
        repaint = changed or current_changed or old.marked != state.marked or old.active != state.active or old.palette != state.palette
        if changed or state.suspended:
            self.right_drag_end()
        self.state = state
        if repaint:
            self.dirty = True
        if changed:
            if old is None or old.directory != state.directory:
                self.canvas.yview_moveto(0)
            self.update_geometry()
        if (changed or current_changed) and self._right_drag_revision is None:
            self.ensure_current()
        if not repaint:
            return
        background, foreground, accent, marked = state.palette
        self.canvas.configure(background=background, highlightbackground=accent if state.active else '#555555')
        self.title.configure(text=f'{self.side.title()} · {state.size}px', background=background, foreground=foreground)
        self.toolbar.configure(background=background)
        for button in self.buttons:
            button.configure(background=background, foreground=foreground, activebackground=accent)

    def update_geometry(self):
        if not self.state:
            return
        columns = grid_columns(max(1, self.canvas.winfo_width()), self.state.size)
        self.page_rows = max(1, self.canvas.winfo_height() // (self.state.size + 54))
        if columns != self.columns:
            self.columns = columns
        self.send('geometry', value=(self.columns, self.page_rows))
        height = math.ceil(len(self.state.items) / self.columns) * (self.state.size + 54)
        self.canvas.configure(scrollregion=(0, 0, self.canvas.winfo_width(), max(height, self.canvas.winfo_height())))

    def resized(self, event):
        self.right_drag_end()
        self.update_geometry()
        self.ensure_current()
        self.dirty = True

    def ensure_current(self):
        if not self.state:
            return
        top = self.state.current // self.columns * (self.state.size + 54)
        view_top = self.canvas.canvasy(0)
        view_height = self.canvas.winfo_height()
        content = max(view_height, math.ceil(len(self.state.items) / self.columns) * (self.state.size + 54))
        if top < view_top:
            self.canvas.yview_moveto(top / max(1, content))
        elif top + self.state.size + 54 > view_top + view_height:
            self.canvas.yview_moveto(max(0, top + self.state.size + 54 - view_height) / max(1, content))

    def show_at(self, rectangle):
        moved = rectangle != self.rectangle
        was_visible = self.visible
        if moved:
            self.rectangle = rectangle
            self.window.geometry(f'{rectangle.width}x{rectangle.height}')
            self.window.update_idletasks()
            self._position_window(rectangle)
            self.dirty = True
        if not self.visible:
            self.window.deiconify()
            ctypes.windll.user32.ShowWindow(wintypes.HWND(self.hwnd), 4)  # SW_SHOWNOACTIVATE
            self.visible = True
            self.dirty = True
        if moved or not was_visible:
            self._position_window(rectangle)

    def _position_window(self, rectangle):
        # Tk's negative geometry offsets are relative to the right/bottom edge.
        # Win32 takes absolute signed coordinates, including monitors to the left.
        position = ctypes.windll.user32.SetWindowPos
        position.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                             ctypes.c_int, ctypes.c_int, wintypes.UINT]
        position(wintypes.HWND(self.hwnd), None, rectangle.left, rectangle.top,
                 rectangle.width, rectangle.height, 0x14)  # NOZORDER | NOACTIVATE

    def hide(self):
        self.right_drag_end()
        if self.visible:
            self.window.withdraw()
            self.visible = False

    def scroll(self, *args):
        self.canvas.yview(*args)
        self.dirty = True

    def wheel(self, event):
        units = -int(event.delta / 120) if abs(event.delta) >= 120 else (-1 if event.delta > 0 else 1)
        self.scroll('scroll', units * 3, 'units')
        if self._right_drag_pointer is not None:
            self._right_drag_visit(*self._right_drag_pointer)
        return 'break'

    def _index_at(self, x, y, *, clamp=False):
        if not self.state or not self.state.items or not 0 <= x < self.canvas.winfo_width():
            return None
        if clamp:
            y = max(0, min(self.canvas.winfo_height() - 1, y))
        elif not 0 <= y < self.canvas.winfo_height():
            return None
        column = int(x) // (self.state.size + 20)
        if column >= self.columns:
            return None
        row = max(0, int(self.canvas.canvasy(y))) // (self.state.size + 54)
        index = row * self.columns + column
        if clamp:
            index = min(index, len(self.state.items) - 1)
        if 0 <= index < len(self.state.items):
            return index
        return None

    def click(self, event, action):
        index = self._index_at(event.x, event.y)
        if index is not None:
            self.send(action, index=index)
        return 'break'

    def right_drag_start(self, event):
        self.right_drag_end()
        index = self._index_at(event.x, event.y)
        if index is not None and not self.state.suspended:
            self._right_drag_revision = self.state.revision
            self._right_drag_pointer = (event.x, event.y)
            self._right_drag_visit(event.x, event.y)
            self._right_drag_timer = self.canvas.after(60, self._right_drag_tick)
        # Tk implicitly captures the mouse until release, including outside the canvas.
        return 'break'

    def right_drag_move(self, event):
        if self._right_drag_revision is not None:
            self._right_drag_pointer = (event.x, event.y)
            self._right_drag_visit(event.x, event.y)
        return 'break'

    def _right_drag_visit(self, x, y):
        if not self.state or self.state.suspended or self._right_drag_revision != self.state.revision:
            self.right_drag_end()
            return
        index = self._index_at(x, y, clamp=True)
        if index is None or index == self._right_drag_last:
            return
        previous = self._right_drag_last
        step = 1 if previous is None or index >= previous else -1
        candidates = (index,) if previous is None else range(previous + step, index + step, step)
        fresh = tuple(i for i in candidates if i not in self._right_drag_seen)
        self._right_drag_seen.update(fresh)
        self._right_drag_last = index
        # Toggle once per gesture, independent of delayed Textual selection snapshots.
        self.send('mark_drag', index=index, value=fresh)

    @staticmethod
    def _right_button_down():
        return os.name != 'nt' or bool(ctypes.windll.user32.GetAsyncKeyState(0x02) & 0x8000)

    def _right_drag_tick(self):
        self._right_drag_timer = None
        if self._right_drag_pointer is None:
            return
        # Release may happen over another app or while a dialog hides this window.
        if not self._right_button_down():
            self.right_drag_end()
            return
        x, y = self._right_drag_pointer
        height = self.canvas.winfo_height()
        direction = -1 if y < 20 else 1 if y >= height - 20 else 0
        if direction and 0 <= x < self.canvas.winfo_width():
            self.scroll('scroll', direction * 3, 'units')
            self._right_drag_visit(x, y)
        if self._right_drag_pointer is not None:
            self._right_drag_timer = self.canvas.after(60, self._right_drag_tick)

    def right_drag_end(self, event=None):
        if self._right_drag_timer is not None:
            self.canvas.after_cancel(self._right_drag_timer)
            self._right_drag_timer = None
        self._right_drag_revision = None
        self._right_drag_seen.clear()
        self._right_drag_last = None
        self._right_drag_pointer = None
        return 'break'

    def draw(self):
        if not self.dirty or not self.state:
            return
        self.dirty = False
        state = self.state
        background, foreground, accent, marked = state.palette
        self.canvas.delete('all')
        self.photos.clear()
        pending = []
        indices = visible_indices(len(state.items), self.columns, int(self.canvas.canvasy(0)), self.canvas.winfo_height(), state.size)
        for index in indices:
            item = state.items[index]
            x = (index % self.columns) * (state.size + 20) + 8
            y = (index // self.columns) * (state.size + 54) + 6
            is_marked = item.path in state.marked
            self.canvas.create_rectangle(x, y, x + state.size + 4, y + state.size + 44,
                                         fill=(CURSOR_BACKGROUND if index == state.current else MARK_BACKGROUND) if is_marked else background,
                                         outline=accent if index == state.current else '#555555', width=3 if index == state.current else 1)
            key = item.request_key(state.size)
            image = self.memory.get(key)
            if image is not None:
                self.memory.move_to_end(key)
                photo = self.image_tk.PhotoImage(image, master=self.window)
                self.photos[index] = photo
                self.canvas.create_image(x + state.size // 2 + 2, y + state.size // 2 + 5, image=photo)
            else:
                label = 'DIR' if item.directory else (item.path.suffix[1:].upper()[:8] or 'FILE')
                self.canvas.create_text(x + state.size // 2 + 2, y + state.size // 2, text=label, fill=MARK_FOREGROUND if is_marked else (marked if item.directory else foreground), font=('Segoe UI', 15, 'bold'))
                if not item.directory and item.path.suffix.lower() in IMAGE_EXTENSIONS and key not in self.memory:
                    pending.append(key)
            if is_marked:
                # The badge remains visible even when an image fills the tile.
                self.canvas.create_rectangle(x + 4, y + 4, x + state.size, y + state.size + 40, outline=MARK_BORDER, width=2)
                self.canvas.create_rectangle(x + 6, y + 6, x + 29, y + 29, fill=MARK_BACKGROUND, outline=MARK_BORDER)
                self.canvas.create_text(x + 18, y + 17, text='✓', fill=MARK_FOREGROUND, font=('Segoe UI', 13, 'bold'))
            label = (MARK_PREFIX if is_marked else '') + item.name
            lines = []
            for line_number in range(2):
                end = 0
                while end < len(label) and self.label_font.measure(label[:end + 1]) <= state.size - 12:
                    end += 1
                end = max(1, end)
                line, label = label[:end], label[end:]
                if line_number == 1 and label:
                    line = line[:-2] + '…'
                lines.append(line)
                if not label:
                    break
            self.canvas.create_text(x + state.size // 2 + 2, y + state.size + 8, text='\n'.join(lines), anchor='n', fill=MARK_FOREGROUND if is_marked else foreground, font=self.label_font)
        if not state.items:
            self.canvas.create_text(12, 16, text='Loading…' if not state.revision[-1] else 'Empty folder', anchor='nw', fill=foreground)
        self.loader.request(self.side, pending)

    def destroy(self):
        self.right_drag_end()
        self.photos.clear()
        self.label_font = None
        if self._wndproc is not None:
            user32 = ctypes.windll.user32
            setter = user32.SetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8 else user32.SetWindowLongW
            setter(wintypes.HWND(self.hwnd), -4, self._previous_proc)
        self.window.destroy()
        self._wndproc = None
