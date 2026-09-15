from __future__ import annotations

import ctypes
import inspect
import os
import subprocess
import sys
import webbrowser
from ctypes import wintypes
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, HorizontalScroll, Vertical
from textual.timer import Timer
from textual.widgets import Button, DataTable, Footer, Header, Static

from .fast_app import FastFileManagerApp, LargeDirectoryFilePane
from .preview.document import (
    DocumentPreviewPanel,
    PREVIEW_EXTENSIONS,
    can_preview,
)
from .text_actions import (
    DEFAULT_EDIT_LIMIT,
    DEFAULT_VIEW_LIMIT,
    SafeTextDecision,
    format_file_size,
    inspect_safe_text_file,
)
from .shortcuts import (
    MAX_SHORTCUTS,
    ShortcutDefinition,
    expand_shortcut_text,
    load_shortcuts,
    save_shortcuts,
    shortcut_config_path,
)
from .platform_support import open_with_default_app
from .keymap import load_keymap, save_keymap
from .theme import (
    THEME_NAME,
    MDIR_THEME_CSS,
    MDIR_THEME,
    install_file_colors,
)
from . import __version__
from .thumbnail_app import ThumbnailAppMixin, THUMBNAIL_BINDINGS
from .keyboard import NativeShortcuts, NativeShortcut, shortcut_routes


VERSION = __version__
HOTKEY_POLL_SECONDS = 0.25
VK_SHIFT = 0x10
VK_LBUTTON = 0x01

install_file_colors()

if TYPE_CHECKING:
    from .preview.native import (
        NativePreviewController,
        PaneLayout,
        WindowRectangle,
    )


def terminal_screen_point_to_cell(
    screen_x: int,
    screen_y: int,
    terminal_grid: "WindowRectangle",
    columns: int,
    rows: int,
) -> Optional[tuple[int, int]]:
    """Convert a physical Windows pointer position to a Textual cell."""
    if not (
        terminal_grid.left <= screen_x < terminal_grid.right
        and terminal_grid.top <= screen_y < terminal_grid.bottom
    ):
        return None
    columns = max(1, int(columns))
    rows = max(1, int(rows))
    cell_x = min(
        columns - 1,
        int(
            (screen_x - terminal_grid.left)
            * columns
            / terminal_grid.width
        ),
    )
    cell_y = min(
        rows - 1,
        int(
            (screen_y - terminal_grid.top)
            * rows
            / terminal_grid.height
        ),
    )
    return cell_x, cell_y


class MDirApp(ThumbnailAppMixin, FastFileManagerApp):
    """Current MDIR-P application without the historical version chain."""

    TITLE = f"MDIR-P {VERSION}"
    SUB_TITLE = "Dual Pane File Manager"
    CSS = FastFileManagerApp.CSS + """
    .thumbnail-toggle {
        min-width: 4;
        width: 4;
        height: 1;
        min-height: 1;
        padding: 0;
        margin: 0 0 0 1;
        border: none;
    }
    .thumbnail-toggle.thumbnail-on {
        background: $success;
        color: $background;
        text-style: bold;
    }
    .selection-spacer { width: 1fr; height: 1; }
    .selection-actions {
        width: 12;
        min-width: 12;
        height: 1;
        margin: 0 0 0 2;
    }
    .drive-bar .selection-actions Button {
        width: 4;
        min-width: 4;
        margin: 0;
        text-style: bold;
    }
    .drive-bar .selection-actions .select-all { color: #e5a000; }
    .drive-bar .selection-actions .select-none { color: #eeeeee; }
    .drive-bar .selection-actions .select-invert { color: #ff5555; }
    #document_preview {
        display: none;
    }

    #shortcut_bar {
        width: 100%;
        height: 2;
        min-height: 2;
        max-height: 2;
        padding: 0;
        background: $panel;
        scrollbar-size-horizontal: 1;
    }

    #shortcut_bar Button {
        height: 2;
        min-height: 2;
        min-width: 8;
        width: auto;
        margin: 0 1 0 0;
        padding: 0 1;
        border: none;
        background: $surface;
        color: $foreground;
        content-align: center middle;
    }

    #shortcut_bar Button:hover {
        background: $primary;
        color: $text-primary;
    }

    #shortcut_edit {
        color: $accent;
        text-style: bold;
    }

    #shortcut_reload {
        color: $success;
    }

    #right_wrap.preview-mode #right {
        display: none;
    }

    #right_wrap.preview-mode #ai_panel {
        display: none;
    }

    #right_wrap.preview-mode #right_drive_bar,
    #right_wrap.preview-mode #right_drive_info {
        display: block;
    }

    #right_wrap.preview-mode #document_preview {
        display: block;
        width: 100%;
        height: 1fr;
        min-height: 0;
    }
    """ + MDIR_THEME_CSS
    BINDINGS = FastFileManagerApp.BINDINGS + [
        Binding(
            "ctrl+f3",
            "toggle_preview",
            "Preview",
            show=True,
            priority=True,
            id="mdir.preview",
        ),
    ] + THUMBNAIL_BINDINGS

    def __init__(self) -> None:
        self._init_thumbnails()
        self.preview_enabled = False
        self.preview_mode = False
        self._shortcut_keyboard = None
        self._shortcut_epoch = 0
        self._shortcut_context = None
        self._file_shortcuts = {}
        self._shortcut_watch_ready = False
        self._preview_modal_suspended = False
        self._preview_path = None
        self._shift_left_latched = False
        self._terminal_window_handle = 0
        self._hotkey_timer: Optional[Timer] = None
        self._preview_layout_timer: Optional[Timer] = None
        self._native_preview: Optional["NativePreviewController"] = None
        self._preview_suppressed_path: Optional[Path] = None
        self.shortcuts = load_shortcuts()
        self.shortcut_project = Path(__file__).resolve().parent.parent
        super().__init__()
        self.user_keymap = load_keymap()
        self.set_keymap(self.user_keymap)
        self.register_theme(MDIR_THEME)
        self.theme = THEME_NAME

    @property
    def native_preview(self) -> "NativePreviewController":
        """Create the Windows overlay only when Preview is first requested."""
        if self._native_preview is None:
            from .preview.native import NativePreviewController

            self._native_preview = NativePreviewController(
                self,
                open_callback=self._native_open_document,
                full_view_callback=self._native_full_view,
                files_callback=self._native_restore_files,
            )
        return self._native_preview

    def _watch_theme(self, theme_name: str) -> None:
        """Apply theme colors to CSS, file cells, and native Preview."""
        super()._watch_theme(theme_name)
        install_file_colors(self.current_theme)
        if self.is_running:
            native_preview = self._native_preview
            if native_preview is not None:
                native_preview.update_theme()
            self.call_after_refresh(self._refresh_themed_file_rows)

    def _refresh_themed_file_rows(self) -> None:
        """Rebuild cached cells without another filesystem scan."""
        for pane in (self.left, self.right):
            if not getattr(pane, "initial_listing_complete", False):
                continue
            selected = pane.selected_path()
            keep_name = selected.name if selected is not None else None
            pane._render_cached_rows(keep_name)

    def compose(self) -> ComposeResult:
        yield Header()
        with HorizontalScroll(id="shortcut_bar"):
            yield Button(
                "Edit Links",
                id="shortcut_edit",
                tooltip="Edit the MDIR-P shortcut configuration",
            )
            for index in range(MAX_SHORTCUTS):
                shortcut = (
                    self.shortcuts[index]
                    if index < len(self.shortcuts)
                    else None
                )
                yield Button(
                    shortcut.label if shortcut else "",
                    id=f"shortcut_{index}",
                    classes="shortcut-button",
                    tooltip=(
                        self._shortcut_tooltip(shortcut)
                        if shortcut
                        else ""
                    ),
                )
            yield Button(
                "Reload",
                id="shortcut_reload",
                tooltip="Reload shortcuts after editing the JSON file",
            )
        with Horizontal(id="panes"):
            with Vertical(id="left_wrap", classes="pane-wrap"):
                with Horizontal(id="left_drive_bar", classes="drive-bar"):
                    yield from self._drive_buttons("left")
                yield Static("", id="left_drive_info", classes="drive-info")
                yield LargeDirectoryFilePane(
                    "left",
                    self.left_start,
                    self.column_widths,
                    self._initial_hidden_system['left'],
                )

            with Vertical(id="right_wrap", classes="pane-wrap"):
                with Horizontal(id="right_drive_bar", classes="drive-bar"):
                    yield from self._drive_buttons("right")
                yield Static("", id="right_drive_info", classes="drive-info")
                yield LargeDirectoryFilePane(
                    "right",
                    self.right_start,
                    self.column_widths,
                    self._initial_hidden_system['right'],
                )
                yield DocumentPreviewPanel(id="document_preview")

        yield Static("", id="status")
        yield Footer()
        yield Static(
            f"{self.TITLE}\nStarting file panels...",
            id="startup_cover",
        )

    @staticmethod
    def _drive_buttons(side: str):
        prefix = "l" if side == "left" else "r"
        label = side.upper()
        for index in range(26):
            letter = chr(ord("A") + index)
            yield Button(
                letter,
                id=f"{prefix}drive_{letter.lower()}",
                classes="drive-button",
                tooltip=f"Switch {label} pane to {letter}:\\",
            )
        yield Button(
            "Hidden",
            id=f"{side}_hidden_toggle",
            classes="hidden-toggle",
            tooltip="Show or hide Hidden/System files",
        )
        yield Button('Th', id=f'{side}_thumbnail', classes='thumbnail-toggle',
                     tooltip='Thumbnail / List for this pane (Alt+T)')
        yield Static('', classes='selection-spacer')
        with Horizontal(classes='selection-actions'):
            for mode, symbol, description in (
                ('all', '*a', 'Select All'),
                ('none', '*-', 'Deselect All'),
                ('invert', '**', 'Invert Selection'),
            ):
                yield Button(symbol, id=f'{side}_select_{mode}',
                             classes=f'selection-button select-{mode}',
                             tooltip=f'{description} — {side.upper()} pane')

    @on(Button.Pressed, '.selection-button')
    def selection_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if len(self.screen_stack) != 1:
            return
        side, mode = event.button.id.split('_select_')
        if side == 'right' and self.ai_mode:
            self.query_one('#ai_panel').focus_prompt()
            self.set_status('Use F12 to restore the right file pane before selecting files.')
            return
        if side == 'right' and self.preview_mode:
            self._hide_document_preview(restore_right_focus=False)
            self.preview_enabled = False
        self.set_active(side)
        if not self.active.set_bulk_selection(mode):
            self.set_status(f'{side.title()} pane: wait for the file list to finish loading.')
            return
        self._sync_thumbnails()
        description = {'all': 'Select All', 'none': 'Deselect All', 'invert': 'Invert Selection'}[mode]
        self.set_status(f'{side.title()} pane: {description} — {len(self.active.marked):,} selected.')

    @property
    def document_preview(self) -> DocumentPreviewPanel:
        return self.query_one("#document_preview", DocumentPreviewPanel)

    @on(Button.Pressed, '.thumbnail-toggle')
    def thumbnail_button_pressed(self, event: Button.Pressed) -> None:
        # Decorated handlers must live on a Textual class: a plain Python mixin
        # has no MessagePump metaclass to register @on handlers.
        event.stop()
        if len(self.screen_stack) == 1:
            side = 'left' if event.button.id == 'left_thumbnail' else 'right'
            self._toggle_thumbnail(side)

    def on_mount(self) -> None:
        super().on_mount()
        self.screen_change_signal.subscribe(self, self._preview_screen_changed, immediate=True)
        self.screen_change_signal.subscribe(self, self._sync_shortcut_keyboard, immediate=True)
        self.watch(self.screen, 'focused', self._sync_shortcut_keyboard)
        self.watch(self, 'app_focus', self._sync_shortcut_keyboard)
        self._shortcut_watch_ready = True
        self._sync_shortcut_buttons()
        self.document_preview.disabled = True
        self._terminal_window_handle = self._active_window_handle()
        if not self.is_headless:
            self._shortcut_keyboard = NativeShortcuts(self._terminal_window_handle,
                lambda key, epoch: self.post_message(NativeShortcut(key, epoch)))
            if not self._shortcut_keyboard.start():
                self.set_status('Windows shortcut capture unavailable; terminal key handling remains active. ' +
                                self._shortcut_keyboard.error)
        self._sync_shortcut_keyboard()
        self._hotkey_timer = self.set_interval(
            HOTKEY_POLL_SECONDS,
            self._poll_native_pointer,
        )

    def set_active(self, side: str, *, focus_table: bool = True) -> None:
        super().set_active(side, focus_table=focus_table)
        # Mouse dispatch focuses the clicked table before it activates its
        # pane. The focus watcher temporarily disables capture in that gap;
        # focus() then sees the same table, so there is no second notification.
        # Publish the completed pane transition, including same-focus clicks.
        self._sync_shortcut_keyboard()

    def set_keymap(self, keymap) -> None:
        super().set_keymap(keymap)
        self._file_shortcuts = shortcut_routes(keymap)
        if self._shortcut_watch_ready:
            self._sync_shortcut_keyboard()

    def _in_file_shortcut_context(self) -> bool:
        if not self.is_running or len(self.screen_stack) != 1 or not self.app_focus:
            return False
        return self.focused is self.active.table and not (self.ai_mode and self.active_side == 'right')

    def _sync_shortcut_keyboard(self, *args) -> None:
        if not self._shortcut_watch_ready:
            return
        enabled = self._in_file_shortcut_context()
        context = (enabled, id(self.screen), id(self.focused), self.active_side,
                   tuple(self._file_shortcuts.items()))
        if context == self._shortcut_context:
            return
        self._shortcut_context = context
        self._shortcut_epoch += 1
        if self._shortcut_keyboard is not None:
            self._shortcut_keyboard.configure(self._shortcut_epoch, self._file_shortcuts if enabled else {})

    def check_action(self, action, parameters):
        file_actions = {entry[0] for entry in self._file_shortcuts.values()}
        if action in file_actions and not self._in_file_shortcut_context():
            # F12 must still let the user leave the AI input panel.
            if not (action == 'toggle_ai_terminal' and len(self.screen_stack) == 1 and self.ai_mode):
                return False
        return super().check_action(action, parameters)

    async def on_event(self, event: events.Event) -> None:
        # Route configured file commands before DataTable consumes a custom key
        # (for example Ctrl+Home). Inputs and modal screens retain their keys.
        if isinstance(event, events.Key) and not event.is_forwarded and self._in_file_shortcut_context() and event.key in self._file_shortcuts:
            event.stop()
            action, parameters = self._file_shortcuts[event.key]
            await self.run_action((None, action, parameters))
            return
        await super().on_event(event)

    async def on_native_shortcut(self, event: NativeShortcut) -> None:
        self._sync_shortcut_keyboard()
        if event.epoch != self._shortcut_epoch or not self._in_file_shortcut_context():
            return
        route = self._file_shortcuts.get(event.key)
        if route is not None:
            await self.run_action((None, route[0], route[1]))

    def _preview_screen_changed(self, screen) -> None:
        if len(self.screen_stack) > 1:
            if self.preview_mode:
                self._preview_modal_suspended = True
                self.native_preview.suspend(wait=True)
            self._sync_thumbnails()
        elif self._preview_modal_suspended:
            self.call_after_refresh(self._resume_preview_after_modal)

    def _resume_preview_after_modal(self) -> None:
        if len(self.screen_stack) != 1 or self._closing:
            return
        if not self._preview_modal_suspended:
            return
        self._preview_modal_suspended = False
        if self.preview_enabled and self.preview_mode and not self.ai_mode:
            if self.left.selected_path() == self._preview_path:
                self.native_preview.resume()
                self._schedule_preview_layout(0.08)
            else:
                self._preview_current_left_selection()
        self._sync_thumbnails()

    @staticmethod
    def _shortcut_tooltip(shortcut: ShortcutDefinition) -> str:
        return f"{shortcut.kind.title()}: {shortcut.target}"

    def _sync_shortcut_buttons(self) -> None:
        """Update fixed button slots without rebuilding the application tree."""
        for index in range(MAX_SHORTCUTS):
            button = self.query_one(f"#shortcut_{index}", Button)
            if index < len(self.shortcuts):
                shortcut = self.shortcuts[index]
                button.label = shortcut.label
                button.tooltip = self._shortcut_tooltip(shortcut)
                button.display = True
            else:
                button.display = False

    def _expanded_shortcut_text(self, value: str) -> str:
        return expand_shortcut_text(
            value,
            current=self.active.current_path,
            left=self.left.current_path,
            right=self.right.current_path,
            project=self.shortcut_project,
            selected=self.active.selected_path(),
            left_selected=self.left.selected_path(),
            right_selected=self.right.selected_path(),
        )

    def _shortcut_pane(self, shortcut: ShortcutDefinition):
        if shortcut.pane == "left":
            return self.left
        if shortcut.pane == "right":
            return self.right
        return self.active

    def _open_shortcut_folder(self, shortcut: ShortcutDefinition) -> None:
        target = Path(self._expanded_shortcut_text(shortcut.target))
        try:
            target = target.resolve()
            if not target.is_dir():
                raise NotADirectoryError("directory does not exist")
        except (OSError, RuntimeError) as exc:
            self.set_status(f"Shortcut folder unavailable: {target} ({exc})")
            return

        pane = self._shortcut_pane(shortcut)
        side = "left" if pane is self.left else "right"
        pane.current_path = target
        pane.marked.clear()
        pane.refresh_listing()
        pane.update_summary()
        self.set_active(side)
        self._save_paths()
        self.update_drive_bar()
        self.set_status(f"Shortcut: {shortcut.label} -> {target}")

    def _launch_shortcut_process(
        self,
        shortcut: ShortcutDefinition,
        *,
        command: bool = False,
    ) -> None:
        target = self._expanded_shortcut_text(shortcut.target)
        working_directory = str(self.active.current_path)
        if command:
            executable = (
                "powershell.exe" if os.name == "nt" else "/bin/sh"
            )
            command_arguments = (
                ["-NoExit", "-Command", target]
                if os.name == "nt"
                else ["-lc", target]
            )
            arguments = [executable, *command_arguments]
        else:
            arguments = [
                target,
                *(self._expanded_shortcut_text(arg) for arg in shortcut.args),
            ]
        process_options = (
            {"creationflags": subprocess.CREATE_NEW_CONSOLE}
            if os.name == "nt"
            else {"start_new_session": True}
        )
        subprocess.Popen(
            arguments,
            cwd=working_directory,
            **process_options,
        )
        self.set_status(f"Launched shortcut: {shortcut.label}")

    async def _run_shortcut_action(self, shortcut: ShortcutDefinition) -> None:
        allowed_actions = {
            "toggle_ai_terminal",
            "toggle_preview",
            "search",
            "powershell_here",
            "refresh_all",
            "hidden_system",
        }
        if shortcut.target not in allowed_actions:
            raise ValueError(f"unsupported action: {shortcut.target}")
        method = getattr(self, f"action_{shortcut.target}")
        result = method()
        if inspect.isawaitable(result):
            await result

    async def _activate_shortcut(self, shortcut: ShortcutDefinition) -> None:
        try:
            if shortcut.kind == "folder":
                self._open_shortcut_folder(shortcut)
            elif shortcut.kind == "file":
                target = Path(self._expanded_shortcut_text(shortcut.target))
                if not target.is_file():
                    raise FileNotFoundError(target)
                if os.name == "nt":
                    os.startfile(target)
                else:
                    subprocess.Popen(["xdg-open", str(target)])
                self.set_status(f"Opened shortcut: {shortcut.label}")
            elif shortcut.kind == "program":
                self._launch_shortcut_process(shortcut)
            elif shortcut.kind == "command":
                self._launch_shortcut_process(shortcut, command=True)
            elif shortcut.kind == "web":
                target = self._expanded_shortcut_text(shortcut.target)
                if not webbrowser.open(target, new=2):
                    raise OSError("the default browser did not accept the URL")
                self.set_status(f"Opened website: {shortcut.label}")
            elif shortcut.kind == "action":
                await self._run_shortcut_action(shortcut)
        except Exception as exc:
            self.set_status(f"Shortcut failed: {shortcut.label} ({exc})")

    def _open_link_manager(self) -> None:
        from .ui.shortcuts import ShortcutManagerScreen

        def links_edited(
            shortcuts: Optional[list[ShortcutDefinition]],
        ) -> None:
            if shortcuts is None:
                self.set_status("Link editing cancelled.")
                self.set_active(self.active_side)
                return
            try:
                config_path = save_shortcuts(shortcuts)
                self.shortcuts = shortcuts
                self._sync_shortcut_buttons()
                self.set_status(
                    f"Saved {len(shortcuts)} link(s): {config_path}"
                )
            except Exception as exc:
                self.set_status(f"Could not save links: {exc}")
            self.set_active(self.active_side)

        self.push_screen(
            ShortcutManagerScreen(
                self.shortcuts,
                self.active.current_path,
            ),
            links_edited,
        )

    def _open_key_manager(self) -> None:
        from .ui.options import KeyManagerScreen

        def keys_edited(keymap: Optional[dict[str, str]]) -> None:
            if keymap is None:
                self.set_status("Key editing cancelled.")
                self.set_active(self.active_side)
                return
            try:
                config_path = save_keymap(keymap)
                self.user_keymap = keymap
                self.set_keymap(keymap)
                self.set_status(f"Saved custom keys: {config_path}")
            except Exception as exc:
                self.set_status(f"Could not save keys: {exc}")
            self.set_active(self.active_side)

        self.push_screen(KeyManagerScreen(self.user_keymap), keys_edited)

    def action_options(self) -> None:
        from .ui.options import OptionsScreen

        def option_selected(option: Optional[str]) -> None:
            if option == "keys":
                self._open_key_manager()
            elif option == "links":
                self._open_link_manager()
            elif option == "theme":
                self.action_change_theme()
            elif option == "help":
                readme_path = self._readme_path()
                if readme_path.is_file():
                    self.push_screen(self.VIEWER_SCREEN(readme_path))
                else:
                    self.set_status(f"README.md not found: {readme_path}")
            else:
                self.set_active(self.active_side)

        self.push_screen(OptionsScreen(), option_selected)

    def _readme_path(self) -> Path:
        """Locate the guide in source, wheel, or portable installations."""
        candidates = (
            self.shortcut_project / "README.md",
            Path(sys.prefix) / "share" / "mdir-p" / "README.md",
            Path(sys.executable).resolve().parent / "README.md",
        )
        return next((path for path in candidates if path.is_file()), candidates[0])

    @on(Button.Pressed, "#shortcut_bar Button")
    async def shortcut_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        event.stop()

        if button_id == "shortcut_edit":
            self._open_link_manager()
            return

        if button_id == "shortcut_reload":
            self.shortcuts = load_shortcuts()
            self._sync_shortcut_buttons()
            self.set_status(
                f"Reloaded {len(self.shortcuts)} shortcut(s) from "
                f"{shortcut_config_path()}"
            )
            return

        if not button_id.startswith("shortcut_"):
            return
        try:
            index = int(button_id.removeprefix("shortcut_"))
            shortcut = self.shortcuts[index]
        except (ValueError, IndexError):
            return
        await self._activate_shortcut(shortcut)

    @staticmethod
    def _active_window_handle() -> int:
        if os.name != "nt":
            return 0
        try:
            get_foreground = ctypes.windll.user32.GetForegroundWindow
            get_foreground.restype = wintypes.HWND
            return int(get_foreground() or 0)
        except Exception:
            return 0

    def _poll_native_pointer(self) -> None:
        # Retain the Windows Terminal Shift-click fallback. Ctrl+F3 is handled
        # by key transitions, never a second, time-based polling path.
        if getattr(self, "_background_polling_paused", lambda: False)():
            self._shift_left_latched = False
            return
        if getattr(self, "_file_operation_busy", False) or getattr(
            self, "_archive_busy", False
        ):
            return
        self._poll_windows_shift_range_click()

    def _poll_windows_shift_range_click(self) -> None:
        """Recover Shift+left-clicks consumed by Windows Terminal."""
        if os.name != "nt" or not self._terminal_window_handle:
            return
        try:
            user32 = ctypes.windll.user32
            get_key_state = user32.GetAsyncKeyState
            get_key_state.argtypes = [ctypes.c_int]
            get_key_state.restype = ctypes.c_short
            left_state = int(get_key_state(VK_LBUTTON))
            shift_down = bool(int(get_key_state(VK_SHIFT)) & 0x8000)
            left_down = bool(left_state & 0x8000)
            clicked = bool(left_state & 0x0001) or (
                left_down and not self._shift_left_latched
            )
            self._shift_left_latched = left_down

            if not shift_down or not clicked:
                return
            if self._active_window_handle() != self._terminal_window_handle:
                return

            point = wintypes.POINT()
            if not user32.GetCursorPos(ctypes.byref(point)):
                return
            self._apply_shift_range_screen_click(point.x, point.y)
        except Exception:
            self._shift_left_latched = False

    def _apply_shift_range_screen_click(
        self,
        screen_x: int,
        screen_y: int,
        terminal_grid: Optional["WindowRectangle"] = None,
    ) -> bool:
        """Apply a native Shift click to the table row under the pointer."""
        if terminal_grid is None:
            from .preview.native import windows_terminal_grid_rectangle

            terminal_grid = windows_terminal_grid_rectangle(
                self._terminal_window_handle
            )
        if terminal_grid is None:
            return False

        cell = terminal_screen_point_to_cell(
            screen_x,
            screen_y,
            terminal_grid,
            self.size.width,
            self.size.height,
        )
        if cell is None:
            return False
        cell_x, cell_y = cell

        for pane in (self.left, self.right):
            table = pane.table
            region = table.region
            if not (
                region.x <= cell_x < region.x + region.width
                and region.y <= cell_y < region.y + region.height
            ):
                continue
            if pane.shift_anchor_row is None:
                return False

            local_y = cell_y - region.y
            target_row = (
                int(table.scroll_offset.y)
                + local_y
                - int(table.header_height)
            )
            if not (0 <= target_row < table.row_count):
                return False

            pane.select_range_to(target_row)
            self.set_active("left" if pane.id == "left" else "right")
            table._shift_mouse_click_pending = True
            return True
        return False

    def _native_preview_layout(self) -> Optional[PaneLayout]:
        from .preview.native import PaneLayout

        try:
            widget = self.document_preview if self.preview_mode else self.right
            region = widget.region
            if region.width <= 0 or region.height <= 0:
                region = self.right.region
            if region.width <= 0 or region.height <= 0:
                return None
            return PaneLayout(
                x=region.x,
                y=region.y,
                width=region.width,
                height=region.height,
                columns=max(1, self.size.width),
                rows=max(1, self.size.height),
            )
        except Exception:
            return None

    def _sync_native_preview_layout(self) -> None:
        if not self.preview_mode:
            return
        pane_layout = self._native_preview_layout()
        if pane_layout is not None:
            self.native_preview.update_layout(pane_layout)

    def _schedule_preview_layout(self, delay: float) -> None:
        self.call_after_refresh(self._sync_native_preview_layout)
        if self._preview_layout_timer is not None:
            self._preview_layout_timer.stop()
        self._preview_layout_timer = self.set_timer(
            delay,
            self._sync_native_preview_layout,
        )

    def _show_document_preview(self, path: Path) -> None:
        if len(self.screen_stack) != 1 or not self.preview_enabled or self.ai_mode or not can_preview(path):
            return

        pane_layout = self._native_preview_layout()
        shown = self.native_preview.show(path, pane_layout=pane_layout)
        wrap = self.query_one("#right_wrap", Vertical)
        self.preview_mode = True
        self._preview_path = path
        self.right.disabled = True
        wrap.set_class(False, "ai-mode")
        wrap.set_class(True, "preview-mode")

        if shown:
            self.document_preview.cancel()
            self.document_preview.disabled = True
            self.document_preview.canvas.update(
                f"Loading native preview...\n\n{path.name}"
            )
            self.set_status(
                f"Preview: {path.name} | background loading | "
                "Wheel: zoom | Drag: pan | Ctrl+F3: on/off"
            )
        else:
            self.document_preview.disabled = False
            self.document_preview.show_path(path)
            self.set_status(
                f"Preview: {path.name} | Ctrl+F3 toggles preview | "
                "Right/Tab restores files"
            )
        self._schedule_preview_layout(0.08)

    def _hide_document_preview(
        self,
        *,
        restore_right_focus: bool = False,
        wait_for_native: bool = False,
    ) -> None:
        self.native_preview.hide(wait=wait_for_native)
        if not self.preview_mode:
            return
        self.preview_mode = False
        self._preview_path = None
        self.document_preview.cancel()
        self.document_preview.disabled = True
        self.right.disabled = False
        self.query_one("#right_wrap", Vertical).set_class(
            False,
            "preview-mode",
        )
        if restore_right_focus:
            self.set_active("right")

    def _preview_current_left_selection(self) -> None:
        if len(self.screen_stack) != 1 or self.ai_mode or not self.preview_enabled:
            return
        path = self.left.selected_path()
        if path == self._preview_suppressed_path:
            return
        self._preview_suppressed_path = None
        if can_preview(path):
            self._show_document_preview(path)
        else:
            self._hide_document_preview(restore_right_focus=False)

    @on(DataTable.RowHighlighted)
    def preview_row_highlighted(
        self,
        event: DataTable.RowHighlighted,
    ) -> None:
        try:
            if event.data_table is self.left.table:
                self._preview_current_left_selection()
        except Exception:
            pass

    def action_toggle_preview(self) -> None:
        if len(self.screen_stack) != 1:
            return

        self.preview_enabled = not self.preview_enabled
        if self.preview_enabled:
            self._preview_suppressed_path = None
            self._preview_current_left_selection()
            if not self.preview_mode:
                self.set_status(
                    "Preview enabled. Select an image, PDF, Office, CSV, "
                    "text, or Markdown file."
                )
            self._restore_preview_file_focus()
            self.call_after_refresh(self._restore_preview_file_focus)
            self.set_timer(0.08, self._restore_preview_file_focus)
            self.set_timer(0.22, self._restore_preview_file_focus)
        else:
            self._hide_document_preview(restore_right_focus=False)
            self.set_status("Automatic document preview disabled.")

    def _restore_preview_file_focus(self) -> None:
        if len(self.screen_stack) != 1 or not self.preview_enabled or not self.preview_mode or self.ai_mode:
            return
        self.native_preview.restore_terminal_focus()
        self.set_active("left")
        self.left.table.refresh()
        self.left.table.focus()

    def action_focus_right(self) -> None:
        if self.preview_mode:
            self._hide_document_preview(restore_right_focus=True)
            self.set_status("Right file pane restored.")
            return
        super().action_focus_right()

    def action_switch_pane(self) -> None:
        if self.preview_mode and self.active_side == "left":
            self._hide_document_preview(restore_right_focus=True)
            self.set_status("Right file pane restored.")
            return
        super().action_switch_pane()

    async def action_toggle_ai_terminal(self) -> None:
        if self.preview_mode:
            self._hide_document_preview(restore_right_focus=False)
        await super().action_toggle_ai_terminal()

    @on(DocumentPreviewPanel.CloseRequested)
    def close_document_preview(
        self,
        event: DocumentPreviewPanel.CloseRequested,
    ) -> None:
        event.stop()
        self._hide_document_preview(restore_right_focus=True)
        self.set_status("Right file pane restored.")

    @on(DocumentPreviewPanel.FullViewRequested)
    def full_document_preview(
        self,
        event: DocumentPreviewPanel.FullViewRequested,
    ) -> None:
        event.stop()
        self.action_view()

    @on(DocumentPreviewPanel.OpenRequested)
    def open_previewed_document(
        self,
        event: DocumentPreviewPanel.OpenRequested,
    ) -> None:
        event.stop()
        path = self.left.selected_path()
        if path is None:
            return
        try:
            self.open_external_path(path)
            self.set_status(
                f"Opened with the default application: {path}"
            )
        except Exception as exc:
            self.set_status(f"Could not open {path.name}: {exc}")

    def _native_full_view(self) -> None:
        self.action_view()

    def _native_open_document(self, path: Path) -> None:
        try:
            self.open_external_path(path)
            self.set_status(f"Opened with the default application: {path}")
        except Exception as exc:
            self.set_status(f"Could not open {path.name}: {exc}")

    def open_external_path(self, path: Path) -> None:
        """Remove Preview before giving the file to another application."""
        if self._thumbnail_manager is not None:
            self._thumbnail_manager.suspend_external()
        self._preview_suppressed_path = path
        if self.preview_mode:
            self._hide_document_preview(
                restore_right_focus=False,
                wait_for_native=True,
            )
        super().open_external_path(path)

    def _native_restore_files(self) -> None:
        self._hide_document_preview(restore_right_focus=True)
        self.set_status("Right file pane restored.")

    def _selected_action_file(self, action_name: str) -> Path | None:
        path = self.active.selected_path()
        if path is None or path.is_dir():
            self.set_status(
                f"{action_name} works on supported text files only."
            )
            return None
        return path

    def _safe_text_action_allowed(
        self,
        path: Path,
        *,
        action_name: str,
        limit: int,
    ) -> bool:
        decision = inspect_safe_text_file(path, max_bytes=limit)
        if decision.allowed:
            return True
        self.set_status(
            self._safe_text_block_message(
                path,
                action_name=action_name,
                decision=decision,
            )
        )
        return False

    @staticmethod
    def _safe_text_block_message(
        path: Path,
        *,
        action_name: str,
        decision: SafeTextDecision,
    ) -> str:
        prefix = f"{action_name} ignored: {path.name}"
        if decision.reason == "unsupported_type":
            file_type = path.suffix.lower() or "extensionless file"
            return (
                f"{prefix} ({file_type}) is not a supported text format. "
                "Use Enter or Preview instead."
            )
        if decision.reason == "too_large":
            return (
                f"{prefix} is {format_file_size(decision.size)}; "
                f"the safety limit is {format_file_size(decision.limit)}."
            )
        if decision.reason == "binary_content":
            return f"{prefix} contains binary data and was not opened."
        if decision.reason == "not_file":
            return f"{action_name} works on supported text files only."
        return f"{prefix} could not be read."

    def action_view(self) -> None:
        path = self._selected_action_file("F3 View")
        if path is None:
            return
        if not self._safe_text_action_allowed(
            path,
            action_name="F3 View",
            limit=DEFAULT_VIEW_LIMIT,
        ):
            return
        self.native_preview.hide()
        super().action_view()

    def action_edit(self) -> None:
        path = self._selected_action_file("F4 Edit")
        if path is None:
            return
        if not self._safe_text_action_allowed(
            path,
            action_name="F4 Edit",
            limit=DEFAULT_EDIT_LIMIT,
        ):
            return
        super().action_edit()

    def on_resize(self, event: events.Resize) -> None:
        if self.preview_mode:
            self._schedule_preview_layout(0.12)

    def on_unmount(self) -> None:
        if self._shortcut_keyboard is not None:
            self._shortcut_keyboard.configure(self._shortcut_epoch + 1, {})
            self._shortcut_keyboard.shutdown()
        self._shutdown_thumbnails()
        if self._preview_layout_timer is not None:
            self._preview_layout_timer.stop()
            self._preview_layout_timer = None
        if self._hotkey_timer is not None:
            self._hotkey_timer.stop()
            self._hotkey_timer = None
        if self._native_preview is not None:
            self._native_preview.shutdown()
        super().on_unmount()


def self_check() -> int:
    """Run a dependency-light structural check for the current package."""
    print(f"MDIR-P {VERSION} package self-check")
    print(f"Default theme: {THEME_NAME}")
    print("Preview starts disabled and uses bounded background rendering")
    print('Thumbnails: Alt+T / Th, independent panes, one Tk loop, bounded workers')
    print("F3/F4 accept bounded text files only")
    print("Large directories use cached metadata and batched row insertion")
    print("Copy, Move, and Delete use cancellable background workers")
    print(f"Top shortcut bar supports up to {MAX_SHORTCUTS} user links")
    required = {".jpg", ".png", ".pdf", ".xlsx", ".xls"}
    if not required.issubset(PREVIEW_EXTENSIONS):
        print("ERROR - required Preview formats are missing.")
        return 1
    app = MDirApp()
    if app.preview_enabled:
        print("ERROR - Preview must start disabled.")
        return 1
    if any(app.thumbnail_modes.values()):
        print('ERROR - Thumbnail views must start disabled.')
        return 1
    if app.theme != THEME_NAME:
        print("ERROR - default theme was not installed.")
        return 1
    print("OK - MDIR-P package is ready.")
    return 0
