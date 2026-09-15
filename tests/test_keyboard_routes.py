import tempfile
import ctypes
import os
import unittest
from pathlib import Path
from unittest.mock import patch
from textual import events
from textual.widgets import DataTable, Input
from mdir.app import MDirApp
from mdir.keyboard import NativeShortcut, NativeShortcuts, ShortcutKeyState, key_signature, shortcut_routes
from mdir.keymap import KEY_DEFINITIONS, load_keymap, save_keymap, validate_keymap
from mdir.advanced import MacroStore, WorkspaceStore
from mdir.core import PropertiesScreen


class KeyboardRoutesTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        (self.root / 'item.txt').write_text('item')
        self.config = patch('mdir.core.load_config_data', return_value={})
        self.keys = patch('mdir.app.load_keymap', return_value={})
        self.config.start(); self.keys.start()
        self.app = MDirApp()
        self.app.left_start = self.app.right_start = self.root
        self.app._save_paths = lambda: None
        self.context = self.app.run_test(size=(140, 40))
        self.pilot = await self.context.__aenter__()
        await self.pilot.pause()
        self.app.set_active('left')
        await self.pilot.pause()

    async def asyncTearDown(self):
        await self.context.__aexit__(None, None, None)
        self.keys.stop(); self.config.stop(); self.temp.cleanup()

    def record_actions(self):
        calls = []
        for definition in KEY_DEFINITIONS:
            def action(*parameters, name=definition.action):
                calls.append((name, parameters))
            setattr(self.app, 'action_' + definition.action, action)
        return calls

    async def test_every_listed_default_key_reaches_exact_action_in_both_panes(self):
        calls = self.record_actions()
        for side in ('left', 'right'):
            self.app.set_active(side)
            await self.pilot.pause()
            for key, expected in shortcut_routes({}).items():
                calls.clear()
                await self.pilot.press(key)
                self.assertEqual(calls, [expected], (side, key))

    async def test_every_editable_key_can_be_remapped_without_old_binding(self):
        definitions = [d for d in KEY_DEFINITIONS if d.editable]
        overrides = {d.binding_id: f'ctrl+alt+{"shift+" if i >= 24 else ""}f{i % 24 + 1}'
                     for i, d in enumerate(definitions)}
        overrides = validate_keymap(overrides)
        self.app.set_keymap(overrides)
        calls = self.record_actions()
        for definition in definitions:
            calls.clear()
            await self.pilot.press(overrides[definition.binding_id])
            self.assertEqual(calls, [(definition.action, ())], definition.label)
        for definition in definitions:
            if definition.default_key in overrides.values(): continue
            calls.clear()
            await self.pilot.press(definition.default_key)
            self.assertEqual(calls, [], definition.default_key)

    async def test_custom_key_overrides_table_key_but_not_dialog_input(self):
        self.app.set_keymap({'mdir.copy': 'ctrl+home'})
        calls = []
        self.app.action_copy = lambda: calls.append('copy')
        await self.pilot.press('ctrl+home')
        self.assertEqual(calls, ['copy'])
        self.app.push_screen(self.app.PROMPT_SCREEN('Input:', 'abcd'))
        await self.pilot.pause()
        field = self.app.screen.query_one(Input)
        await self.pilot.press('end', 'ctrl+home')
        self.assertEqual(calls, ['copy'])
        self.assertIs(self.app.focused, field)
        await self.pilot.press('escape')

    async def test_native_capture_delivers_once_and_rejects_stale_context(self):
        app = self.app
        bridge = NativeShortcuts(1, lambda key, epoch: app.post_message(NativeShortcut(key, epoch)))
        app._shortcut_keyboard = bridge
        app._shortcut_context = None
        app._sync_shortcut_keyboard()
        calls = []
        app.action_mindex = lambda: calls.append('mindex')
        state = bridge.matcher
        state.feed(0xA2, True, True); state.feed(0xA0, True, True)
        captured = state.feed(ord('F'), True, True)
        self.assertTrue(captured.consume)  # Terminal must not open its own Find UI.
        self.assertEqual(captured.key, 'ctrl+shift+f')
        self.assertIsNone(state.feed(ord('F'), True, True).key)
        app.post_message(NativeShortcut(captured.key, captured.epoch))
        await self.pilot.pause()
        self.assertEqual(calls, ['mindex'])
        app.push_screen(app.PROMPT_SCREEN('Input:', 'abcd'))
        await self.pilot.pause()
        app.post_message(NativeShortcut(captured.key, captured.epoch))
        await self.pilot.pause()
        self.assertEqual(calls, ['mindex'])
        self.assertEqual(state.config[1], {})
        await self.pilot.press('escape')
        self.assertTrue(state.config[1])
        await app.on_event(events.AppBlur())
        await self.pilot.pause()
        self.assertEqual(state.config[1], {})

    async def test_save_commits_typed_key_without_apply_and_survives_reload(self):
        config = self.root / 'keys.json'
        with patch('mdir.app.save_keymap', side_effect=lambda keys: save_keymap(keys, config)):
            self.app._open_key_manager()
            await self.pilot.pause()
            table = self.app.screen.query_one('#key_table', DataTable)
            index = next(i for i, d in enumerate(KEY_DEFINITIONS) if d.binding_id == 'mdir.copy')
            table.move_cursor(row=index)
            await self.pilot.pause()
            self.app.screen.query_one('#key_input', Input).value = 'ctrl+home'
            self.assertTrue(await self.pilot.click('#key_save'))
            await self.pilot.pause()
        self.assertEqual(load_keymap(config), {'mdir.copy': 'ctrl+home'})
        self.app.set_keymap(load_keymap(config))
        calls = []
        self.app.action_copy = lambda: calls.append('copy')
        await self.pilot.press('ctrl+home')
        self.assertEqual(calls, ['copy'])

    async def test_invalid_editor_value_does_not_close_keys_on_save(self):
        self.app._open_key_manager()
        await self.pilot.pause()
        table = self.app.screen.query_one('#key_table', DataTable)
        table.move_cursor(row=next(i for i, d in enumerate(KEY_DEFINITIONS) if d.binding_id == 'mdir.copy'))
        await self.pilot.pause()
        self.app.screen.query_one('#key_input', Input).value = 'up'
        await self.pilot.click('#key_save')
        self.assertEqual(len(self.app.screen_stack), 2)
        await self.pilot.press('escape')

    async def native_press(self, key):
        app = self.app
        if app._shortcut_keyboard is None:
            app._shortcut_keyboard = NativeShortcuts(1, lambda *args: None)
            app._shortcut_context = None
            app._sync_shortcut_keyboard()
        state = app._shortcut_keyboard.matcher
        vk, modifiers = key_signature(key)
        codes = [code for name, code in [('ctrl', 0xA2), ('shift', 0xA0), ('alt', 0xA4)] if name in modifiers]
        for code in codes: state.feed(code, True, True)
        capture = state.feed(vk, True, True)
        self.assertTrue(capture.consume, key)
        self.assertEqual(capture.key, key)
        app.post_message(NativeShortcut(capture.key, capture.epoch))
        state.feed(vk, False, True)
        for code in reversed(codes): state.feed(code, False, True)
        await self.pilot.pause()

    async def test_native_hidden_key_survives_mouse_pane_roundtrips(self):
        app = self.app
        hidden = self.root / '.mouse-hidden.txt'
        hidden.write_text('mouse switch fixture')
        if os.name == 'nt':
            self.assertTrue(ctypes.windll.kernel32.SetFileAttributesW(str(hidden), 2))
        await self.native_press('ctrl+h')
        await self.wait_for(lambda: hidden in app.left.entries)
        for side in ('right', 'right', 'left', 'right', 'left'):
            pane = app.left if side == 'left' else app.right
            other = app.right if side == 'left' else app.left
            other_before = other.show_hidden_system
            await self.pilot.click(pane.table, offset=(5, 2))
            self.assertEqual(app.active_side, side)
            self.assertIs(app.focused, pane.table)
            before = pane.show_hidden_system
            await self.native_press('ctrl+h')
            self.assertEqual(pane.show_hidden_system, not before)
            self.assertEqual(other.show_hidden_system, other_before)
            await self.wait_for(lambda: (hidden in pane.entries) == pane.show_hidden_system)
            self.assertEqual(pane.current_path, self.root)

    async def test_capture_recovers_after_focus_precedes_activation_without_new_focus_event(self):
        app = self.app
        await self.native_press('ctrl+h')
        # Screen mouse dispatch changes focus before MDirDataTable activates
        # the pane. Reproduce that ordering without repairing the bridge.
        for side in ('right', 'left'):
            pane = app.right if side == 'right' else app.left
            app.screen.set_focus(pane.table)
            self.assertEqual(app._shortcut_keyboard.matcher.config[1], {})
            app.set_active(side)
            self.assertTrue(app._shortcut_keyboard.matcher.config[1])
            before = pane.show_hidden_system
            await self.native_press('ctrl+h')
            self.assertEqual(pane.show_hidden_system, not before)

    async def test_native_shortcuts_resume_after_dialog_then_mouse_switch(self):
        app = self.app
        await self.native_press('ctrl+h')
        for side in ('right', 'left'):
            pane = app.right if side == 'right' else app.left
            await self.pilot.click(pane.table, offset=(5, 2))
            path = self.root / 'item.txt'
            pane.table.move_cursor(row=pane.row_by_path[path])
            await self.pilot.pause()
            await self.native_press('alt+enter')
            self.assertIsInstance(app.screen, PropertiesScreen)
            self.assertEqual(app._shortcut_keyboard.matcher.config[1], {})
            await self.pilot.press('escape')
            await self.native_press('ctrl+h')
            await self.native_press('tab')
            await self.native_press('ctrl+h')

    async def wait_for(self, predicate):
        for _ in range(150):
            if predicate(): return
            await self.pilot.pause(0.02)
        self.assertTrue(predicate())

    async def test_reported_ctrl_h_reveals_only_active_pane_without_parent_navigation(self):
        hidden = self.root / '.hidden.txt'
        hidden.write_text('hidden fixture')
        if os.name == 'nt':
            self.assertTrue(ctypes.windll.kernel32.SetFileAttributesW(str(hidden), 2))
        app = self.app
        await self.native_press('ctrl+h')
        await self.wait_for(lambda: hidden in app.left.entries)
        self.assertEqual(app.left.current_path, self.root)
        self.assertFalse(app.right.show_hidden_system)
        self.assertNotIn(hidden, app.right.entries)
        await self.native_press('tab')
        await self.native_press('ctrl+h')
        await self.wait_for(lambda: hidden in app.right.entries)
        await self.native_press('ctrl+h')
        await self.wait_for(lambda: hidden not in app.right.entries)
        self.assertTrue(app.left.show_hidden_system)
        self.assertEqual(app.right.current_path, self.root)

    async def test_reported_workspace_keys_restore_paths_active_pane_and_hidden_flags(self):
        app = self.app
        app._workspace_store = WorkspaceStore(self.root / 'workspaces.json')
        folder = self.root / 'saved-right'; folder.mkdir()
        app.right.current_path = folder
        app.right.refresh_listing()
        await self.native_press('ctrl+h')
        await self.native_press('tab')
        await self.native_press('ctrl+shift+s')
        app.screen.query_one(Input).value = 'test-workspace'
        await self.pilot.press('enter')
        saved = app._workspace_store.get('test-workspace')
        self.assertIsNotNone(saved)
        app.left.current_path = folder
        app.right.current_path = self.root
        app.left.show_hidden_system = False
        app.right.show_hidden_system = True
        app.left.refresh_listing(); app.right.refresh_listing()
        app.set_active('left')
        await self.pilot.pause()
        await self.native_press('ctrl+shift+l')
        await self.pilot.press('enter')
        self.assertEqual((app.left.current_path, app.right.current_path), (self.root, folder))
        self.assertEqual(app.active_side, 'right')
        self.assertTrue(app.left.show_hidden_system)
        self.assertFalse(app.right.show_hidden_system)

    async def test_reported_macro_keys_record_copy_save_and_play_actual_operation(self):
        app = self.app
        app._macro_store = MacroStore(self.root / 'macros.json')
        destination = self.root / 'destination'; destination.mkdir()
        app.right.current_path = destination; app.right.refresh_listing()
        source = self.root / 'item.txt'
        app.left.table.move_cursor(row=app.left.row_by_path[source])
        await self.pilot.pause()
        await self.native_press('ctrl+shift+m')
        app.screen.query_one(Input).value = 'test-copy'
        await self.pilot.press('enter')
        self.assertEqual(app._macro_recording_name, 'test-copy')
        await self.native_press('f5')
        await self.pilot.press('enter')
        target = destination / source.name
        await self.wait_for(lambda: target.exists() and not app._file_operation_busy and len(app.screen_stack) == 1)
        self.assertEqual(target.read_text(), source.read_text())
        await self.native_press('ctrl+shift+m')
        self.assertIsNone(app._macro_recording_name)
        self.assertEqual(len(app._macro_store.get('test-copy').actions), 1)
        target.unlink()  # Only this test's copied fixture.
        await self.native_press('ctrl+alt+m')
        await self.pilot.press('enter')
        self.assertEqual(len(app.screen_stack), 2)  # Review before playback.
        await self.pilot.press('enter')
        await self.wait_for(lambda: target.exists() and not app._file_operation_busy and len(app.screen_stack) == 1)
        self.assertEqual(target.read_text(), 'item')

    async def test_reported_alt_enter_opens_properties_repeatedly(self):
        path = self.root / 'item.txt'
        self.app.left.table.move_cursor(row=self.app.left.row_by_path[path])
        await self.pilot.pause()
        for _ in range(3):
            await self.native_press('alt+enter')
            self.assertIsInstance(self.app.screen, PropertiesScreen)
            self.assertEqual(self.app.screen.path, path)
            self.assertEqual(self.app._shortcut_keyboard.matcher.config[1], {})
            await self.pilot.press('escape')
            self.assertEqual(len(self.app.screen_stack), 1)


class NativeKeyMatchingTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows keyboard hook')
    def test_native_shortcut_hook_starts_and_releases_thread(self):
        bridge = NativeShortcuts(1, lambda *args: None)
        bridge.configure(1, shortcut_routes({}))
        try:
            self.assertTrue(bridge.start(), bridge.error)
        finally:
            self.assertTrue(bridge.shutdown())
        self.assertFalse(bridge.active)

    def test_all_keys_compile_and_only_registered_chords_are_consumed(self):
        for key, route in shortcut_routes({}).items():
            state = ShortcutKeyState(); state.configure(10, {key: route})
            vk, modifiers = key_signature(key)
            for modifier, code in [('ctrl', 0xA2), ('shift', 0xA0), ('alt', 0xA4)]:
                if modifier in modifiers: state.feed(code, True, True)
            captured = state.feed(vk, True, True)
            self.assertEqual((captured.consume, captured.key, captured.epoch), (True, key, 10))
            self.assertTrue(state.feed(vk, False, False).consume)
            self.assertFalse(state.feed(vk, True, False).consume)

    def test_ctrl_shift_chords_and_ctrl_h_do_not_collapse(self):
        state = ShortcutKeyState(); state.configure(2, shortcut_routes({}))
        state.feed(0xA2, True, True)
        self.assertEqual(state.feed(ord('H'), True, True).key, 'ctrl+h')
        state.feed(ord('H'), False, True)
        self.assertEqual(state.feed(ord('D'), True, True).key, 'ctrl+d')
        state.feed(ord('D'), False, True); state.feed(0xA0, True, True)
        self.assertEqual(state.feed(ord('D'), True, True).key, 'ctrl+shift+d')

    def test_navigation_repeat_and_command_repeat(self):
        state = ShortcutKeyState(); state.configure(1, shortcut_routes({}))
        self.assertEqual(state.feed(0x28, True, True).key, 'down')
        self.assertEqual(state.feed(0x28, True, True).key, 'down')
        self.assertEqual(state.feed(0x74, True, True).key, 'f5')
        self.assertIsNone(state.feed(0x74, True, True).key)
        state.configure(2, {})
        self.assertTrue(state.feed(0x74, False, True).consume)
        self.assertFalse(state.feed(0x74, True, True).consume)

    def test_reserved_keys_and_hidden_fixed_navigation_cannot_be_assigned(self):
        for key in ('up', 'home', 'pagedown', 'alt+f4', 'super+l', 'ctrl+alt+delete'):
            with self.assertRaises(ValueError, msg=key): validate_keymap({'mdir.copy': key})

