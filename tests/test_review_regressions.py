from __future__ import annotations

import inspect
import unittest

import mdir.elevation as elevation
import mdir.fast_app as fast_app
import mdir.office_pdf_preview as office_pdf_preview


class Review2630RegressionTests(unittest.TestCase):
    def test_shell_item_uses_selected_absolute_path_without_resolving_link(self) -> None:
        source = inspect.getsource(elevation._create_shell_item)
        self.assertIn("os.path.abspath(os.fspath(path))", source)
        self.assertNotIn("path.resolve", source)

    def test_admin_delete_stops_before_permanent_batch_after_cancel(self) -> None:
        source = inspect.getsource(elevation.run_elevated_delete)
        self.assertIn("Do not start the permanent-delete batch after cancellation", source)
        self.assertIn("result.cancelled = True", source)

    def test_office_request_is_registered_before_waiting_for_session_lock(self) -> None:
        source = inspect.getsource(office_pdf_preview.render_office_pdf_cached)
        active = source.index("_ACTIVE_CANCELS.add(cancel)")
        session = source.index("with _SESSION_LOCK:")
        self.assertLess(active, session)

    def test_late_startup_callback_does_not_unconditionally_steal_focus(self) -> None:
        source = inspect.getsource(fast_app.FastFileManagerApp._finish_startup_frame)
        self.assertIn("self.active.table.screen is self.screen", source)


if __name__ == "__main__":
    unittest.main()
