"""Regression tests for progress-overlay redraws and safe large-folder refreshes."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from mdir.app import MDirApp
from mdir.fast_app import FastFileManagerApp, LargeDirectoryFilePane
from mdir.progress import ProgressSnapshot


class OverlayRedrawTests(unittest.TestCase):
    @staticmethod
    def fake_pane():
        return SimpleNamespace(
            table=SimpleNamespace(refresh=Mock()),
            refresh=Mock(),
        )

    def test_redraw_only_visible_cells_without_rebuilding_large_lists(self):
        left, right = self.fake_pane(), self.fake_pane()
        screen = SimpleNamespace(refresh=Mock())
        fake = SimpleNamespace(
            is_running=True, screen_stack=(screen,),
            left=left, right=right, screen=screen,
        )
        FastFileManagerApp._refresh_post_progress_view(fake)
        left.table.refresh.assert_called_once_with(repaint=True)
        right.table.refresh.assert_called_once_with(repaint=True)
        left.refresh.assert_called_once_with(repaint=True)
        right.refresh.assert_called_once_with(repaint=True)
        screen.refresh.assert_called_once_with(repaint=True)

    def test_redraw_does_not_repaint_beneath_an_open_modal(self):
        left, right = self.fake_pane(), self.fake_pane()
        screen = SimpleNamespace(refresh=Mock())
        fake = SimpleNamespace(
            is_running=True, screen_stack=(screen, object()),
            left=left, right=right, screen=screen,
        )
        FastFileManagerApp._refresh_post_progress_view(fake)
        left.table.refresh.assert_not_called()
        right.table.refresh.assert_not_called()
        screen.refresh.assert_not_called()

    def test_native_window_prevents_duplicate_file_progress_terminal_updates(self):
        app = MDirApp()
        native = SimpleNamespace(update=Mock())
        status = Mock()
        app.set_status = status
        app._file_operation_busy = True
        app._file_operation_screen = None
        app._file_mini_window = native

        snapshot = ProgressSnapshot(
            operation="move", total_items=866, items_done=468,
            current_name="음악 파일 🎵.m4a", total_bytes=3_400_000_000,
            bytes_done=1_800_000_000,
        )
        app._update_file_operation_snapshot(snapshot)
        native.update.assert_called_once_with(snapshot)
        status.assert_not_called()

    def test_native_window_prevents_duplicate_archive_terminal_updates(self):
        app = MDirApp()
        native = SimpleNamespace(update=Mock())
        status = Mock()
        app.set_status = status
        app._archive_busy = True
        app._archive_progress_screen = None
        app._archive_mini_window = native

        snapshot = ProgressSnapshot(
            operation="compress", total_items=100, items_done=20,
            current_name="노래.m4a",
        )
        app._update_archive_progress(snapshot)
        native.update.assert_called_once_with(snapshot)
        status.assert_not_called()


class StaleDirectoryRefreshTests(unittest.IsolatedAsyncioTestCase):
    async def test_stale_generation_never_clears_current_rows(self):
        pane = SimpleNamespace(
            _listing_generation=8,
            app=SimpleNamespace(_file_operation_busy=False, _archive_busy=False),
            _prepare_cached_rows=Mock(),
        )
        result = await LargeDirectoryFilePane.render_cached_rows_responsively(
            pane, generation=7,
        )
        self.assertFalse(result)
        pane._prepare_cached_rows.assert_not_called()

    async def test_bulk_transfer_pauses_auto_refresh_before_clearing_rows(self):
        pane = SimpleNamespace(
            _listing_generation=8,
            app=SimpleNamespace(_file_operation_busy=True, _archive_busy=False),
            _prepare_cached_rows=Mock(),
        )
        result = await LargeDirectoryFilePane.render_cached_rows_responsively(
            pane, generation=8,
        )
        self.assertFalse(result)
        pane._prepare_cached_rows.assert_not_called()


if __name__ == "__main__":
    unittest.main()
