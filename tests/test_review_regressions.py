"""Regression coverage for the 2.26.29 release audit; no real elevated deletes."""
import ctypes
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from mdir import elevation, office_pdf_preview as office


@unittest.skipUnless(os.name == 'nt', 'Windows COM boundary')
class ElevatedDeleteCancellationTests(unittest.TestCase):
    def setUp(self):
        self.ole = Mock()
        self.ole.CoInitializeEx.return_value = 0
        self.dll = patch.object(ctypes, 'WinDLL', return_value=self.ole)
        self.dll.start()
        self.addCleanup(self.dll.stop)

    def test_cancelled_recycle_batch_never_starts_permanent_batch(self):
        small, large = Path('small.txt'), Path('large.bin')
        with patch.object(elevation, '_run_native_shell_delete', return_value=True) as run, \
             patch.object(os.path, 'lexists', return_value=True):
            with self.assertRaises(elevation.ElevationCancelled):
                elevation.run_elevated_delete([small, large], permanent_items=[large])
        run.assert_called_once_with((small,), recycle=True, owner_hwnd=0)
        self.ole.CoUninitialize.assert_called_once()

    def test_partial_cancel_preserves_completed_count_and_stops(self):
        done, left, large = Path('done.txt'), Path('left.txt'), Path('large.bin')
        with patch.object(elevation, '_run_native_shell_delete', return_value=True) as run, \
             patch.object(os.path, 'lexists', side_effect=lambda p: p != done):
            result = elevation.run_elevated_delete([done, left, large], permanent_items=[large])
        self.assertTrue(result.cancelled)
        self.assertEqual(result.completed, 1)
        self.assertEqual(result.recycled, 1)
        self.assertEqual(result.permanently_deleted, 0)
        self.assertEqual(run.call_count, 1)

    def test_second_batch_error_reports_first_batch_success(self):
        small, large = Path('small.txt'), Path('large.bin')
        with patch.object(elevation, '_run_native_shell_delete',
                          side_effect=[False, elevation.ElevationError('broker error')]), \
             patch.object(os.path, 'lexists', side_effect=lambda p: p == large):
            result = elevation.run_elevated_delete([small, large], permanent_items=[large])
        self.assertEqual(result.completed_names, ['small.txt'])
        self.assertEqual(result.recycled, 1)
        self.assertEqual(result.permanently_deleted, 0)
        self.assertIn('broker error', result.errors[0])

    def test_shell_receives_link_path_instead_of_resolved_target(self):
        link = Path('selected-link')
        def create(name, context, iid, output):
            self.assertEqual(name, os.path.abspath(link))
            ctypes.cast(output, ctypes.POINTER(ctypes.c_void_p))[0] = 123
            return 0
        self.ole.SHCreateItemFromParsingName.side_effect = create
        with patch.object(Path, 'resolve', return_value=Path('unselected-target')):
            self.assertEqual(elevation._create_shell_item(link).value, 123)


class OfficeQueueCancellationTests(unittest.TestCase):
    def test_new_selection_cancels_waiting_conversion_before_worker_starts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'queued.xlsx'
            source.write_bytes(b'fixture')
            cancel = threading.Event()
            results = []
            with patch.dict(os.environ, {'LOCALAPPDATA': str(root)}), \
                 patch.object(office, '_get_session') as session, \
                 patch.object(office, '_diagnostic'):
                office._SESSION_LOCK.acquire()
                worker = threading.Thread(target=lambda: results.append(
                    office.render_office_pdf_cached(source, cancel=cancel)))
                worker.start()
                try:
                    deadline = time.monotonic() + 3
                    registered = False
                    while time.monotonic() < deadline:
                        with office._ACTIVE_LOCK:
                            registered = cancel in office._ACTIVE_CANCELS
                        if registered:
                            break
                        time.sleep(0.01)
                    self.assertTrue(registered, 'Queued conversion must be cancellable')
                    office.cancel_office_pdf_preview()
                    self.assertTrue(cancel.is_set())
                finally:
                    cancel.set()
                    office._SESSION_LOCK.release()
                    worker.join(timeout=5)
                self.assertFalse(worker.is_alive())
                session.assert_not_called()
            self.assertFalse(results[0].ok)
            self.assertEqual(results[0].error, 'cancelled')
            with office._ACTIVE_LOCK:
                self.assertNotIn(cancel, office._ACTIVE_CANCELS)
