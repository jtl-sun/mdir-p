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
        import time
        from mdir.app import MDirApp
        from test_thumbnail import FakeManager
        for operation in ('copy', 'move'):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source_dir = root / 'left'; source_dir.mkdir()
                out = root / 'right'; out.mkdir()
                source = source_dir / 'data.bin'; source.write_bytes(b'x' * (8 * 1024 * 1024))
                app = MDirApp(); app.left_start = source_dir; app.right_start = out
                app._save_paths = lambda: None
                advance = ProgressTracker.advance
                def slow_advance(tracker, amount):
                    time.sleep(0.5)
                    advance(tracker, amount)
                replace = ops._replace_path
                def cross(src, dst):
                    if src == source and operation == 'move':
                        raise OSError(errno.EXDEV, 'cross device')
                    return replace(src, dst)
                with patch('mdir.core.load_config_data', return_value={}), patch('mdir.thumbnail_app.ThumbnailManager', FakeManager), patch.object(ProgressTracker, 'advance', slow_advance), patch.object(ops, '_replace_path', side_effect=cross):
                    async with app.run_test(size=(120, 38)) as pilot:
                        for _ in range(100):
                            if app.left.initial_listing_complete and app.right.initial_listing_complete: break
                            await pilot.pause(0.02)
                        app._start_file_operation(operation, (source,), out, 'left')
                        await pilot.pause(0.1)
                        await pilot.click('#file_operation_background')
                        await pilot.pause(0.1)
                        self.assertNotIsInstance(app.screen, FileOperationProgressScreen)
                        self.assertTrue(app._file_operation_busy)
                        window = app._file_mini_window
                        self.assertIsNotNone(window)
                        self.assertIsNone(window.process.poll())
                        app.set_active('right')
                        self.assertEqual(app.active_side, 'right')
                        # Exercise commands from the independent window.
                        window.commands.put('pause')
                        await pilot.pause(0.2)
                        self.assertTrue(app._file_operation_pause.is_set())
                        window.commands.put('resume')
                        await pilot.pause(0.2)
                        self.assertFalse(app._file_operation_pause.is_set())
                        window.commands.put('foreground')
                        await pilot.pause(0.1)
                        self.assertIsInstance(app.screen, FileOperationProgressScreen)
                        await pilot.click('#file_operation_background')
                        for _ in range(150):
                            if not app._file_operation_busy: break
                            await pilot.pause(0.02)
                        self.assertFalse(app._file_operation_busy)
                        self.assertIsNone(app._file_mini_window)
                        self.assertEqual((out / source.name).read_bytes(), b'x' * (8 * 1024 * 1024))
                        self.assertEqual(source.exists(), operation == 'copy')
