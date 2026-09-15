from __future__ import annotations

import os
import unittest
from collections import OrderedDict
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import ImageTk
from mdir.preview.native import PaneLayout, WindowRectangle
from mdir.thumbnail import ThumbnailItem
from mdir.thumbnail_native import PaneState, ThumbnailWindow, ThumbnailEvent
import test_thumbnail as thumbnail


@unittest.skipUnless(os.name == 'nt', 'Windows thumbnail canvas')
class ThumbnailDragNativeTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        self.root = tk.Tk()
        self.root.withdraw()
        self.events = []
        self.window = ThumbnailWindow(self.root, SimpleNamespace(terminal_hwnd=0, emit=self.events.append),
                                      'left', SimpleNamespace(request=lambda *a: None), OrderedDict(), ImageTk)
        items = (ThumbnailItem(None, '..', True),) + tuple(
            ThumbnailItem(Path(f'{i}.txt'), f'{i}.txt', False) for i in range(99))
        self.state = PaneState('left', Path('.'), ('folder', 1, 1, 100, True), items,
                              0, frozenset({Path('2.txt')}), 144, True,
                              PaneLayout(0, 0, 50, 30, 100, 30),
                              ('#202020', '#dddddd', '#7894a8', '#f1cd69'))
        self.window.update_state(self.state)
        self.window.show_at(WindowRectangle(-12000, -12000, -11300, -11450))
        self.root.update()
        self.window.canvas.yview_moveto(0)
        self.events.clear()
        self.button_patch = patch.object(self.window, '_right_button_down', return_value=True)
        self.button = self.button_patch.start()

    def tearDown(self):
        self.button_patch.stop()
        self.window.destroy()
        self.root.destroy()

    def event(self, name, x, y):
        self.window.canvas.event_generate(name, x=x, y=y)
        self.root.update()

    def marks(self):
        return [i for e in self.events if e.action == 'mark_drag' for i in e.value]

    def test_actual_bindings_fast_motion_reverse_and_new_gesture(self):
        for side in ('left', 'right'):
            with self.subTest(side=side):
                self.window.side = side
                self.events.clear()
                self.event('<ButtonPress-3>', 180, 50)
                self.event('<B3-Motion>', 510, 250)  # index 7: fast motion skips events
                self.event('<B3-Motion>', 180, 50)   # revisiting never toggles twice
                self.event('<ButtonRelease-3>', 180, 50)
                self.assertEqual(self.marks(), list(range(1, 8)))
                self.assertTrue(all(e.side == side for e in self.events if e.action == 'mark_drag'))
                self.assertIsNone(self.window._right_drag_timer)
                self.event('<B3-Motion>', 510, 250)
                self.assertEqual(self.marks(), list(range(1, 8)))
                self.event('<ButtonPress-3>', 180, 50)
                self.event('<ButtonRelease-3>', 180, 50)
                self.assertEqual(self.marks(), list(range(1, 8)) + [1])

    def test_edge_scroll_continues_and_release_outside_stops(self):
        w = self.window
        self.event('<ButtonPress-3>', 180, 50)
        self.event('<B3-Motion>', 510, w.canvas.winfo_height() + 40)
        for _ in range(10):
            w.canvas.after_cancel(w._right_drag_timer)
            w._right_drag_tick()
        self.assertGreater(w.canvas.canvasy(0), 0)
        marked = self.marks()
        self.assertGreater(max(marked), 11)
        self.assertEqual(marked, list(range(1, max(marked) + 1)))
        top = w.canvas.canvasy(0)
        w.update_state(replace(self.state, current=1))
        self.assertEqual(w.canvas.canvasy(0), top)  # stale cursor cannot snap view back
        self.event('<ButtonRelease-3>', -40, -40)
        self.assertIsNone(w._right_drag_timer)
        self.assertIsNone(w._right_drag_pointer)

    def test_top_edge_scroll_and_missing_release(self):
        w = self.window
        w.canvas.yview_moveto(0.4)
        before = w.canvas.canvasy(0)
        self.event('<ButtonPress-3>', 180, 250)
        self.event('<B3-Motion>', 180, -30)
        for _ in range(4):
            w.canvas.after_cancel(w._right_drag_timer)
            w._right_drag_tick()
        self.assertLess(w.canvas.canvasy(0), before)
        self.button.return_value = False
        w.canvas.after_cancel(w._right_drag_timer)
        w._right_drag_tick()
        self.assertIsNone(w._right_drag_pointer)
        self.assertIsNone(w._right_drag_timer)

    def test_revision_modal_hide_resize_and_destroy_cancel(self):
        w = self.window
        changes = [lambda: w.update_state(replace(w.state, revision=('new', 2, 1, 100, True))),
                   lambda: w.update_state(replace(w.state, suspended=True)),
                   w.hide, lambda: w.resized(None)]
        for change in changes:
            w.update_state(replace(self.state, suspended=False))
            w.canvas.yview_moveto(0)
            w.right_drag_start(SimpleNamespace(x=180, y=50))
            self.assertIsNotNone(w._right_drag_timer)
            change()
            count = len(self.marks())
            w.right_drag_move(SimpleNamespace(x=510, y=250))
            self.assertEqual(len(self.marks()), count)
            self.assertIsNone(w._right_drag_timer)
        w.right_drag_start(SimpleNamespace(x=180, y=50))  # tearDown must cancel timer

    def test_empty_and_outside_start_do_not_select(self):
        w = self.window
        for x, y in [(-1, 50), (800, 50), (10, -10), (10, 800)]:
            w.right_drag_start(SimpleNamespace(x=x, y=y))
            self.assertIsNone(w._right_drag_timer)
        w.update_state(replace(self.state, items=(), revision=('empty', 1, 1, 0, True)))
        w.right_drag_start(SimpleNamespace(x=10, y=50))
        self.assertFalse(self.marks())


class ThumbnailDragAppTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fixture = thumbnail.ThumbnailAppTests('test_mouse_selection_mark_stale_click_and_folder')
        await self.fixture.asyncSetUp()
        self.app, self.pilot = self.fixture.app, self.fixture.pilot
        await self.fixture.enable_both()

    async def asyncTearDown(self):
        await self.fixture.asyncTearDown()

    @unittest.skipUnless(os.name == 'nt', 'Windows thumbnail canvas')
    async def test_real_canvas_gestures_update_both_panes_and_list_marks(self):
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        app = self.app
        try:
            for side in ('left', 'right'):
                pane = app.left if side == 'left' else app.right
                other = app.right if side == 'left' else app.left
                before_other = set(other.marked)
                pane.toggle_mark_path(pane.entries[3])
                app._sync_thumbnails()
                emitted = []
                window = ThumbnailWindow(root, SimpleNamespace(terminal_hwnd=0, emit=emitted.append),
                                         side, SimpleNamespace(request=lambda *a: None), OrderedDict(), ImageTk)
                try:
                    window.update_state(app._thumbnail_manager.states[side])
                    window.show_at(WindowRectangle(-12000, -12000, -11300, -11450))
                    root.update()
                    window.canvas.yview_moveto(0)
                    with patch.object(window, '_right_button_down', return_value=True):
                        for name, x, y in [('<ButtonPress-3>', 10, 50), ('<B3-Motion>', 510, 250),
                                           ('<B3-Motion>', 180, 50), ('<ButtonRelease-3>', 180, 50)]:
                            window.canvas.event_generate(name, x=x, y=y)
                            root.update()
                    # Deliver queued events without repairing native selection snapshots.
                    for event in emitted:
                        app.post_message(event)
                    expected = set(pane.entries[1:8]) - {pane.entries[3]}
                    await self.fixture.wait_for(lambda: pane.marked == expected)
                    self.assertEqual(other.marked, before_other)
                    self.assertEqual(app.active_side, side)
                    self.assertEqual(pane.table.cursor_row, 1)
                    self.assertNotIn(None, pane.marked)
                    self.assertEqual(set(pane.selected_items()), expected)
                    self.assertEqual(app._thumbnail_manager.states[side].marked, frozenset(expected))
                    app._toggle_thumbnail(side)
                    self.assertEqual(pane.marked, expected)
                finally:
                    window.destroy()
        finally:
            root.destroy()

    async def test_stale_disabled_and_modal_batches_are_ignored(self):
        app = self.app
        pane = app.left
        revision = app._thumbnail_revision(pane)
        async def emit(rev=revision):
            await app.on_thumbnail_event(ThumbnailEvent('left', 'mark_drag', revision=rev, index=3, value=(0, 1, 2, 3)))
        await emit(('stale',))
        self.assertFalse(pane.marked)
        app.action_options()
        await self.pilot.pause()
        await emit()
        self.assertFalse(pane.marked)
        await self.pilot.press('escape')
        app.thumbnail_modes['left'] = False
        await emit()
        self.assertFalse(pane.marked)
