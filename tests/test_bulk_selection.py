import ctypes
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from textual.content import Content
from textual.widgets import Button, Static
from mdir.app import MDirApp
from mdir.file_pane import CachedEntry
from test_thumbnail import FakeManager


class BulkSelectionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for side in ('left', 'right'):
            folder = self.root / side
            folder.mkdir()
            (folder / 'photo.png').write_bytes(b'1234')
            (folder / 'notes.txt').write_text('notes')
            (folder / 'folder').mkdir()
            hidden = folder / '.hidden.txt'
            hidden.write_text('hidden')
            if os.name == 'nt':
                ctypes.windll.kernel32.SetFileAttributesW(str(hidden), 2)
        self.config = patch('mdir.core.load_config_data', return_value={})
        self.keys = patch('mdir.app.load_keymap', return_value={})
        self.manager = patch('mdir.thumbnail_app.ThumbnailManager', FakeManager)
        for patcher in (self.config, self.keys, self.manager): patcher.start()
        self.app = MDirApp()
        self.app.left_start = self.root / 'left'
        self.app.right_start = self.root / 'right'
        self.app._save_paths = lambda: None
        self.context = self.app.run_test(size=(140, 38))
        self.pilot = await self.context.__aenter__()
        await self.ready()

    async def asyncTearDown(self):
        await self.context.__aexit__(None, None, None)
        for patcher in (self.manager, self.keys, self.config): patcher.stop()
        self.temp.cleanup()

    async def ready(self):
        for _ in range(150):
            if self.app.left.initial_listing_complete and self.app.right.initial_listing_complete:
                return
            await self.pilot.pause(0.02)
        self.fail('Listing did not complete')

    async def click(self, side, mode):
        self.assertTrue(await self.pilot.click(f'#{side}_select_{mode}'))
        await self.pilot.pause()

    async def test_buttons_are_right_aligned_and_separate_from_th_on_both_sides(self):
        for width in (140, 110):
            await self.pilot.resize_terminal(width, 38)
            for side in ('left', 'right'):
                bar = self.app.query_one(f'#{side}_drive_bar')
                th = self.app.query_one(f'#{side}_thumbnail')
                buttons = [self.app.query_one(f'#{side}_select_{mode}', Button) for mode in ('all', 'none', 'invert')]
                self.assertEqual([str(b.label) for b in buttons], ['*a', '*-', '**'])
                self.assertEqual(
                    buttons[2].label,
                    Content.from_markup('[#e5a000]*[/][#eeeeee]*[/]'),
                )
                self.assertGreaterEqual(buttons[0].region.x - th.region.right, 2)
                self.assertEqual(buttons[-1].region.right, bar.region.right)
                self.assertTrue(all(b.region.y == th.region.y for b in buttons))

    async def test_select_invert_clear_are_independent_and_exclude_parent_and_hidden(self):
        for side in ('left', 'right', 'left'):
            pane = self.app.left if side == 'left' else self.app.right
            other = self.app.right if side == 'left' else self.app.left
            other_before = set(other.marked)
            pane.table.move_cursor(row=pane.row_by_path[pane.current_path / 'notes.txt'])
            cursor = pane.table.cursor_row
            await self.click(side, 'all')
            self.assertEqual(pane.marked, {pane.current_path / name for name in ('notes.txt', 'photo.png', 'folder')})
            self.assertEqual(pane.table.cursor_row, cursor)
            self.assertIs(self.app.focused, pane.table)
            self.assertEqual(other.marked, other_before)
            summary = str(pane.query_one('.pane_summary', Static).render())
            self.assertIn('Files: 2 / 2', summary)
            self.assertIn('Folders: 1 / 1', summary)
            pane.toggle_mark_path(pane.current_path / 'notes.txt')
            await self.click(side, 'invert')
            self.assertEqual(pane.marked, {pane.current_path / 'notes.txt'})
            await self.click(side, 'none')
            self.assertFalse(pane.marked)
            self.assertEqual(other.marked, other_before)

    async def test_hidden_items_and_thumbnail_selection_follow_same_marks(self):
        await self.pilot.click('#left_hidden_toggle')
        await self.ready()
        await self.pilot.click('#left_thumbnail')
        await self.pilot.click('#right_thumbnail')
        await self.click('left', 'all')
        pane = self.app.left
        self.assertIn(pane.current_path / '.hidden.txt', pane.marked)
        self.assertEqual(self.app._thumbnail_manager.states['left'].marked, frozenset(pane.marked))
        self.assertEqual(self.app._thumbnail_manager.states['right'].marked, frozenset())
        await self.click('left', 'invert')
        self.assertFalse(self.app._thumbnail_manager.states['left'].marked)
        await self.click('right', 'all')
        self.assertEqual(len(self.app.right.marked), 3)
        await self.click('right', 'none')
        self.assertFalse(self.app._thumbnail_manager.states['right'].marked)

    async def test_bulk_marks_feed_existing_copy_confirmation_and_engine(self):
        destination = self.root / 'copy-target'
        destination.mkdir()
        self.app.right.current_path = destination
        self.app.right.refresh_listing()
        await self.ready()
        await self.click('left', 'all')
        await self.pilot.press('f5')
        self.assertEqual(len(self.app.screen_stack), 2)
        await self.pilot.press('enter')
        for _ in range(150):
            if (destination / 'notes.txt').exists() and not self.app._file_operation_busy and len(self.app.screen_stack) == 1:
                break
            await self.pilot.pause(0.02)
        self.assertEqual({p.name for p in destination.iterdir()}, {'notes.txt', 'photo.png', 'folder'})
        self.assertEqual((destination / 'notes.txt').read_text(), 'notes')

    async def test_right_selection_restores_preview_pane_without_changing_left_marks(self):
        app = self.app
        app._native_preview = Mock()
        app._native_preview.show.return_value = True
        app.left.table.move_cursor(row=app.left.row_by_path[app.left.current_path / 'notes.txt'])
        app.set_active('left')
        await self.pilot.press('ctrl+f3')
        self.assertTrue(app.preview_mode)
        await self.click('right', 'all')
        self.assertFalse(app.preview_mode)
        self.assertFalse(app.preview_enabled)
        self.assertIs(app.focused, app.right.table)
        self.assertEqual(len(app.right.marked), 3)
        self.assertFalse(app.left.marked)

    async def test_empty_and_loading_panes_do_not_select_stale_entries(self):
        empty = self.root / 'empty'; empty.mkdir()
        pane = self.app.left
        await self.click('left', 'all')
        previous = set(pane.marked)
        pane.initial_listing_complete = False
        self.assertFalse(pane.set_bulk_selection('invert'))
        self.assertEqual(pane.marked, previous)
        pane.current_path = empty
        pane.marked.clear()
        pane.refresh_listing()
        await self.ready()
        for mode in ('all', 'invert', 'none'):
            await self.click('left', mode)
            self.assertFalse(pane.marked)

    async def test_five_thousand_items_use_cache_keep_cursor_and_reset_range(self):
        pane = self.app.left
        entries = [CachedEntry(pane.current_path / f'item-{i:05}.txt', False, i, 0) for i in range(5000)]
        pane._apply_scanned_entries(entries, pane.current_path)
        pane._render_cached_rows()
        pane.table.move_cursor(row=40)
        pane.set_shift_selection_anchor(10)
        await self.pilot.pause()
        with patch.object(pane, 'refresh_listing', side_effect=AssertionError('Unexpected scan')):
            await self.click('left', 'all')
            self.assertEqual(len(pane.marked), 5000)
            self.assertEqual(pane.table.cursor_row, 40)
            self.assertIsNone(pane.shift_anchor_row)
            self.assertIn('Files: 5,000 / 5,000', str(pane.query_one('.pane_summary', Static).render()))
            await self.click('left', 'invert')
            self.assertFalse(pane.marked)

    async def test_repeated_shift_page_selection_repaints_only_changed_rows(self):
        pane = self.app.left
        entries = [
            CachedEntry(
                pane.current_path / f'perf-{i:05}.txt',
                False,
                i,
                0,
            )
            for i in range(5000)
        ]
        pane._apply_scanned_entries(entries, pane.current_path)
        pane._render_cached_rows()
        start_row = pane.row_by_path[entries[10].path]
        pane.table.move_cursor(row=start_row, column=0)
        pane.reset_shift_selection_anchor()

        with (
            patch.object(
                pane,
                'refresh_listing',
                side_effect=AssertionError('Unexpected rescan'),
            ),
            patch.object(
                pane,
                '_update_mark_cell',
                wraps=pane._update_mark_cell,
            ) as repaint,
        ):
            pane.shift_select(40)
            self.assertEqual(len(pane.marked), 41)
            self.assertLessEqual(repaint.call_count, 41)

            repaint.reset_mock()
            pane.shift_select(40)
            self.assertEqual(len(pane.marked), 81)
            self.assertLessEqual(repaint.call_count, 40)

            repaint.reset_mock()
            pane.shift_select(-20)
            self.assertEqual(len(pane.marked), 61)
            self.assertLessEqual(repaint.call_count, 20)


    async def test_right_drag_tracks_captured_pointer_motion_and_accelerates_below_pane(self):
        pane = self.app.left
        entries = [
            CachedEntry(
                pane.current_path / f'pointer-{i:03}.txt',
                False,
                i,
                0,
            )
            for i in range(200)
        ]
        pane._apply_scanned_entries(entries, pane.current_path)
        pane._render_cached_rows()
        table = pane.table
        start = pane.row_by_path[entries[2].path]
        table._right_dragging = True
        table._drag_rows_seen.clear()
        table._right_drag_last_row = None
        table._toggle_drag_range_to(start)

        scroll_y = int(table.scroll_offset.y)
        target = min(table.row_count - 1, scroll_y + 8)
        local_y = int(table.header_height) + target - scroll_y
        local_x = 10
        event = SimpleNamespace(
            screen_x=int(table.region.x) + local_x,
            screen_y=int(table.region.y) + local_y,
            x=local_x,
            y=local_y,
            # Deliberately stale metadata: captured B3-Motion must follow
            # geometry rather than this old row.
            style=SimpleNamespace(meta={'row': start}),
            stop=Mock(),
        )
        # MouseMove only publishes the newest pointer sample. Selection work
        # is intentionally coalesced into the persistent drag-controller tick
        # so high-rate B3-Motion bursts cannot starve timers/repaints.
        with patch.object(
            table,
            '_toggle_drag_range_to',
            wraps=table._toggle_drag_range_to,
        ) as toggle_range:
            for _ in range(25):
                await table.on_mouse_move(event)
            toggle_range.assert_not_called()

        self.assertEqual(table._right_drag_last_row, start)
        self.assertEqual(table._right_drag_pointer_x, local_x)
        self.assertEqual(table._right_drag_pointer_y, local_y)

        with patch.object(
            table,
            '_sample_native_right_drag_pointer',
            return_value=(local_x, local_y, True),
        ):
            table._right_drag_auto_scroll_tick()

        self.assertEqual(table._right_drag_last_row, target)
        self.assertIn(pane.entries[target], pane.marked)

        table._update_right_drag_auto_scroll(int(table.size.height) - 1)
        near_step = table._right_drag_scroll_step
        table._update_right_drag_auto_scroll(int(table.size.height) + 18)
        far_step = table._right_drag_scroll_step
        self.assertEqual(table._right_drag_scroll_direction, 1)
        self.assertGreater(far_step, near_step)

        table.end_right_drag()

    async def test_list_right_drag_batches_crossed_rows(self):
        pane = self.app.left
        entries = [
            CachedEntry(
                pane.current_path / f'drag-{i:03}.txt',
                False,
                i,
                0,
            )
            for i in range(100)
        ]
        pane._apply_scanned_entries(entries, pane.current_path)
        pane._render_cached_rows()
        table = pane.table
        start = pane.row_by_path[entries[5].path]
        end = pane.row_by_path[entries[35].path]
        table._drag_rows_seen.clear()
        table._right_drag_last_row = None

        with patch.object(
            pane,
            'toggle_mark_paths',
            wraps=pane.toggle_mark_paths,
        ) as batch_toggle:
            table._toggle_drag_range_to(start)
            batch_toggle.reset_mock()
            table._toggle_drag_range_to(end)
            batch_toggle.assert_called_once()
            toggled = tuple(batch_toggle.call_args.args[0])
            self.assertEqual(len(toggled), end - start)

        expected = {
            path
            for path in pane.entries[start : end + 1]
            if path is not None
        }
        self.assertEqual(pane.marked, expected)
