"""Regression tests: large pane updates and modal compositing must not overlap."""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from mdir.app import MDirApp
from mdir.fast_app import FastFileManagerApp


class ModalRepaintTests(unittest.TestCase):
    def test_modal_pop_schedules_one_full_repaint(self):
        dummy = SimpleNamespace(
            screen_stack=[object(), object()],
            _modal_was_open=False,
            _preview_modal_suspended=False,
            preview_mode=False,
            _sync_thumbnails=Mock(),
            call_after_refresh=Mock(),
            _redraw_after_modal=Mock(),
            _resume_preview_after_modal=Mock(),
        )
        MDirApp._preview_screen_changed(dummy, object())
        self.assertTrue(dummy._modal_was_open)
        dummy.screen_stack = [object()]
        MDirApp._preview_screen_changed(dummy, object())
        self.assertFalse(dummy._modal_was_open)
        dummy.call_after_refresh.assert_called_once_with(
            dummy._redraw_after_modal
        )
        # Subsequent main-screen updates must not create an infinite loop.
        MDirApp._preview_screen_changed(dummy, object())
        dummy.call_after_refresh.assert_called_once()

    def test_resume_repaint_rechecks_deferred_directory_changes(self):
        host = SimpleNamespace(
            is_running=True,
            screen_stack=[object()],
            _closing=False,
            _refresh_post_progress_view=Mock(),
            _poll_directory_changes=Mock(),
            set_timer=Mock(),
        )
        MDirApp._redraw_after_modal(host)
        host._refresh_post_progress_view.assert_called_once()
        host._poll_directory_changes.assert_called_once()
        host.set_timer.assert_called_once_with(
            0.06, host._refresh_post_progress_view
        )

    def test_manual_redraw_only_when_main_file_panes_are_visible(self):
        host = SimpleNamespace(
            screen_stack=[object(), object()],
            _refresh_post_progress_view=Mock(),
            set_timer=Mock(),
        )
        MDirApp.action_redraw_screen(host)
        host._refresh_post_progress_view.assert_not_called()
        host.screen_stack = [object()]
        MDirApp.action_redraw_screen(host)
        host._refresh_post_progress_view.assert_called_once()


class BackgroundRefreshModalGuardTests(unittest.TestCase):
    def test_changed_panels_are_not_rebuilt_under_modal(self):
        host = SimpleNamespace(
            _file_operation_busy=False,
            _archive_busy=False,
            _directory_refresh_running=False,
            screen_stack=[object(), object()],
            left=Mock(side_effect=AssertionError("Must not touch panes")),
            right=Mock(side_effect=AssertionError("Must not touch panes")),
        )
        FastFileManagerApp._apply_directory_changes(
            host, (("left", object(), None),)
        )
        self.assertFalse(host._directory_refresh_running)

    def test_pending_directory_results_are_discarded_under_modal(self):
        host = SimpleNamespace(
            _file_operation_busy=False,
            _archive_busy=False,
            screen_stack=[object(), object()],
            _directory_refresh_running=True,
            run_worker=Mock(),
        )
        FastFileManagerApp._finish_background_directory_refresh(
            host, (("left", "unused"),)
        )
        host.run_worker.assert_not_called()
        self.assertFalse(host._directory_refresh_running)


if __name__ == "__main__":
    unittest.main()
