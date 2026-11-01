"""Regression coverage for visible marks and actionable cleanup blockers."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rich.text import Text
from textual.app import App
from textual.widgets import DataTable, Static

from mdir.ui.duplicate_review import DuplicateReviewScreen


class VisibleMarkAndDeletionFeedbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_marks_render_as_unambiguous_rich_text(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            a, b = root / "first.m4a", root / "second.m4a"
            a.write_bytes(b"identical song")
            b.write_bytes(b"identical song")
            screen = DuplicateReviewScreen(
                root, [("Exact 1", a, 14), ("Exact 1", b, 14)],
                1, 0, root / "notes.json",
            )
            app = App()
            async with app.run_test(size=(145, 45)) as pilot:
                app.push_screen(screen)
                await pilot.pause()
                table = screen.query_one("#duplicate_table", DataTable)
                self.assertIsInstance(table.get_row_at(0)[0], Text)
                self.assertEqual(table.get_row_at(0)[0].plain, "—")
                await pilot.click("#duplicate_mark")
                await pilot.pause()
                self.assertEqual(len(screen._marked), 1)
                self.assertEqual(table.get_row_at(0)[0].plain, "✓ MARK")
                self.assertEqual(table.get_row_at(1)[0].plain, "—")
                self.assertIn(
                    "Eligible to recycle: 1",
                    str(screen.query_one("#duplicate_feedback", Static).render()),
                )
                screen.dismiss(None)
                await pilot.pause()

    async def test_all_marked_shows_blocker_even_after_cursor_moves(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            a, b = root / "original.m4a", root / "backup.m4a"
            a.write_bytes(b"sound")
            b.write_bytes(b"sound")
            screen = DuplicateReviewScreen(
                root, [("Exact 1", a, 5), ("Exact 1", b, 5)],
                1, 0, root / "notes.json",
            )
            app = App()
            async with app.run_test(size=(145, 45)) as pilot:
                app.push_screen(screen)
                await pilot.pause()
                screen._marked = {("Exact 1", a), ("Exact 1", b)}
                screen._show_page()
                await pilot.click("#duplicate_delete_marked")
                await pilot.pause()
                self.assertIs(app.screen, screen)
                table = screen.query_one("#duplicate_table", DataTable)
                table.move_cursor(row=1)
                await pilot.pause()
                feedback = str(
                    screen.query_one("#duplicate_feedback", Static).render()
                )
                self.assertIn("Deletion blocked", feedback)
                self.assertIn("0 eligible", feedback)
                self.assertIn("Unmark at least one copy", feedback)
                self.assertTrue(a.exists())
                self.assertTrue(b.exists())
                screen.dismiss(None)
                await pilot.pause()

    async def test_row_select_does_not_depend_on_button_focus(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            a, b = root / "A.m4a", root / "B.m4a"
            a.write_bytes(b"same")
            b.write_bytes(b"same")
            screen = DuplicateReviewScreen(
                root, [("Exact 1", a, 4), ("Exact 1", b, 4)],
                1, 0, root / "notes.json",
            )
            app = App()
            async with app.run_test(size=(145, 45)) as pilot:
                app.push_screen(screen)
                await pilot.pause()
                screen.query_one("#duplicate_keep").focus()
                screen.row_selected(type("RowSelected", (), {"stop": lambda _:None})())
                await pilot.pause()
                self.assertEqual(len(screen._marked), 1)
                self.assertIn(
                    "✓ MARK", screen.query_one("#duplicate_table", DataTable).get_row_at(0)[0].plain
                )
                screen.dismiss(None)
                await pilot.pause()


if __name__ == "__main__":
    unittest.main()
