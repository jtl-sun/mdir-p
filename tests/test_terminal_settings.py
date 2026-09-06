import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("hide_azure", Path(__file__).resolve().parents[1] / "tools/windows-terminal/hide_azure.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TerminalSettingsTests(unittest.TestCase):
    def test_preserves_other_settings_and_original_backup(self):
        original = {"profiles": {"list": [{"name": "Ubuntu-26.04", "hidden": False}, {"source": "Windows.Terminal.Azure", "hidden": False}]}, "theme": "dark", "disabledProfileSources": ["Other.Source"]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            payload = json.dumps(original).encode()
            path.write_bytes(payload)
            backup = module.apply(path)
            self.assertEqual(backup.read_bytes(), payload)
            changed = json.loads(path.read_text())
            self.assertTrue(changed["profiles"]["list"][1]["hidden"])
            self.assertEqual(changed["profiles"]["list"][0], original["profiles"]["list"][0])
            self.assertEqual(changed["theme"], "dark")
            self.assertEqual(changed["disabledProfileSources"], ["Other.Source", "Windows.Terminal.Azure"])
            self.assertIsNone(module.apply(path))

    def test_invalid_json_is_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text('{ // comment\n }')
            original = path.read_bytes()
            with self.assertRaises(ValueError):
                module.apply(path)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(len(list(path.parent.iterdir())), 1)

    def test_missing_azure_disables_generator(self):
        self.assertEqual(module.updated_settings({})["disabledProfileSources"], ["Windows.Terminal.Azure"])
