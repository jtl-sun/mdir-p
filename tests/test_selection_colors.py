import os
import unittest
from unittest.mock import patch
from rich.style import Style
from textual.coordinate import Coordinate
from mdir.selection_style import MARK_BACKGROUND, MARK_FOREGROUND, MARK_PREFIX, CURSOR_BACKGROUND
import test_bulk_selection as bulk


class SelectionColorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.env = patch.dict(os.environ)
        self.env.start()
        os.environ.pop('NO_COLOR', None)
        self.fixture = bulk.BulkSelectionTests('test_select_invert_clear_are_independent_and_exclude_parent_and_hidden')
        await self.fixture.asyncSetUp()
        self.app, self.pilot = self.fixture.app, self.fixture.pilot

    async def asyncTearDown(self):
        await self.fixture.asyncTearDown()
        self.env.stop()

    def row_backgrounds(self, pane, row):
        y = pane.table.header_height + row - int(pane.table.scroll_y)
        return {s.style.bgcolor.get_truecolor().hex for s in pane.table.render_line(y)
                if s.style and s.style.bgcolor}

    async def test_marked_rows_cursor_hover_and_clear_render_in_both_panes(self):
        for side in ('left', 'right'):
            pane = self.app.left if side == 'left' else self.app.right
            folder = pane.current_path / 'folder'
            row = pane.row_by_path[folder]
            original = pane.table.get_cell_at(Coordinate(row, 0)).get_style_at_offset(self.app.console, 0).color
            await self.fixture.click(side, 'all')
            self.assertIn(MARK_BACKGROUND, self.row_backgrounds(pane, row))
            text = pane.table.get_cell_at(Coordinate(row, 0))
            self.assertTrue(text.plain.startswith(MARK_PREFIX))
            self.assertEqual(text.get_style_at_offset(self.app.console, 0).color.get_truecolor().hex, MARK_FOREGROUND)
            await self.pilot.hover(pane.table, offset=(5, pane.table.header_height + row))
            self.assertIn(MARK_BACKGROUND, self.row_backgrounds(pane, row))
            pane.table.move_cursor(row=row)
            await self.pilot.pause()
            self.assertIn(CURSOR_BACKGROUND, self.row_backgrounds(pane, row))
            await self.fixture.click(side, 'none')
            pane.table.move_cursor(row=0)
            await self.pilot.pause()
            self.assertNotIn(MARK_BACKGROUND, self.row_backgrounds(pane, row))
            text = pane.table.get_cell_at(Coordinate(row, 0))
            self.assertFalse(text.plain.startswith(MARK_PREFIX))
            self.assertEqual(text.get_style_at_offset(self.app.console, 0).color, original)

    async def test_render_preserves_mouse_cell_metadata(self):
        pane = self.app.left
        await self.fixture.click('left', 'all')
        row = pane.row_by_path[pane.current_path / 'notes.txt']
        cells = pane.table._render_cell(row, 0, pane.table._get_row_style(row, Style()), 30)
        self.assertTrue(any(segment.style and segment.style.meta.get('row') == row
                            for line in cells for segment in line))


@unittest.skipUnless(os.name == 'nt', 'Windows thumbnail canvas')
class ThumbnailSelectionColorTests(unittest.TestCase):
    def test_image_badges_folder_colors_and_unmark_on_real_canvas(self):
        import tkinter as tk
        from pathlib import Path
        from collections import OrderedDict
        from types import SimpleNamespace
        from PIL import Image, ImageTk
        from mdir.thumbnail_native import ThumbnailWindow, PaneState
        from mdir.thumbnail import ThumbnailItem
        from mdir.preview.native import PaneLayout
        from mdir.selection_style import MARK_BORDER
        from dataclasses import replace
        root = tk.Tk(); root.withdraw()
        items = (ThumbnailItem(Path('plain'), 'plain', True),
                 ThumbnailItem(Path('chosen'), 'chosen', True),
                 ThumbnailItem(Path('photo.png'), 'photo.png', False))
        bitmap = Image.new('RGB', (100, 100), 'red')
        memory = OrderedDict([(items[2].request_key(144), bitmap)])
        window = ThumbnailWindow(root, SimpleNamespace(terminal_hwnd=0, emit=lambda *a: None),
                                 'left', SimpleNamespace(request=lambda *a: None), memory, ImageTk)
        state = PaneState('left', Path('.'), ('folder', 1, 1, 3, True), items, 2,
                          frozenset({Path('chosen'), Path('photo.png')}), 144, True,
                          PaneLayout(0, 0, 80, 30, 160, 30),
                          ('#202020', '#dddddd', '#7894a8', '#e0bd62'))
        try:
            window.update_state(state); window.columns = 3
            window.canvas.yview_moveto(0)
            with patch.object(window.canvas, 'winfo_height', return_value=240):
                window.dirty = True; window.draw()
                canvas = window.canvas
                texts = [(canvas.itemcget(i, 'text'), canvas.itemcget(i, 'fill'))
                         for i in canvas.find_all() if canvas.type(i) == 'text']
                self.assertEqual(texts.count(('✓', MARK_FOREGROUND)), 2)
                self.assertIn(('DIR', '#e0bd62'), texts)
                self.assertIn(('DIR', MARK_FOREGROUND), texts)
                self.assertTrue(any(canvas.type(i) == 'image' for i in canvas.find_all()))
                image_index = max(i for i in canvas.find_all() if canvas.type(i) == 'image')
                self.assertTrue(any(i > image_index and canvas.type(i) == 'rectangle'
                                    and canvas.itemcget(i, 'outline') == MARK_BORDER
                                    for i in canvas.find_all()))
                self.assertTrue(any(canvas.type(i) == 'rectangle' and canvas.itemcget(i, 'outline') == MARK_BORDER
                                    for i in canvas.find_all()))
                window.update_state(replace(state, marked=frozenset()))
                window.draw()
                self.assertFalse(any(canvas.type(i) == 'text' and canvas.itemcget(i, 'text').startswith('✓')
                                     for i in canvas.find_all()))
        finally:
            window.destroy(); root.destroy(); bitmap.close()
