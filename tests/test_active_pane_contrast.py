"""The modern mDir skin must darken the working pane, not the inactive one."""
import unittest

from mdir.app import MDirApp
from mdir.theme import MDIR_THEME_CSS


class ActivePaneContrastTests(unittest.TestCase):
    def test_modern_only_backgrounds(self):
        self.assertIn("FilePane.skin-modern.active DataTable", MDIR_THEME_CSS)
        self.assertIn("FilePane.skin-modern DataTable:focus", MDIR_THEME_CSS)
        self.assertIn("background: #191919;", MDIR_THEME_CSS)
        self.assertIn("background: #292929;", MDIR_THEME_CSS)
        self.assertIn('pane.set_class(self.theme == THEME_NAME, "skin-modern")',
                      __import__("inspect").getsource(MDirApp._sync_skin_classes))

    def test_theme_colours_preserve_retro_selection(self):
        from mdir.theme import OLD_M_THEME, NORTON_THEME
        self.assertEqual(OLD_M_THEME.background, "#000000")
        self.assertEqual(NORTON_THEME.panel, "#0000aa")

if __name__ == "__main__":
    unittest.main()
