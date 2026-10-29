"""Regression checks for both DOS palettes and high-contrast row selection."""
import unittest
from unittest.mock import patch

from rich.style import Style
from textual.theme import Theme

from mdir.theme import (
    MDIR_THEME, OLD_M_THEME, NORTON_THEME,
    OLD_M_THEME_NAME, NORTON_THEME_NAME,
    selection_colors, install_file_colors,
)


class RetroThemeTests(unittest.TestCase):
    def tearDown(self):
        install_file_colors(MDIR_THEME)

    def test_distinct_retro_palettes(self):
        self.assertEqual(OLD_M_THEME.name, OLD_M_THEME_NAME)
        self.assertEqual(OLD_M_THEME.background, "#000000")
        self.assertEqual(OLD_M_THEME.accent, "#ff5a61")
        self.assertEqual(NORTON_THEME.name, NORTON_THEME_NAME)
        self.assertEqual(NORTON_THEME.panel, "#0000aa")
        self.assertEqual(NORTON_THEME.variables["mdir-header-foreground"], "#ffff55")

    def test_selected_row_colors_for_both_panes_and_default(self):
        expected = [
            (MDIR_THEME, ("#159bb8", "#ffffff"), ("#364953", "#ffffff")),
            (OLD_M_THEME, ("#ff5a61", "#000000"), ("#99484d", "#ffffff")),
            (NORTON_THEME, ("#55ffff", "#000066"), ("#315fc2", "#ffffff")),
        ]
        for theme, active, inactive in expected:
            with self.subTest(theme=theme.name):
                install_file_colors(theme)
                self.assertEqual(selection_colors(active=True), active)
                self.assertEqual(selection_colors(active=False), inactive)

    def test_selected_segments_are_contrasting_and_preserve_metadata(self):
        from mdir.ui.rename import SlowRenameDataTable
        from rich.segment import Segment
        from unittest.mock import MagicMock
        table = SlowRenameDataTable()
        original = Segment("Favorites", Style(color="#7e9aaa", meta={"row": 2}))
        with patch.object(type(table).__mro__[1], "_render_cell", return_value=[[original]]):
            with patch.object(table, "_pane", return_value=MagicMock(has_class=lambda c: True)):
                install_file_colors(OLD_M_THEME)
                lines = table._render_cell(2, 0, Style(), 20, cursor=True)
        self.assertEqual(lines[0][0].style.color.get_truecolor().hex, "#000000")
        self.assertEqual(lines[0][0].style.bgcolor.get_truecolor().hex, "#ff5a61")
        self.assertEqual(lines[0][0].style.meta.get("row"), 2)


if __name__ == "__main__":
    unittest.main()
