from __future__ import annotations

import ctypes
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from textual.widgets import Button

from mdir.app import MDirApp
from mdir import core
from mdir.thumbnail_native import ThumbnailEvent, ThumbnailManager
from mdir.advanced import Workspace, WorkspaceStore
from test_thumbnail import FakeManager


class PaneButtonTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for side in ('left', 'right'):
            folder = self.root / side
            folder.mkdir()
            (folder / 'normal.txt').write_text('normal')
            hidden = folder / '.secret.txt'
            hidden.write_text('hidden')
            if os.name == 'nt':
                self.assertTrue(ctypes.windll.kernel32.SetFileAttributesW(str(hidden), 2))
        self.config_patch = patch('mdir.core.load_config_data', return_value={})
        self.config_patch.start()
        self.manager_patch = patch('mdir.thumbnail_app.ThumbnailManager', FakeManager)
        self.manager_patch.start()
        self.app = MDirApp()
        self.app.left_start = self.root / 'left'
        self.app.right_start = self.root / 'right'
        self.app._save_paths = lambda: None
        self.context = self.app.run_test(size=(120, 38))
        self.pilot = await self.context.__aenter__()
        await self.ready()

    async def asyncTearDown(self):
        await self.context.__aexit__(None, None, None)
        self.manager_patch.stop()
        self.config_patch.stop()
        self.temp.cleanup()

    async def ready(self):
        for _ in range(150):
            if self.app.left.initial_listing_complete and self.app.right.initial_listing_complete:
                return
            await self.pilot.pause(0.02)
        self.fail('Listing did not finish')

    async def test_th_buttons_reach_handler_and_toggle_independently(self):
        app = self.app
        self.assertTrue(await self.pilot.click('#left_thumbnail'))
        self.assertEqual(app.thumbnail_modes, {'left': True, 'right': False})
        self.assertTrue(await self.pilot.click('#right_thumbnail'))
        self.assertEqual(app.thumbnail_modes, {'left': True, 'right': True})
        self.assertEqual(app.active_side, 'right')
        self.assertIs(app.focused, app.right.table)
        self.assertTrue(await self.pilot.click('#right_thumbnail'))
        self.assertEqual(app.thumbnail_modes, {'left': True, 'right': False})
        self.assertTrue(app.query_one('#left_thumbnail', Button).has_class('thumbnail-on'))
        self.assertFalse(app.query_one('#right_thumbnail', Button).has_class('thumbnail-on'))

    async def test_hidden_buttons_change_only_clicked_pane(self):
        app = self.app
        right_generation = app.right._listing_generation
        self.assertTrue(await self.pilot.click('#left_hidden_toggle'))
        await self.ready()
        self.assertTrue(app.left.show_hidden_system)
        self.assertFalse(app.right.show_hidden_system)
        self.assertEqual(app.right._listing_generation, right_generation)
        self.assertIn(self.root / 'left/.secret.txt', app.left.entries)
        self.assertNotIn(self.root / 'right/.secret.txt', app.right.entries)
        self.assertIs(app.focused, app.left.table)
        self.assertTrue(await self.pilot.click('#right_hidden_toggle'))
        await self.ready()
        self.assertTrue(app.left.show_hidden_system)
        self.assertTrue(app.right.show_hidden_system)
        self.assertIn(self.root / 'right/.secret.txt', app.right.entries)
        self.assertTrue(await self.pilot.click('#left_hidden_toggle'))
        await self.ready()
        self.assertFalse(app.left.show_hidden_system)
        self.assertTrue(app.right.show_hidden_system)
        self.assertFalse(app.query_one('#left_hidden_toggle', Button).has_class('showing-hidden'))
        self.assertTrue(app.query_one('#right_hidden_toggle', Button).has_class('showing-hidden'))

    async def test_hidden_shortcut_targets_active_pane_after_button_click(self):
        await self.pilot.click('#left_hidden_toggle')
        await self.ready()
        await self.pilot.press('tab', 'ctrl+h')
        await self.ready()
        self.assertEqual(self.app.active_side, 'right')
        self.assertTrue(self.app.left.show_hidden_system)
        self.assertTrue(self.app.right.show_hidden_system)
        await self.pilot.press('ctrl+h')
        await self.ready()
        self.assertTrue(self.app.left.show_hidden_system)
        self.assertFalse(self.app.right.show_hidden_system)

    async def test_native_messages_after_button_activation_use_real_queue(self):
        app = self.app
        await self.pilot.click('#left_thumbnail')
        path = self.root / 'left/normal.txt'
        app.post_message(ThumbnailEvent('left', 'mark', revision=app._thumbnail_revision(app.left),
                                        index=app.left.row_by_path[path]))
        await self.pilot.pause()
        self.assertEqual(app.left.marked, {path})
        app.post_message(ThumbnailEvent('left', 'close', revision=app._thumbnail_revision(app.left)))
        await self.pilot.pause()
        self.assertFalse(app.thumbnail_modes['left'])

    async def test_hidden_settings_persist_separately_and_migrate_legacy(self):
        app = self.app
        await self.pilot.click('#right_hidden_toggle')
        await self.ready()
        config = self.root / 'config.json'
        with patch.object(core, 'CONFIG_PATH', config):
            core.MDir._save_paths(app)
        saved = json.loads(config.read_text(encoding='utf-8'))
        self.assertEqual(saved['show_hidden_system_by_pane'], {'left': False, 'right': True})
        with patch('mdir.core.load_config_data', return_value=saved):
            restored = MDirApp()
        self.assertEqual(restored._initial_hidden_system, {'left': False, 'right': True})
        with patch('mdir.core.load_config_data', return_value={'show_hidden_system': True}):
            legacy = MDirApp()
        self.assertEqual(legacy._initial_hidden_system, {'left': True, 'right': True})

    async def test_workspace_roundtrip_keeps_different_hidden_states(self):
        app = self.app
        app._workspace_store = WorkspaceStore(self.root / 'workspaces.json')
        await self.pilot.click('#left_hidden_toggle')
        await self.ready()
        app.action_save_workspace()
        await self.pilot.pause()
        app.screen.query_one('#compact_input').value = 'independent'
        await self.pilot.press('enter')
        saved = app._workspace_store.get('independent')
        self.assertTrue(saved.left_show_hidden)
        self.assertFalse(saved.right_show_hidden)
        await self.pilot.click('#left_hidden_toggle')
        await self.pilot.click('#right_hidden_toggle')
        await self.ready()
        app.action_load_workspace()
        await self.pilot.pause()
        await self.pilot.press('enter')
        await self.ready()
        self.assertTrue(app.left.show_hidden_system)
        self.assertFalse(app.right.show_hidden_system)
        # Old saved workspaces retain their previous global visibility semantics.
        legacy = Workspace('legacy', str(self.root / 'left'), str(self.root / 'right'), show_hidden=True)
        app._workspace_store.save(legacy)
        app.action_load_workspace()
        await self.pilot.pause()
        app.screen.query_one('#compact_input').value = 'legacy'
        await self.pilot.press('enter')
        await self.ready()
        self.assertTrue(app.left.show_hidden_system)
        self.assertTrue(app.right.show_hidden_system)

    async def test_hidden_search_result_does_not_enable_other_pane(self):
        app = self.app
        self.assertTrue(app._reveal_search_result(self.root / 'right/.secret.txt', 'right'))
        await self.ready()
        self.assertFalse(app.left.show_hidden_system)
        self.assertTrue(app.right.show_hidden_system)
        self.assertEqual(app.right.selected_path(), self.root / 'right/.secret.txt')
        self.assertNotIn(self.root / 'left/.secret.txt', app.left.entries)

    async def test_hidden_button_updates_thumbnail_items_only_on_its_side(self):
        app = self.app
        await self.pilot.click('#left_thumbnail')
        await self.pilot.click('#right_thumbnail')
        app._sync_thumbnails()
        previous_right = app._thumbnail_manager.states['right'].items
        await self.pilot.click('#left_hidden_toggle')
        await self.ready()
        app._sync_thumbnails()
        self.assertEqual(app.thumbnail_modes, {'left': True, 'right': True})
        self.assertIs(app._thumbnail_manager.states['right'].items, previous_right)
        self.assertIn(self.root / 'left/.secret.txt', [item.path for item in app._thumbnail_manager.states['left'].items])
        self.assertNotIn(self.root / 'right/.secret.txt', [item.path for item in app._thumbnail_manager.states['right'].items])

    @unittest.skipUnless(os.name == 'nt', 'Windows native integration')
    async def test_th_button_starts_real_tk_manager_and_keeps_keyboard_focus(self):
        app = self.app
        # An invalid host keeps windows hidden while exercising the real Tk thread
        # and post_message path, without targeting the user's foreground app.
        app._terminal_window_handle = 1
        with patch('mdir.thumbnail_app.ThumbnailManager', ThumbnailManager):
            await self.pilot.click('#left_thumbnail')
            await self.pilot.click('#right_thumbnail')
            for _ in range(100):
                if app._thumbnail_geometry == {'left': (1, 1), 'right': (1, 1)}:
                    break
                await self.pilot.pause(0.02)
            self.assertFalse(app._thumbnail_manager.error)
            self.assertTrue(app._thumbnail_manager.thread.is_alive())
            self.assertEqual(app._thumbnail_geometry, {'left': (1, 1), 'right': (1, 1)})
            self.assertEqual(app.thumbnail_modes, {'left': True, 'right': True})
            self.assertIs(app.focused, app.right.table)
            await self.pilot.press('alt+t')
            self.assertEqual(app.thumbnail_modes, {'left': True, 'right': False})
            await self.pilot.press('tab', 'alt+t')
            self.assertEqual(app.thumbnail_modes, {'left': False, 'right': False})
            self.assertTrue(app._thumbnail_manager.shutdown())
            self.assertFalse(any(t.is_alive() and t.name.startswith('mdir-thumbnail-') for t in threading.enumerate()))
