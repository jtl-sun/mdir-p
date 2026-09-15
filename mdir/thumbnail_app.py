"""Textual-side thumbnail state; file panes remain the single selection authority."""
from __future__ import annotations

from textual.binding import Binding
from textual.widgets import Button

from .preview.native import PaneLayout
from .thumbnail import SIZES, ThumbnailItem, navigate
from .thumbnail_native import PaneState, ThumbnailEvent, ThumbnailManager


THUMBNAIL_BINDINGS = [
    Binding('alt+t', 'toggle_thumbnail', 'Thumbnails', show=False, priority=True),
    *[Binding(key, f"thumbnail_navigate('{key}')", '', show=False, priority=True)
      for key in ('left', 'right', 'up', 'down', 'home', 'end', 'pageup', 'pagedown')],
]


class ThumbnailAppMixin:
    def _init_thumbnails(self):
        self.thumbnail_modes = {'left': False, 'right': False}
        self.thumbnail_sizes = {'left': 144, 'right': 144}
        self._thumbnail_geometry = {'left': (1, 3), 'right': (1, 3)}
        self._thumbnail_snapshots = {}
        self._thumbnail_manager = None
        self._thumbnail_timer = None

    def check_action(self, action, parameters):
        if action in {'thumbnail_navigate', 'toggle_thumbnail'}:
            if len(self.screen_stack) != 1 or (self.ai_mode and self.active_side == 'right'):
                return False
            return self.focused is self.active.table
        return super().check_action(action, parameters)

    def action_toggle_thumbnail(self):
        self._toggle_thumbnail(self.active_side)

    def _toggle_thumbnail(self, side):
        if self.thumbnail_modes[side]:
            self.thumbnail_modes[side] = False
        else:
            if self._thumbnail_manager is None:
                self._thumbnail_manager = ThumbnailManager(self, self._terminal_window_handle)
            if not self._thumbnail_manager.start():
                self.set_status(self._thumbnail_manager.error)
                return
            # Preview and AI temporarily reserve the right pane. Explicit Th restores files.
            if self.preview_mode:
                self._hide_document_preview(restore_right_focus=False)
            self.preview_enabled = False
            if self.ai_mode and side == 'right':
                self.set_status('Use F12 to restore the right file pane, then Th.')
                return
            self.thumbnail_modes[side] = True
            if self._thumbnail_timer is None:
                self._thumbnail_timer = self.set_interval(0.15, self._sync_thumbnails)
        self.set_active(side)
        self._sync_thumbnails()
        enabled = ' + '.join(side for side, enabled in self.thumbnail_modes.items() if enabled)
        self.set_status(f'Thumbnail ({enabled}): Tab pane | Arrow navigate | Space/right-drag mark | F5 Copy | F6 Move | Alt+T List' if enabled else 'File list restored.')

    def _thumbnail_revision(self, pane):
        return (str(pane.current_path), pane._listing_generation,
                getattr(pane, '_thumbnail_revision', 0), pane.table.row_count,
                pane.initial_listing_complete and pane.cached_path == pane.current_path)

    def _sync_thumbnails(self):
        manager = self._thumbnail_manager
        if manager is None or not self.is_running or self._exit or self._closing:
            return
        states = {}
        for side in ('left', 'right'):
            enabled = self.thumbnail_modes[side]
            self.query_one(f'#{side}_thumbnail', Button).set_class(enabled, 'thumbnail-on')
            if not enabled:
                self._thumbnail_snapshots.pop(side, None)
                continue
            pane = self.left if side == 'left' else self.right
            revision = self._thumbnail_revision(pane)
            snapshot = self._thumbnail_snapshots.get(side)
            if snapshot is None or snapshot[0] != revision:
                items = []
                if revision[-1]:
                    for path in pane.entries[:pane.table.row_count]:
                        metadata = pane.metadata_by_path.get(path)
                        items.append(ThumbnailItem(path, path.name if path else '..',
                            metadata.is_directory if metadata else True,
                            metadata.modified if metadata else 0,
                            metadata.size if metadata else 0))
                snapshot = self._thumbnail_snapshots[side] = (revision, tuple(items))
            region = pane.table.region
            layout = PaneLayout(region.x, region.y, max(1, region.width), max(1, region.height),
                                max(1, self.size.width), max(1, self.size.height))
            theme = self.current_theme
            palette = (str(theme.background or '#202020'), str(theme.foreground or '#dddddd'),
                       str(theme.primary or '#7894a8'), str(theme.warning or '#f1cd69'))
            suspended = (len(self.screen_stack) != 1 or (side == 'right' and (self.ai_mode or self.preview_mode)))
            states[side] = PaneState(side, pane.current_path, revision, snapshot[1], pane.table.cursor_row,
                                    frozenset(pane.marked), self.thumbnail_sizes[side], side == self.active_side,
                                    layout, palette, suspended)
        manager.publish(states)
        if not states and self._thumbnail_timer is not None:
            self._thumbnail_timer.stop()
            self._thumbnail_timer = None

    def action_thumbnail_navigate(self, key):
        pane = self.active
        if not self.thumbnail_modes[self.active_side]:
            if key not in ('left', 'right'):
                actions = {'up': 'cursor_up', 'down': 'cursor_down', 'home': 'scroll_top',
                           'end': 'scroll_bottom', 'pageup': 'page_up', 'pagedown': 'page_down'}
                getattr(pane.table, 'action_' + actions[key])()
            return
        columns, page_rows = self._thumbnail_geometry[self.active_side]
        target = navigate(pane.table.cursor_row, pane.table.row_count, columns, key, page_rows)
        pane.reset_shift_selection_anchor()
        pane.table.move_cursor(row=target, column=0)
        pane.update_info()
        self._sync_thumbnails()

    async def on_thumbnail_event(self, event: ThumbnailEvent):
        if event.action == 'error':
            self.thumbnail_modes = {'left': False, 'right': False}
            self._sync_thumbnails()
            self.set_status(f'Thumbnail view unavailable: {self._thumbnail_manager.error}')
            return
        if event.side not in self.thumbnail_modes or not self.thumbnail_modes[event.side]:
            return
        if event.action == 'geometry':
            self._thumbnail_geometry[event.side] = event.value
            return
        if len(self.screen_stack) != 1 or (event.side == 'right' and (self.ai_mode or self.preview_mode)):
            return
        pane = self.left if event.side == 'left' else self.right
        # Ignore delayed clicks after directory changes, sorting, refresh, or row replacement.
        if event.revision != self._thumbnail_revision(pane):
            return
        if event.action == 'close':
            self._toggle_thumbnail(event.side)
            return
        if event.action == 'size':
            index = SIZES.index(self.thumbnail_sizes[event.side])
            self.thumbnail_sizes[event.side] = SIZES[max(0, min(len(SIZES) - 1, index + event.value))]
        elif event.action in ('select', 'mark', 'mark_drag', 'open'):
            if not 0 <= event.index < pane.table.row_count:
                return
            self.set_active(event.side)
            pane.table.move_cursor(row=event.index, column=0)
            if event.action == 'mark_drag':
                pane.reset_shift_selection_anchor()
                # Fast motion can cross many rows. Repaint/tally once per batch.
                with self.batch_update():
                    for row in dict.fromkeys(event.value):
                        if not 0 <= row < len(pane.entries):
                            continue
                        path = pane.entries[row]
                        if path is None:
                            continue
                        if path in pane.marked:
                            pane.marked.remove(path)
                        else:
                            pane.marked.add(path)
                        pane._update_mark_cell(path)
                    pane.update_info()
                    pane.update_summary()
            elif event.action == 'mark':
                path = pane.selected_path()
                if path is not None:
                    pane.toggle_mark_path(path)
            elif event.action == 'open':
                self._open_from_pane(pane)
        self._sync_thumbnails()

    def _shutdown_thumbnails(self):
        if self._thumbnail_timer:
            self._thumbnail_timer.stop()
            self._thumbnail_timer = None
        if self._thumbnail_manager:
            self._thumbnail_manager.shutdown()
