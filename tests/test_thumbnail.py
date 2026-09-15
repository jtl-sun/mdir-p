from __future__ import annotations

import asyncio
import ctypes
from ctypes import wintypes
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image

from mdir import __version__
from mdir.app import MDirApp
from mdir.preview.native import PaneLayout, WindowRectangle
from mdir.thumbnail import (MAX_PENDING, VERSION, ThumbnailCache, ThumbnailItem,
                            ThumbnailLoader, grid_columns, navigate, visible_indices)
from mdir.thumbnail_native import PaneState, ThumbnailEvent, ThumbnailManager, ThumbnailWindow, should_show


class ThumbnailDataTests(unittest.TestCase):
    def test_grid_navigation_and_virtualization(self):
        self.assertEqual(grid_columns(700, 144), 4)
        self.assertEqual(navigate(8, 50, 4, 'up'), 4)
        self.assertEqual(navigate(8, 50, 4, 'down'), 12)
        self.assertEqual(navigate(0, 50, 4, 'left'), 0)
        self.assertEqual(navigate(49, 50, 4, 'right'), 49)
        self.assertEqual(navigate(0, 0, 4, 'end'), 0)
        self.assertLess(len(visible_indices(10000, 4, 0, 600, 144)), 30)
        self.assertGreater(visible_indices(10000, 4, 40000, 600, 144).start, 700)

    def test_cache_invalidation_size_orientation_and_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = ThumbnailCache(root / 'cache')
            path = root / 'photo.jpg'
            exif = Image.Exif()
            exif[274] = 6
            with Image.new('RGB', (240, 120), 'red') as source:
                source.save(path, exif=exif)
            old = cache.cache_path(path, 96)
            with cache.load(path, 96) as image:
                self.assertEqual(image.size, (48, 96))
            self.assertTrue(old.exists())
            self.assertNotEqual(old, cache.cache_path(path, 144))
            old.write_bytes(b'broken cache')
            with cache.load(path, 96) as image:
                self.assertEqual(image.size, (48, 96))
            with Image.new('RGB', (120, 120), 'blue') as source:
                source.save(path)
            self.assertNotEqual(old, cache.cache_path(path, 96))
            with cache.load(path, 96) as image:
                self.assertEqual(image.size, (96, 96))
                self.assertGreater(image.getpixel((0, 0))[2], 200)

    def test_cache_cleanup_evicts_oldest(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = ThumbnailCache(Path(directory), limit=15)
            for index in range(3):
                path = cache.root / f'{index}.png'
                path.write_bytes(b'x' * 10)
                os.utime(path, (100 + index, 100 + index))
            cache.cleanup(force=True)
            self.assertEqual([p.name for p in cache.root.iterdir()], ['2.png'])

    def test_loader_replaces_work_and_discards_stale_results(self):
        release = threading.Event()
        entered = threading.Event()
        def load(path, size):
            entered.set()
            release.wait(2)
            return Image.new('RGB', (8, 8))
        loader = ThumbnailLoader(SimpleNamespace(load=load))
        keys = [(Path(str(i)), 0, 0, 96) for i in range(10000)]
        try:
            loader.request('left', keys)
            self.assertTrue(entered.wait(1))
            loader.request('right', keys[100:])
            self.assertLessEqual(len(loader.pending), MAX_PENDING)
            loader.request('left', [])
            loader.request('right', [])
            release.set()
        finally:
            self.assertTrue(loader.shutdown())
        self.assertFalse(loader.results)

    def test_external_visibility_and_version(self):
        self.assertTrue(should_show(10, 10, False, False))
        for values in [(10, 11, False, False), (10, 10, True, False),
                       (10, 10, False, True), (0, 0, False, False)]:
            self.assertFalse(should_show(*values))
        self.assertEqual(VERSION, __version__)


class FakeManager:
    def __init__(self, *args):
        self.states = {}
        self.error = ''
        self.suspended = False
        self.closed = False

    def start(self):
        return True

    def publish(self, states):
        self.states = states

    def suspend_external(self):
        self.suspended = True

    def shutdown(self):
        self.closed = True
        return True


class ThumbnailAppTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.left = self.root / 'left'
        self.right = self.root / 'right'
        self.left.mkdir()
        self.right.mkdir()
        for index in range(20):
            (self.left / f'{index:02}.txt').write_text(f'file {index}')
            (self.right / f'{index:02}.txt').write_text(f'other {index}')
        (self.left / 'folder').mkdir()
        self.manager_patch = patch('mdir.thumbnail_app.ThumbnailManager', FakeManager)
        self.manager_patch.start()
        self.app = MDirApp()
        self.app.left_start, self.app.right_start = self.left, self.right
        self.app._save_paths = lambda: None
        self.context = self.app.run_test(size=(120, 38))
        self.pilot = await self.context.__aenter__()
        await self.wait_for(lambda: self.app.left.initial_listing_complete and self.app.right.initial_listing_complete)

    async def asyncTearDown(self):
        await self.context.__aexit__(None, None, None)
        self.manager_patch.stop()
        self.temporary.cleanup()

    async def wait_for(self, predicate):
        for _ in range(150):
            if predicate():
                return
            await self.pilot.pause(0.02)
        self.assertTrue(predicate())

    async def enable_both(self):
        await self.pilot.press('alt+t', 'tab', 'alt+t')
        self.assertEqual(self.app.thumbnail_modes, {'left': True, 'right': True})

    async def test_tab_arrow_space_and_independent_close(self):
        await self.pilot.press('alt+t')
        self.app._thumbnail_geometry['left'] = (4, 3)
        await self.pilot.press('down')
        self.assertEqual(self.app.left.table.cursor_row, 4)
        await self.pilot.press('space')
        self.assertTrue(self.app.left.marked)
        left_row = self.app.left.table.cursor_row
        await self.pilot.press('tab', 'down', 'right', 'left')
        self.assertEqual(self.app.active_side, 'right')
        self.assertEqual(self.app.right.table.cursor_row, 1)
        self.assertEqual(self.app.left.table.cursor_row, left_row)
        await self.pilot.press('alt+t')
        self.assertEqual(self.app.thumbnail_modes, {'left': True, 'right': True})
        await self.pilot.press('alt+t')
        self.assertEqual(self.app.thumbnail_modes, {'left': True, 'right': False})
        await self.pilot.press('tab', 'alt+t')
        self.assertTrue(self.app.left.marked)
        self.assertIsNone(self.app._thumbnail_timer)

    async def test_mouse_selection_mark_stale_click_and_folder(self):
        await self.enable_both()
        app = self.app
        rev = app._thumbnail_revision(app.left)
        row = app.left.row_by_path[self.left / '03.txt']
        await app.on_thumbnail_event(ThumbnailEvent('left', 'mark', revision=rev, index=row))
        self.assertEqual(app.active_side, 'left')
        self.assertEqual(app.left.selected_items(), [self.left / '03.txt'])
        await app.on_thumbnail_event(ThumbnailEvent('left', 'mark', revision=rev, index=row))
        self.assertFalse(app.left.marked)
        folder_row = app.left.row_by_path[self.left / 'folder']
        await app.on_thumbnail_event(ThumbnailEvent('left', 'open', revision=rev, index=folder_row))
        await self.wait_for(lambda: app.left.cached_path == self.left / 'folder')
        self.assertTrue(app.thumbnail_modes['left'])
        await app.on_thumbnail_event(ThumbnailEvent('left', 'mark', revision=rev, index=row))
        self.assertFalse(app.left.marked)

    async def test_copy_move_reuse_existing_dialogs_and_engine(self):
        await self.enable_both()
        app = self.app
        await self.pilot.press('tab')
        source = self.left / '03.txt'
        destination = self.right / source.name
        destination.unlink()  # Only test fixture; avoid an overwrite dialog for this test.
        rev = app._thumbnail_revision(app.left)
        await app.on_thumbnail_event(ThumbnailEvent('left', 'mark', revision=rev, index=app.left.row_by_path[source]))
        await self.pilot.press('f5')
        app._sync_thumbnails()
        self.assertTrue(all(s.suspended for s in app._thumbnail_manager.states.values()))
        await self.pilot.press('enter')
        await self.wait_for(lambda: destination.exists() and not app._file_operation_busy)
        self.assertEqual(destination.read_text(), source.read_text())
        self.assertTrue(source.exists())
        self.assertTrue(all(app.thumbnail_modes.values()))
        await self.wait_for(lambda: len(app.screen_stack) == 1)
        destination.unlink()
        app.left.marked.clear()
        app.left.toggle_mark_path(source)
        await self.pilot.press('f6', 'enter')
        await self.wait_for(lambda: not source.exists() and destination.exists() and not app._file_operation_busy)
        self.assertEqual(destination.read_text(), 'file 3')
        self.assertTrue(all(app.thumbnail_modes.values()))

    async def test_external_suspend_preserves_state_and_size(self):
        await self.enable_both()
        app = self.app
        rev = app._thumbnail_revision(app.right)
        await app.on_thumbnail_event(ThumbnailEvent('right', 'size', revision=rev, value=1))
        self.assertEqual(app.thumbnail_sizes['right'], 168)
        self.assertEqual(app.thumbnail_sizes['left'], 144)
        with patch('mdir.core.open_with_default_app'):
            app.open_external_path(self.right / '00.txt')
        self.assertTrue(app._thumbnail_manager.suspended)
        self.assertTrue(all(app.thumbnail_modes.values()))

    async def test_preview_reserves_right_pane_and_tab_restores_thumbnails(self):
        app = self.app
        app._native_preview = Mock()
        app._native_preview.show.return_value = True
        await self.enable_both()
        await self.pilot.press('tab')
        app.left.table.move_cursor(row=app.left.row_by_path[self.left / '03.txt'])
        app.left.toggle_mark_path(self.left / '03.txt')
        app.right.toggle_mark_path(self.right / '04.txt')
        await self.pilot.press('ctrl+f3')
        await self.wait_for(lambda: app.preview_mode)
        app._sync_thumbnails()
        self.assertFalse(app._thumbnail_manager.states['left'].suspended)
        self.assertTrue(app._thumbnail_manager.states['right'].suspended)
        row = app.left.row_by_path[self.left / '05.txt']
        app.post_message(ThumbnailEvent('left', 'select', index=row,
            revision=app._thumbnail_revision(app.left)))
        await self.wait_for(lambda: app._native_preview.show.call_args.args[0] == self.left / '05.txt')
        await self.pilot.press('tab')
        app._sync_thumbnails()
        self.assertFalse(app.preview_mode)
        self.assertFalse(app.right.disabled)
        self.assertEqual(app.active_side, 'right')
        self.assertFalse(app._thumbnail_manager.states['right'].suspended)
        self.assertEqual(app.left.marked, {self.left / '03.txt'})
        self.assertEqual(app.right.marked, {self.right / '04.txt'})

    async def test_preview_open_suspends_thumbnails_before_external_launch(self):
        app = self.app
        app._native_preview = Mock()
        app._native_preview.show.return_value = True
        await self.enable_both()
        await self.pilot.press('tab')
        app.left.table.move_cursor(row=app.left.row_by_path[self.left / '03.txt'])
        await self.pilot.press('ctrl+f3')
        await self.wait_for(lambda: app.preview_mode)
        path = self.left / '03.txt'
        def open_file(opened):
            self.assertEqual(opened, path)
            self.assertTrue(app._thumbnail_manager.suspended)
            self.assertFalse(app.preview_mode)
            app._native_preview.hide.assert_called_with(wait=True)
        with patch('mdir.core.open_with_default_app', side_effect=open_file) as opened:
            app._native_open_document(path)
            opened.assert_called_once_with(path)
        self.assertTrue(app._thumbnail_manager.suspended)
        self.assertEqual(app._preview_suppressed_path, path)
        self.assertTrue(all(app.thumbnail_modes.values()))

    async def test_dialog_keys_and_snapshot_identity(self):
        await self.enable_both()
        app = self.app
        app._sync_thumbnails()
        before = app._thumbnail_manager.states['left'].items
        app._sync_thumbnails()
        self.assertIs(before, app._thumbnail_manager.states['left'].items)
        app.action_options()
        await self.pilot.pause()
        app._sync_thumbnails()
        self.assertTrue(all(s.suspended for s in app._thumbnail_manager.states.values()))
        await self.pilot.press('right')
        self.assertEqual(app.focused.id, 'option_links')
        await self.pilot.press('escape')
        app._sync_thumbnails()
        self.assertTrue(all(not s.suspended for s in app._thumbnail_manager.states.values()))


@unittest.skipUnless(os.name == 'nt', 'Windows native windows')
class ThumbnailNativeTests(unittest.TestCase):
    def test_single_ui_thread_dual_window_shutdown(self):
        events = []
        manager = ThumbnailManager(SimpleNamespace(post_message=events.append), 1)
        state = PaneState('left', Path('.'), ('folder', 1, 1, 1, True),
                          (ThumbnailItem(None, '..', True),), 0, frozenset(), 144, True,
                          PaneLayout(0, 0, 50, 30, 100, 30),
                          ('#202020', '#dddddd', '#7894a8', '#f1cd69'), suspended=True)
        from dataclasses import replace
        try:
            self.assertTrue(manager.start())
            manager.publish({'left': state, 'right': replace(state, side='right')})
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline and {e.side for e in events if e.action == 'geometry'} != {'left', 'right'}:
                time.sleep(0.03)
            self.assertFalse(manager.error)
            self.assertEqual({e.side for e in events if e.action == 'geometry'}, {'left', 'right'})
            manager.publish({'left': state})
            time.sleep(0.2)
            self.assertFalse(manager.error)
        finally:
            self.assertTrue(manager.shutdown())
        self.assertFalse(any(t.name.startswith('mdir-thumbnail-') and t.is_alive() for t in threading.enumerate()))

    def test_native_mouse_noactivate_and_virtual_canvas(self):
        import tkinter as tk
        from PIL import ImageTk
        from collections import OrderedDict
        root = tk.Tk()
        root.withdraw()
        sent = []
        manager = SimpleNamespace(terminal_hwnd=0, emit=sent.append)
        loader = SimpleNamespace(request=Mock())
        window = ThumbnailWindow(root, manager, 'left', loader, OrderedDict(), ImageTk)
        items = tuple(ThumbnailItem(Path(f'{i}.png'), f'{i}.png', False) for i in range(10000))
        state = PaneState('left', Path('.'), ('folder', 1, 1, 10000, True), items,
                          0, frozenset({Path('0.png')}), 144, True,
                          PaneLayout(0, 0, 50, 30, 100, 30),
                          ('#202020', '#dddddd', '#7894a8', '#f1cd69'))
        try:
            window.update_state(state)
            with patch.object(window.canvas, 'winfo_width', return_value=660), patch.object(window.canvas, 'winfo_height', return_value=500):
                window.update_geometry()
                window.canvas.yview_moveto(0)
                window.draw()
                self.assertLess(len(window.canvas.find_all()), 120)
                self.assertLess(len(loader.request.call_args.args[1]), 30)
                window.click(SimpleNamespace(x=180, y=30), 'mark')
                self.assertEqual(sent[-1].index, 1)
                self.assertEqual(sent[-1].action, 'mark')
                window.wheel(SimpleNamespace(delta=-120))
                self.assertTrue(window.dirty)
            user32 = ctypes.windll.user32
            user32.SendMessageW.restype = ctypes.c_ssize_t
            self.assertEqual(user32.SendMessageW(ctypes.c_void_p(window.hwnd), 0x21, 0, 0), 3)
            style = user32.GetWindowLongW(ctypes.c_void_p(window.hwnd), -20)
            self.assertTrue(style & 0x08000000)
            self.assertFalse(style & 0x8)  # No TOPMOST.
        finally:
            window.destroy()
            root.destroy()
            del window, root
            import gc
            gc.collect()

    def test_offscreen_window_show_hide_preserves_foreground(self):
        import tkinter as tk
        from PIL import ImageTk
        from collections import OrderedDict
        root = tk.Tk()
        root.withdraw()
        manager = SimpleNamespace(terminal_hwnd=0, emit=lambda event: None)
        window = ThumbnailWindow(root, manager, 'left', SimpleNamespace(request=lambda *a: None), OrderedDict(), ImageTk)
        state = PaneState('left', Path('.'), ('folder', 1, 1, 100, True),
                          tuple(ThumbnailItem(Path(f'{i}.png'), f'{i}.png', False) for i in range(100)),
                          0, frozenset(), 144, True, PaneLayout(0, 0, 50, 30, 100, 30),
                          ('#202020', '#dddddd', '#7894a8', '#f1cd69'))
        user32 = ctypes.windll.user32
        user32.GetForegroundWindow.restype = ctypes.c_void_p
        foreground = user32.GetForegroundWindow()
        try:
            window.update_state(state)
            window.show_at(WindowRectangle(-12000, -12000, -11340, -11450))
            root.update()
            window.draw()
            self.assertEqual(window.canvas.winfo_width() // 164, window.columns)
            self.assertGreater(window.canvas.winfo_height(), 450)
            self.assertEqual(user32.GetForegroundWindow(), foreground)
            self.assertTrue(window.visible)
            self.assertTrue(window.window.winfo_ismapped())
            rectangle = wintypes.RECT()
            user32.GetWindowRect(ctypes.c_void_p(window.hwnd), ctypes.byref(rectangle))
            self.assertEqual((rectangle.left, rectangle.top), (-12000, -12000))
            window.wheel(SimpleNamespace(delta=-120))
            root.update()
            self.assertGreater(window.canvas.canvasy(0), 0)
            window.hide()
            root.update()
            self.assertFalse(window.window.winfo_ismapped())
            self.assertEqual(user32.GetForegroundWindow(), foreground)
        finally:
            window.destroy()
            root.destroy()
            del window, root
            import gc
            gc.collect()
