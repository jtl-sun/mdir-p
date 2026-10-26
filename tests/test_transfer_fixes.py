import errno
import os
import stat
import tempfile
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch
from textual.app import App
from textual.widgets import Static
from mdir.ui.dialogs import FileOperationProgressScreen
from mdir.progress import ProgressTracker, ProgressSnapshot
import mdir.file_operations as ops

class TransferTests(unittest.TestCase):
    def test_readonly_overwrite_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'photos'; source.mkdir()
            (source / 'new.jpg').write_bytes(b'new')
            out = root / 'out'; out.mkdir()
            old = out / 'photos'; old.mkdir()
            (old / 'old.jpg').write_bytes(b'old')
            os.chmod(old / 'old.jpg', stat.S_IREAD)
            result = ops.run_file_operation('copy', [source], out, overwrite=True)
            self.assertEqual(result.errors, [])
            self.assertEqual(list(out.iterdir()), [old])
            self.assertTrue(source.exists())

    def cross_move(self, fail_cleanup=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / 'photos'; source.mkdir()
            (source / 'photo.jpg').write_bytes(b'new')
            os.chmod(source / 'photo.jpg', stat.S_IREAD)
            out = root / 'out'; out.mkdir()
            target = out / source.name
            replace = ops._replace_path
            remove = ops._remove_existing_target
            def cross(src, dst):
                if src == source:
                    raise OSError(errno.EXDEV, 'cross device')
                return replace(src, dst)
            def cleanup(path):
                if path == source and fail_cleanup:
                    raise PermissionError('locked source')
                return remove(path)
            with patch.object(ops, '_replace_path', side_effect=cross), patch.object(ops, '_remove_existing_target', side_effect=cleanup):
                result = ops.run_file_operation('move', [source], out, tracker=ProgressTracker('move'))
            self.assertEqual((target / 'photo.jpg').read_bytes(), b'new')
            self.assertEqual(source.exists(), fail_cleanup)
            self.assertEqual(bool(result.errors), fail_cleanup)
            self.assertEqual(result.completed, 0 if fail_cleanup else 1)
            if source.exists(): remove(source)
            remove(target)

    def test_cross_drive_readonly_source_removed(self):
        self.cross_move()

    def test_source_cleanup_failure_keeps_destination(self):
        self.cross_move(True)

class TestApp(App):
    def set_status(self, text): self.status_text = text

class ProgressUiTests(unittest.IsolatedAsyncioTestCase):
    async def test_background_resumes_and_dismisses_and_can_reopen(self):
        app = TestApp()
        cancel, pause = Event(), Event()
        async with app.run_test(size=(120, 35)) as pilot:
            screen = FileOperationProgressScreen('copy', 1, cancel, pause)
            app.push_screen(screen)
            await pilot.pause()
            screen.update_snapshot(ProgressSnapshot('copy', bytes_done=1024, total_bytes=2048, total_items=1))
            self.assertIn('1.0 KB', str(screen.query_one('#file_operation_metrics', Static).render()))
            await pilot.click('#file_operation_pause')
            self.assertTrue(pause.is_set())
            await pilot.click('#file_operation_background')
            await pilot.pause()
            self.assertFalse(pause.is_set())
            self.assertFalse(cancel.is_set())
            self.assertIs(app.screen, app.screen_stack[0])
            app.push_screen(FileOperationProgressScreen('copy', 1, cancel, pause))
            await pilot.pause()
            self.assertIsInstance(app.screen, FileOperationProgressScreen)

    async def test_real_worker_continues_after_background(self):
        import asyncio
        from mdir.app import MDirApp
        from test_thumbnail import FakeManager

        async def wait_until(predicate, message, timeout=15):
            deadline = asyncio.get_running_loop().time() + timeout
            while not predicate():
                if asyncio.get_running_loop().time() >= deadline:
                    self.fail(message)
                await asyncio.sleep(0.05)

        for operation in ('copy', 'move'):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source_dir = root / 'left'; source_dir.mkdir()
                out = root / 'right'; out.mkdir()
                payload = b'x' * (2 * 1024 * 1024)
                source = source_dir / 'data.bin'; source.write_bytes(payload)
                app = MDirApp(); app.left_start = source_dir; app.right_start = out
                app._save_paths = lambda: None
                entered, release = Event(), Event()
                advance = ProgressTracker.advance
                def gated_advance(tracker, amount):
                    advance(tracker, amount)
                    if not entered.is_set():
                        entered.set()
                        if not release.wait(120):
                            raise TimeoutError('Test did not release transfer worker')
                replace = ops._replace_path
                def cross(src, dst):
                    if src == source and operation == 'move':
                        raise OSError(errno.EXDEV, 'cross device')
                    return replace(src, dst)
                with patch('mdir.core.load_config_data', return_value={}), patch('mdir.thumbnail_app.ThumbnailManager', FakeManager), patch.object(ProgressTracker, 'advance', gated_advance), patch.object(ops, '_replace_path', side_effect=cross):
                    async with app.run_test(size=(120, 38)) as pilot:
                        try:
                            await wait_until(lambda: app.left.initial_listing_complete and app.right.initial_listing_complete, 'Pane listing did not finish')
                            app._start_file_operation(operation, (source,), out, 'left')
                            await wait_until(entered.is_set, 'Transfer worker did not start')
                            await pilot.click('#file_operation_background')
                            await wait_until(lambda: not isinstance(app.screen, FileOperationProgressScreen), 'Background did not close modal')
                            self.assertTrue(app._file_operation_busy)
                            window = app._file_mini_window
                            self.assertIsNotNone(window)
                            self.assertIsNone(window.process.poll())
                            app.set_active('right')
                            self.assertEqual(app.active_side, 'right')
                            window.commands.put('pause')
                            await wait_until(app._file_operation_pause.is_set, 'Mini-window pause was not handled')
                            window.commands.put('resume')
                            await wait_until(lambda: not app._file_operation_pause.is_set(), 'Mini-window resume was not handled')
                            window.commands.put('foreground')
                            await wait_until(lambda: isinstance(app.screen, FileOperationProgressScreen), 'Foreground was not restored')
                            await pilot.pause()
                            await pilot.click('#file_operation_background')
                            await wait_until(lambda: not isinstance(app.screen, FileOperationProgressScreen), 'Second Background failed')
                            release.set()
                            await wait_until(lambda: not app._file_operation_busy, 'Background transfer did not finish')
                            self.assertIsNone(app._file_mini_window)
                            self.assertEqual((out / source.name).read_bytes(), payload)
                            self.assertEqual(source.exists(), operation == 'copy')
                        finally:
                            # Always unblock and join the real worker before
                            # TemporaryDirectory removes files, including on failure.
                            if app._file_operation_busy:
                                app._file_operation_cancel.set()
                                app._file_operation_pause.clear()
                            release.set()
                            await wait_until(lambda: not app._file_operation_busy, 'Transfer worker cleanup timed out')
