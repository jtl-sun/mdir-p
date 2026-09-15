import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from textual.widgets import Input
from mdir.app import MDirApp
from mdir.preview.hotkey import PreviewHotkey, PreviewKeyState
from mdir.keyboard import NativeShortcuts, NativeShortcut


class PreviewDialogTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.path = self.root / 'original.txt'
        self.path.write_text('preview test')
        self.config = patch('mdir.core.load_config_data', return_value={})
        self.keys = patch('mdir.app.load_keymap', return_value={})
        self.config.start(); self.keys.start()
        self.app = MDirApp()
        self.app.left_start = self.app.right_start = self.root
        self.app._save_paths = lambda: None
        self.app._native_preview = Mock()
        self.app._native_preview.show.return_value = True
        self.context = self.app.run_test(size=(120, 38))
        self.pilot = await self.context.__aenter__()
        await self.wait_for(lambda: self.app.left.initial_listing_complete)
        self.app.left.table.move_cursor(row=self.app.left.row_by_path[self.path])
        self.app.set_active('left')
        await self.pilot.pause()

    async def asyncTearDown(self):
        await self.context.__aexit__(None, None, None)
        self.keys.stop(); self.config.stop(); self.temp.cleanup()

    async def wait_for(self, predicate):
        for _ in range(100):
            if predicate(): return
            await self.pilot.pause(.02)
        self.assertTrue(predicate())

    async def test_rename_cancel_hides_preview_and_preserves_input_focus(self):
        app = self.app
        await self.pilot.press('ctrl+f3')
        for _ in range(3):
            await self.pilot.press('f2')
            self.assertEqual(len(app.screen_stack), 2)
            app._native_preview.suspend.assert_called_with(wait=True)
            shown = app._native_preview.show.call_count
            await self.pilot.pause(.3)
            self.assertIsInstance(app.focused, Input)
            app._preview_current_left_selection()
            self.assertEqual(app._native_preview.show.call_count, shown)
            await self.pilot.press('ctrl+f3')
            self.assertTrue(app.preview_enabled)
            self.assertIsInstance(app.focused, Input)
            await self.pilot.press('escape')
            await self.wait_for(lambda: not app._preview_modal_suspended)
            self.assertTrue(app.preview_enabled)
            self.assertTrue(app.preview_mode)
            self.assertIs(app.focused, app.left.table)
        self.assertEqual(app._native_preview.resume.call_count, 3)
        self.assertTrue(self.path.exists())
        await self.pilot.press('ctrl+f3')
        self.assertFalse(app.preview_enabled)
        await self.pilot.press('ctrl+f3')
        self.assertTrue(app.preview_enabled)

    async def test_confirm_rename_previews_new_path(self):
        await self.pilot.press('ctrl+f3', 'f2')
        field = self.app.screen.query_one(Input)
        field.value = 'renamed.txt'
        await self.pilot.press('enter')
        target = self.root / 'renamed.txt'
        await self.wait_for(lambda: target.exists() and self.app._preview_path == target)
        self.assertFalse(self.path.exists())
        self.assertFalse(self.app._preview_modal_suspended)

    async def test_nested_option_screens_resume_only_after_last_dialog(self):
        app = self.app
        await self.pilot.press('ctrl+f3', 'f10')
        app.push_screen(app.PROMPT_SCREEN('Nested:', 'value'))
        await self.pilot.pause()
        self.assertEqual(len(app.screen_stack), 3)
        await self.pilot.press('escape')
        self.assertEqual(len(app.screen_stack), 2)
        self.assertTrue(app._preview_modal_suspended)
        app._native_preview.resume.assert_not_called()
        await self.pilot.press('escape')
        await self.wait_for(lambda: not app._preview_modal_suspended)
        app._native_preview.resume.assert_called_once()

    async def test_each_native_press_toggles_once_and_consumes_terminal_duplicate(self):
        app = self.app
        app._shortcut_keyboard = NativeShortcuts(1, lambda *args: None)
        app._shortcut_context = None
        app._sync_shortcut_keyboard()
        state = app._shortcut_keyboard.matcher
        state.feed(0xA2, True, True)
        for index in range(8):
            capture = state.feed(0x72, True, True)
            self.assertTrue(capture.consume)
            self.assertIsNone(state.feed(0x72, True, True).key)
            app.post_message(NativeShortcut(capture.key, capture.epoch))
            state.feed(0x72, False, True)
            await self.pilot.pause()
            self.assertEqual(app.preview_enabled, index % 2 == 0)
        self.assertFalse(app.preview_enabled)

    async def test_custom_shortcut_and_mouse_action_do_not_use_native_binding(self):
        app = self.app
        app.user_keymap = {'mdir.preview': 'ctrl+alt+p'}
        app.set_keymap(app.user_keymap)
        app.post_message(NativeShortcut('ctrl+f3', app._shortcut_epoch))
        await self.pilot.press('ctrl+f3')
        self.assertFalse(app.preview_enabled)
        await self.pilot.press('ctrl+alt+p')
        self.assertTrue(app.preview_enabled)
        await self.pilot.press('ctrl+alt+p')
        self.assertFalse(app.preview_enabled)
        # Direct actions are shared by footer clicks and configured links.
        app.action_toggle_preview(); app.action_toggle_preview()
        self.assertFalse(app.preview_enabled)

    async def test_footer_mouse_clicks_work_with_native_keyboard_observer(self):
        app = self.app
        app._shortcut_keyboard = NativeShortcuts(1, lambda *args: None)
        await self.pilot.resize_terminal(200, 38)
        await self.pilot.pause()
        for index in range(4):
            footer_key = next(key for key in app.query('FooterKey') if key.key == 'ctrl+f3')
            self.assertTrue(await self.pilot.click(footer_key))
            self.assertEqual(app.preview_enabled, index % 2 == 0)
            await self.pilot.pause(0.35)


class PreviewHotkeyTests(unittest.TestCase):
    def test_modifier_transitions_require_exact_ctrl_f3(self):
        state = PreviewKeyState()
        state.observe(0xA2, True, True)
        self.assertTrue(state.observe(0x72, True, True))
        state.observe(0x72, False, True)
        state.observe(0xA0, True, True)
        self.assertFalse(state.observe(0x72, True, True))
        state.observe(0x72, False, True)
        state.observe(0xA0, False, True)
        self.assertTrue(state.observe(0x72, True, True))
        state.observe(0x72, False, True)
        state.observe(0xA2, False, True)
        self.assertFalse(state.observe(0x72, True, True))

    def test_short_presses_hold_repeat_and_other_apps(self):
        state = PreviewKeyState()
        for _ in range(20):
            self.assertTrue(state.update(0x72, True, True, True))
            self.assertFalse(state.update(0x72, True, True, True))
            self.assertFalse(state.update(0x72, False, True, True))
        self.assertFalse(state.update(0x72, True, True, False))
        self.assertFalse(state.update(0x72, False, True, False))
        self.assertFalse(state.update(0x72, True, False, True))
        self.assertFalse(state.update(0x41, True, True, True))

    @unittest.skipUnless(os.name == 'nt', 'Windows observer')
    def test_native_observer_starts_and_releases_its_thread(self):
        monitor = PreviewHotkey(1, lambda: None)
        try:
            self.assertTrue(monitor.start(), monitor.error)
        finally:
            self.assertTrue(monitor.shutdown())
        self.assertFalse(monitor.active)

