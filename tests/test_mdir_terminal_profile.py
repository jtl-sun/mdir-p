import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "windows-terminal"
    / "mdir_profile.py"
)
spec = importlib.util.spec_from_file_location("mdir_terminal_profile", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MDirTerminalProfileTests(unittest.TestCase):
    def test_profile_hides_host_scrollbar_and_padding(self):
        payload = module.fragment_payload(
            r"C:\Users\sun\AppData\Local\mDIR\venv\Scripts\python.exe",
            icon_path=r"C:\Users\sun\AppData\Local\mDIR\mdir.ico",
            starting_directory=r"C:\Users\sun",
        )
        self.assertEqual(list(payload), ["profiles"])
        self.assertEqual(len(payload["profiles"]), 1)
        profile = payload["profiles"][0]
        self.assertEqual(profile["name"], "mDIR")
        self.assertEqual(profile["guid"], module.PROFILE_GUID)
        self.assertEqual(profile["scrollbarState"], "hidden")
        self.assertEqual(profile["padding"], "0")
        self.assertFalse(profile["suppressApplicationTitle"])
        self.assertIn('"C:\\Users\\sun\\AppData\\Local\\mDIR\\venv\\Scripts\\python.exe"', profile["commandline"])
        self.assertTrue(profile["commandline"].endswith(" -P -m mdir"))

    def test_fragment_write_is_valid_utf8_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mDIR" / "mdir.json"
            module.write_fragment(
                path,
                r"C:\mDIR\python.exe",
                starting_directory=r"C:\Users\sun",
            )
            raw = path.read_bytes()
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
            payload = json.loads(raw.decode("utf-8"))
            self.assertEqual(payload["profiles"][0]["scrollbarState"], "hidden")
            self.assertEqual(payload["profiles"][0]["padding"], "0")

    def test_installer_targets_dedicated_profile_without_editing_settings_json(self):
        installer = (Path(__file__).resolve().parents[1] / "install_windows.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("Windows Terminal\\Fragments\\mDIR", installer)
        self.assertIn('new-tab -p "mDIR"', installer)
        self.assertNotIn("settings.json", installer)


if __name__ == "__main__":
    unittest.main()
