from pathlib import Path
import unittest


class RootScreenLayoutTests(unittest.TestCase):
    def test_main_screen_is_fixed_and_uses_full_textual_width(self):
        source = (Path(__file__).resolve().parents[1] / "mdir" / "app.py").read_text(encoding="utf-8")
        self.assertIn("Screen {\n        overflow: hidden;\n    }", source)
        self.assertIn("#panes {\n        width: 100%;\n    }", source)


if __name__ == "__main__":
    unittest.main()
