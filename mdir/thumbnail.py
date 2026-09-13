from __future__ import annotations

import hashlib
import os
import queue
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

from .preview.native import PaneLayout, WindowRectangle, calculate_pane_rectangle, windows_terminal_grid_rectangle
from . import core as legacy


THUMBNAIL_MIN_SIZE = 96
THUMBNAIL_MAX_SIZE = 240
THUMBNAIL_STEP = 24
DEFAULT_THUMBNAIL_SIZE = 144
CACHE_LIMIT_BYTES = 1024 * 1024 * 1024
CACHE_CLEANUP_BATCH = 500


@dataclass(frozen=True)
class ThumbnailItem:
    path: Path
    is_directory: bool
    size: int
    modified: float

    @property
    def is_image(self) -> bool:
        return (not self.is_directory) and self.path.suffix.lower() in legacy.IMAGE_EXTENSIONS


class NativeThumbnailController:
    """Native Windows thumbnail grid layered over one Textual file table.

    The window never takes keyboard focus, so F5/F6 and the rest of mDIR's
    keyboard workflow keep working in Windows Terminal while the user selects
    images with the mouse.
    """

    def __init__(
        self,
        app,
        *,
        select_callback: Callable[[str, Path], None],
        toggle_callback: Callable[[str, Path], None],
        open_callback: Callable[[str, Path], None],
        close_callback: Callable[[], None],
    ) -> None:
        self.app = app
        self.select_callback = select_callback
        self.toggle_callback = toggle_callback
        self.open_callback = open_callback
        self.close_callback = close_callback
        self._commands: queue.Queue[tuple[str, object]] = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()
        self._shutdown_complete = threading.Event()
        self._started_ok = False
        self._terminal_hwnd = 0
        self._window_hwnd = 0
        self.available = os.name == "nt"
        self.last_error = ""

    @staticmethod
    def _foreground_window() -> int:
        if os.name != "nt":
            return 0
        try:
            import ctypes
            from ctypes import wintypes

            get_foreground = ctypes.windll.user32.GetForegroundWindow
            get_foreground.restype = wintypes.HWND
            return int(get_foreground() or 0)
        except Exception:
            return 0

    def start(self) -> bool:
        if not self.available:
            return False
        if self._thread is not None and self._thread.is_alive():
            return True
        self._terminal_hwnd = self._foreground_window()
        self._ready.clear()
        self._shutdown_complete.clear()
        self._started_ok = False
        self._thread = threading.Thread(
            target=self._thread_main,
            name="mDIR-Native-Thumbnails",
            daemon=False,
        )
        self._thread.start()
        self._ready.wait(timeout=1.0)
        if self._ready.is_set() and not self._started_ok:
            self.available = False
            return False
        return bool(self._thread and self._thread.is_alive())

    def show(
        self,
        *,
        side: str,
        directory: Path,
        items: Iterable[ThumbnailItem],
        marked: Iterable[Path],
        current: Optional[Path],
        pane_layout: PaneLayout,
        thumbnail_size: int = DEFAULT_THUMBNAIL_SIZE,
    ) -> bool:
        if not self.start():
            return False
        foreground = self._foreground_window()
        if foreground and foreground != self._window_hwnd:
            self._terminal_hwnd = foreground
        payload = {
            "side": side,
            "directory": str(directory),
            "items": [
                (str(item.path), item.is_directory, int(item.size), float(item.modified))
                for item in items
            ],
            "marked": [str(path) for path in marked],
            "current": str(current) if current else "",
            "pane_layout": pane_layout,
            "terminal_hwnd": self._terminal_hwnd,
            "thumbnail_size": int(thumbnail_size),
        }
        self._commands.put(("show", payload))
        return True

    def update_layout(self, pane_layout: PaneLayout) -> None:
        if self._thread is not None:
            self._commands.put(("layout", pane_layout))

    def update_selection(
        self,
        *,
        marked: Iterable[Path],
        current: Optional[Path],
    ) -> None:
        if self._thread is not None:
            self._commands.put(
                (
                    "selection",
                    {
                        "marked": [str(path) for path in marked],
                        "current": str(current) if current else "",
                    },
                )
            )

    def update_theme(self) -> None:
        if self._thread is not None:
            self._commands.put(("theme", self._theme_palette()))

    def hide(self) -> None:
        if self._thread is not None:
            self._commands.put(("hide", None))

    def shutdown(self, timeout: float = 4.0) -> bool:
        thread = self._thread
        if thread is None:
            return True
        self._commands.put(("shutdown", None))
        self._shutdown_complete.wait(timeout=max(0.2, timeout))
        thread.join(timeout=0.5)
        stopped = not thread.is_alive()
        if stopped:
            self._thread = None
        return stopped

    @staticmethod
    def _tk_color(value: object, fallback: str) -> str:
        """Convert Textual colors to a Tk-compatible #RRGGBB value.

        Textual may emit #RRGGBBAA (for example #D8D8D899). Tk on Windows
        rejects 8-digit hex colors, so discard the alpha channel here.
        """
        text = str(value or "").strip()
        if text.startswith("#"):
            if len(text) >= 7:
                candidate = text[:7]
                try:
                    int(candidate[1:], 16)
                    return candidate
                except ValueError:
                    pass
            if len(text) == 4:
                try:
                    int(text[1:], 16)
                    return "#" + "".join(ch * 2 for ch in text[1:])
                except ValueError:
                    pass
        return fallback

    def _theme_palette(self) -> dict[str, str]:
        defaults = {
            "background": "#1e1e1e",
            "surface": "#292929",
            "foreground": "#f0f0f0",
            "primary": "#00aaff",
            "accent": "#00d7af",
            "warning": "#ffd75f",
            "muted": "#9a9a9a",
        }
        try:
            colors = self.app.current_theme.to_color_system().generate()
            return {
                "background": self._tk_color(
                    colors.get("background"), defaults["background"]
                ),
                "surface": self._tk_color(
                    colors.get("surface"), defaults["surface"]
                ),
                "foreground": self._tk_color(
                    colors.get("foreground"), defaults["foreground"]
                ),
                "primary": self._tk_color(
                    colors.get("primary"), defaults["primary"]
                ),
                "accent": self._tk_color(
                    colors.get("accent"), defaults["accent"]
                ),
                "warning": self._tk_color(
                    colors.get("warning"), defaults["warning"]
                ),
                "muted": self._tk_color(
                    colors.get("foreground-muted"), defaults["muted"]
                ),
            }
        except Exception:
            return defaults

    def _thread_main(self) -> None:
        window: Optional[_ThumbnailWindow] = None
        try:
            window = _ThumbnailWindow(
                self._commands,
                terminal_hwnd=self._terminal_hwnd,
                palette=self._theme_palette(),
                select_callback=lambda side, path: self._call_path(
                    self.select_callback, side, path
                ),
                toggle_callback=lambda side, path: self._call_path(
                    self.toggle_callback, side, path
                ),
                open_callback=lambda side, path: self._call_path(
                    self.open_callback, side, path
                ),
                close_callback=lambda: self._call(self.close_callback),
            )
            self._window_hwnd = window.window_hwnd()
            self._started_ok = True
            self._ready.set()
            window.run()
        except Exception as exc:
            self.last_error = str(exc)
            self.available = False
            self._ready.set()
        finally:
            self._window_hwnd = 0
            self._shutdown_complete.set()

    def _call(self, callback: Callable[[], None]) -> None:
        try:
            self.app.call_from_thread(callback)
        except Exception:
            pass

    def _call_path(
        self,
        callback: Callable[[str, Path], None],
        side: str,
        path: Path,
    ) -> None:
        try:
            self.app.call_from_thread(callback, side, path)
        except Exception:
            pass


class _ThumbnailWindow:
    POLL_MS = 35

    def __init__(
        self,
        commands: queue.Queue[tuple[str, object]],
        *,
        terminal_hwnd: int,
        palette: dict[str, str],
        select_callback: Callable[[str, Path], None],
        toggle_callback: Callable[[str, Path], None],
        open_callback: Callable[[str, Path], None],
        close_callback: Callable[[], None],
    ) -> None:
        import tkinter as tk

        self.tk = tk
        self.commands = commands
        self.terminal_hwnd = int(terminal_hwnd)
        self.palette = palette
        self.select_callback = select_callback
        self.toggle_callback = toggle_callback
        self.open_callback = open_callback
        self.close_callback = close_callback

        self.root = tk.Tk()
        self.root.withdraw()
        self.root.overrideredirect(True)
        self.root.configure(bg=self.palette["background"])

        self.side = "left"
        self.directory = Path(".")
        self.items: list[ThumbnailItem] = []
        self.marked: set[Path] = set()
        self.current: Optional[Path] = None
        self.pane_layout: Optional[PaneLayout] = None
        self.thumbnail_size = DEFAULT_THUMBNAIL_SIZE
        self.visible = False
        self._generation = 0
        self._photo_by_index: dict[int, object] = {}
        self._pending_indices: set[int] = set()
        self._load_requests: queue.Queue[Optional[tuple[int, int, Path, int]]] = queue.Queue()
        self._load_results: queue.Queue[tuple[int, int, Path, object | None]] = queue.Queue()
        self._loader_stop = threading.Event()
        self._loader = threading.Thread(
            target=self._loader_main,
            name="mDIR-Thumbnail-Loader",
            daemon=True,
        )
        self._loader.start()
        self._last_geometry: Optional[WindowRectangle] = None

        self._build_ui()
        self._apply_windows_styles()
        self.root.after(self.POLL_MS, self._poll_commands)
        self.root.after(self.POLL_MS, self._poll_results)
        self.root.after(180, self._follow_terminal)
        threading.Thread(
            target=self._trim_cache,
            name="mDIR-Thumbnail-Cache-Cleanup",
            daemon=True,
        ).start()

    @staticmethod
    def cache_root() -> Path:
        base = Path(os.environ.get("LOCALAPPDATA", Path.home()))
        root = base / "mDIR" / "thumbnail-cache"
        root.mkdir(parents=True, exist_ok=True)
        return root

    @classmethod
    def _cache_path(cls, path: Path, thumbnail_size: int) -> Path:
        try:
            stat = path.stat()
            signature = (
                f"{path.resolve(strict=False)}|{stat.st_mtime_ns}|"
                f"{stat.st_size}|{thumbnail_size}"
            )
        except OSError:
            signature = f"{path}|0|0|{thumbnail_size}"
        digest = hashlib.sha1(signature.encode("utf-8", "surrogatepass")).hexdigest()
        return cls.cache_root() / f"{digest}.jpg"

    @classmethod
    def _load_thumbnail(cls, path: Path, thumbnail_size: int):
        from PIL import Image, ImageOps

        cache_path = cls._cache_path(path, thumbnail_size)
        if cache_path.is_file():
            try:
                with Image.open(cache_path) as cached:
                    return cached.convert("RGB").copy()
            except Exception:
                try:
                    cache_path.unlink()
                except OSError:
                    pass

        try:
            with Image.open(path) as source:
                image = ImageOps.exif_transpose(source).convert("RGB")
                image.thumbnail(
                    (thumbnail_size, thumbnail_size),
                    Image.Resampling.LANCZOS,
                )
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    image.save(cache_path, "JPEG", quality=82, optimize=True)
                except OSError:
                    pass
                return image.copy()
        except Exception:
            return None

    @classmethod
    def _trim_cache(cls) -> None:
        try:
            root = cls.cache_root()
            files = [p for p in root.iterdir() if p.is_file()]
            total = 0
            stats: list[tuple[float, int, Path]] = []
            for path in files:
                try:
                    stat = path.stat()
                except OSError:
                    continue
                total += stat.st_size
                stats.append((stat.st_mtime, stat.st_size, path))
            if total <= CACHE_LIMIT_BYTES:
                return
            stats.sort()
            for _, size, path in stats[:CACHE_CLEANUP_BATCH]:
                try:
                    path.unlink()
                    total -= size
                except OSError:
                    pass
                if total <= int(CACHE_LIMIT_BYTES * 0.85):
                    break
        except Exception:
            pass

    def _loader_main(self) -> None:
        while not self._loader_stop.is_set():
            request = self._load_requests.get()
            if request is None:
                return
            generation, index, path, thumbnail_size = request
            image = self._load_thumbnail(path, thumbnail_size)
            self._load_results.put((generation, index, path, image))

    def _build_ui(self) -> None:
        tk = self.tk
        self.toolbar = tk.Frame(
            self.root,
            bg=self.palette["surface"],
            height=34,
        )
        self.toolbar.pack(side="top", fill="x")
        self.toolbar.pack_propagate(False)

        self.title = tk.Label(
            self.toolbar,
            text=" THUMBNAILS ",
            bg=self.palette["surface"],
            fg=self.palette["foreground"],
            font=("Cascadia Mono", 10, "bold"),
            anchor="w",
        )
        self.title.pack(side="left", fill="y", padx=(4, 6))

        self.hint = tk.Label(
            self.toolbar,
            text="Right-click: mark  |  Ctrl+click: mark",
            bg=self.palette["surface"],
            fg=self.palette["muted"],
            font=("Cascadia Mono", 9),
            anchor="w",
        )
        self.hint.pack(side="left", fill="both", expand=True)

        for label, command in (
            ("-", lambda: self._resize_thumbnails(-THUMBNAIL_STEP)),
            ("+", lambda: self._resize_thumbnails(THUMBNAIL_STEP)),
            ("List", self._request_close),
        ):
            button = tk.Button(
                self.toolbar,
                text=label,
                command=command,
                bg=self.palette["surface"],
                fg=self.palette["foreground"],
                activebackground=self.palette["primary"],
                activeforeground="white",
                relief="flat",
                borderwidth=0,
                padx=9,
                font=("Cascadia Mono", 9, "bold"),
            )
            button.pack(side="right", fill="y", padx=(1, 0))

        self.canvas = tk.Canvas(
            self.root,
            bg=self.palette["background"],
            highlightthickness=0,
        )
        self.scrollbar = tk.Scrollbar(
            self.root,
            orient="vertical",
            command=self._yview,
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.canvas.bind("<Configure>", lambda _event: self._render())
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<Button-1>", self._on_left_click)
        self.canvas.bind("<Control-Button-1>", self._on_ctrl_click)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<Double-Button-1>", self._on_double_click)

    def window_hwnd(self) -> int:
        if os.name != "nt":
            return 0
        try:
            import ctypes
            from ctypes import wintypes

            hwnd = int(self.root.winfo_id())
            get_ancestor = ctypes.windll.user32.GetAncestor
            get_ancestor.argtypes = [wintypes.HWND, wintypes.UINT]
            get_ancestor.restype = wintypes.HWND
            return int(get_ancestor(hwnd, 2) or hwnd)
        except Exception:
            return 0

    def _apply_windows_styles(self) -> None:
        if os.name != "nt":
            return
        try:
            import ctypes
            from ctypes import wintypes

            hwnd = self.window_hwnd()
            user32 = ctypes.windll.user32
            GWL_EXSTYLE = -20
            GWLP_HWNDPARENT = -8
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_NOACTIVATE = 0x08000000
            style = int(user32.GetWindowLongW(hwnd, GWL_EXSTYLE))
            user32.SetWindowLongW(
                hwnd,
                GWL_EXSTYLE,
                style | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
            )
            if self.terminal_hwnd:
                if ctypes.sizeof(ctypes.c_void_p) == 8:
                    setter = user32.SetWindowLongPtrW
                    setter.argtypes = [
                        wintypes.HWND,
                        ctypes.c_int,
                        ctypes.c_void_p,
                    ]
                    setter(
                        wintypes.HWND(hwnd),
                        GWLP_HWNDPARENT,
                        ctypes.c_void_p(self.terminal_hwnd),
                    )
                else:
                    user32.SetWindowLongW(
                        hwnd,
                        GWLP_HWNDPARENT,
                        self.terminal_hwnd,
                    )
        except Exception:
            pass

    def _restore_terminal_focus(self) -> None:
        """Return keyboard input to Windows Terminal after a thumbnail click."""
        if os.name != "nt" or not self.terminal_hwnd:
            return
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            user32.SetForegroundWindow.argtypes = [wintypes.HWND]
            user32.SetForegroundWindow.restype = wintypes.BOOL
            user32.BringWindowToTop.argtypes = [wintypes.HWND]
            user32.BringWindowToTop.restype = wintypes.BOOL
            user32.BringWindowToTop(wintypes.HWND(self.terminal_hwnd))
            user32.SetForegroundWindow(wintypes.HWND(self.terminal_hwnd))
        except Exception:
            pass

    def _restore_terminal_focus_soon(self) -> None:
        try:
            self.root.after(1, self._restore_terminal_focus)
            self.root.after(35, self._restore_terminal_focus)
        except Exception:
            self._restore_terminal_focus()

    def _request_close(self) -> None:
        self.close_callback()
        self._restore_terminal_focus_soon()

    def _resize_thumbnails(self, delta: int) -> None:
        self.thumbnail_size = max(
            THUMBNAIL_MIN_SIZE,
            min(THUMBNAIL_MAX_SIZE, self.thumbnail_size + delta),
        )
        self._generation += 1
        self._photo_by_index.clear()
        self._pending_indices.clear()
        self._render()
        self._restore_terminal_focus_soon()

    def _columns(self) -> int:
        width = max(1, int(self.canvas.winfo_width()))
        return max(1, width // self._cell_width())

    def _cell_width(self) -> int:
        return self.thumbnail_size + 26

    def _cell_height(self) -> int:
        return self.thumbnail_size + 50

    def _scroll_height(self) -> int:
        columns = self._columns()
        rows = (len(self.items) + columns - 1) // columns
        return max(1, rows * self._cell_height())

    def _yview(self, *args) -> None:
        self.canvas.yview(*args)
        self._render()

    def _on_wheel(self, event) -> None:
        delta = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(delta * 3, "units")
        self._render()
        self._restore_terminal_focus_soon()

    def _event_index(self, event) -> Optional[int]:
        columns = self._columns()
        x = int(self.canvas.canvasx(event.x))
        y = int(self.canvas.canvasy(event.y))
        if x < 0 or y < 0:
            return None
        col = x // self._cell_width()
        row = y // self._cell_height()
        index = row * columns + col
        if 0 <= index < len(self.items):
            return index
        return None

    def _select_index(self, index: int, *, toggle: bool = False) -> None:
        item = self.items[index]
        self.current = item.path
        self.select_callback(self.side, item.path)
        if toggle:
            if item.path in self.marked:
                self.marked.remove(item.path)
            else:
                self.marked.add(item.path)
            self.toggle_callback(self.side, item.path)
        self._render()

    def _on_left_click(self, event) -> None:
        index = self._event_index(event)
        if index is not None:
            self._select_index(index)
        self._restore_terminal_focus_soon()

    def _on_ctrl_click(self, event) -> None:
        index = self._event_index(event)
        if index is not None:
            self._select_index(index, toggle=True)
        self._restore_terminal_focus_soon()

    def _on_right_click(self, event) -> None:
        index = self._event_index(event)
        if index is not None:
            self._select_index(index, toggle=True)
        self._restore_terminal_focus_soon()

    def _on_double_click(self, event) -> None:
        index = self._event_index(event)
        if index is not None:
            item = self.items[index]
            self.current = item.path
            self.select_callback(self.side, item.path)
            self.open_callback(self.side, item.path)
        self._restore_terminal_focus_soon()

    def _visible_indices(self) -> range:
        columns = self._columns()
        cell_h = self._cell_height()
        top = int(self.canvas.canvasy(0))
        bottom = int(self.canvas.canvasy(max(1, self.canvas.winfo_height())))
        first_row = max(0, top // cell_h - 2)
        last_row = max(first_row, bottom // cell_h + 2)
        start = first_row * columns
        end = min(len(self.items), (last_row + 1) * columns)
        return range(start, end)

    def _request_visible_thumbnails(self) -> None:
        for index in self._visible_indices():
            if index in self._photo_by_index or index in self._pending_indices:
                continue
            item = self.items[index]
            if not item.is_image:
                continue
            self._pending_indices.add(index)
            self._load_requests.put(
                (self._generation, index, item.path, self.thumbnail_size)
            )

    def _render(self) -> None:
        if not self.visible:
            return
        self.canvas.configure(scrollregion=(0, 0, 1, self._scroll_height()))
        self.canvas.delete("item")
        columns = self._columns()
        cell_w = self._cell_width()
        cell_h = self._cell_height()

        for index in self._visible_indices():
            item = self.items[index]
            row, col = divmod(index, columns)
            x0 = col * cell_w + 7
            y0 = row * cell_h + 7
            x1 = x0 + self.thumbnail_size + 12
            y1 = y0 + self.thumbnail_size + 36

            marked = item.path in self.marked
            current = item.path == self.current
            outline = (
                self.palette["warning"]
                if marked
                else self.palette["primary"]
                if current
                else self.palette["surface"]
            )
            width = 3 if (marked or current) else 1
            self.canvas.create_rectangle(
                x0,
                y0,
                x1,
                y1,
                fill=self.palette["surface"],
                outline=outline,
                width=width,
                tags="item",
            )

            photo = self._photo_by_index.get(index)
            image_y = y0 + self.thumbnail_size // 2 + 8
            image_x = x0 + self.thumbnail_size // 2 + 6
            if photo is not None:
                self.canvas.create_image(
                    image_x,
                    image_y,
                    image=photo,
                    anchor="center",
                    tags="item",
                )
            else:
                placeholder = "DIR" if item.is_directory else item.path.suffix.upper().lstrip(".") or "FILE"
                self.canvas.create_text(
                    image_x,
                    image_y,
                    text=placeholder,
                    fill=(
                        self.palette["accent"]
                        if item.is_directory
                        else self.palette["muted"]
                    ),
                    font=("Cascadia Mono", 11, "bold"),
                    tags="item",
                )

            name = item.path.name
            max_chars = max(10, self.thumbnail_size // 8)
            if len(name) > max_chars:
                name = name[: max_chars - 1] + "…"
            label = ("* " if marked else "") + name
            self.canvas.create_text(
                x0 + 6,
                y0 + self.thumbnail_size + 24,
                text=label,
                fill=(
                    self.palette["warning"]
                    if marked
                    else self.palette["foreground"]
                ),
                font=("Cascadia Mono", 9, "bold" if marked else "normal"),
                width=self.thumbnail_size,
                anchor="w",
                tags="item",
            )
        self._request_visible_thumbnails()

    def _poll_results(self) -> None:
        changed = False
        try:
            from PIL import ImageTk

            while True:
                generation, index, _path, image = self._load_results.get_nowait()
                self._pending_indices.discard(index)
                if generation != self._generation or image is None:
                    continue
                self._photo_by_index[index] = ImageTk.PhotoImage(image)
                changed = True
        except queue.Empty:
            pass
        except Exception:
            pass
        if changed:
            self._render()
        self.root.after(self.POLL_MS, self._poll_results)

    def _apply_show(self, payload: dict[str, object]) -> None:
        self.side = str(payload.get("side", "left"))
        self.directory = Path(str(payload.get("directory", ".")))
        self.items = [
            ThumbnailItem(Path(path), bool(is_directory), int(size), float(modified))
            for path, is_directory, size, modified in payload.get("items", [])
        ]
        self.marked = {Path(path) for path in payload.get("marked", [])}
        current = str(payload.get("current", ""))
        self.current = Path(current) if current else None
        self.pane_layout = payload.get("pane_layout")  # type: ignore[assignment]
        self.terminal_hwnd = int(payload.get("terminal_hwnd", self.terminal_hwnd))
        self.thumbnail_size = max(
            THUMBNAIL_MIN_SIZE,
            min(
                THUMBNAIL_MAX_SIZE,
                int(payload.get("thumbnail_size", self.thumbnail_size)),
            ),
        )
        self._generation += 1
        self._photo_by_index.clear()
        self._pending_indices.clear()
        self.title.configure(
            text=f" THUMBNAILS  {self.directory} "
        )
        self.visible = True
        self._apply_geometry()
        self.root.deiconify()
        self.root.lift()
        self._render()

    def _apply_selection(self, payload: dict[str, object]) -> None:
        self.marked = {Path(path) for path in payload.get("marked", [])}
        current = str(payload.get("current", ""))
        self.current = Path(current) if current else None
        self._render()

    def _apply_palette(self, palette: dict[str, str]) -> None:
        self.palette = palette
        self.root.configure(bg=palette["background"])
        self.toolbar.configure(bg=palette["surface"])
        self.title.configure(bg=palette["surface"], fg=palette["foreground"])
        self.hint.configure(bg=palette["surface"], fg=palette["muted"])
        self.canvas.configure(bg=palette["background"])
        self._render()

    def _poll_commands(self) -> None:
        try:
            while True:
                command, payload = self.commands.get_nowait()
                if command == "show":
                    self._apply_show(payload)  # type: ignore[arg-type]
                elif command == "selection":
                    self._apply_selection(payload)  # type: ignore[arg-type]
                elif command == "layout":
                    self.pane_layout = payload  # type: ignore[assignment]
                    self._apply_geometry()
                elif command == "theme":
                    self._apply_palette(payload)  # type: ignore[arg-type]
                elif command == "hide":
                    self.visible = False
                    self.root.withdraw()
                elif command == "shutdown":
                    self._loader_stop.set()
                    self._load_requests.put(None)
                    self.root.destroy()
                    return
        except queue.Empty:
            pass
        self.root.after(self.POLL_MS, self._poll_commands)

    def _apply_geometry(self) -> None:
        if not self.visible or self.pane_layout is None or not self.terminal_hwnd:
            return
        terminal = windows_terminal_grid_rectangle(self.terminal_hwnd)
        if terminal is None:
            return
        rectangle = calculate_pane_rectangle(terminal, self.pane_layout)
        self._last_geometry = rectangle
        self.root.geometry(
            f"{rectangle.width}x{rectangle.height}+{rectangle.left}+{rectangle.top}"
        )

    def _follow_terminal(self) -> None:
        if self.visible:
            self._apply_geometry()
        self.root.after(180, self._follow_terminal)

    def run(self) -> None:
        self.root.mainloop()
