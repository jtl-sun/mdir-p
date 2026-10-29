from pathlib import Path
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from mdir.shortcuts import (
    CONFIG_ENVIRONMENT_VARIABLE,
    DEFAULT_SHORTCUTS,
    load_shortcuts,
    migrate_legacy_shortcut_config,
    save_shortcuts,
    shortcut_config_path,
)


class ShortcutPrivacyTests(unittest.TestCase):
    def test_builtin_links_are_portable(self):
        for item in DEFAULT_SHORTCUTS:
            target = item.target
            self.assertNotRegex(target, r"^[A-Za-z]:[\\/]")
            self.assertNotIn("\\Users\\", target)
            self.assertNotIn("/Users/", target)
            self.assertNotIn("/home/", target)

    def test_legacy_personal_links_migrate_without_deleting_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / ".mdir-p-shortcuts.json"
            destination = root / "Config" / "shortcuts.json"
            values = [
                {
                    "label": "PrivateFolder",
                    "type": "folder",
                    "target": r"D:\\Private\\Work",
                    "args": [],
                    "pane": "active",
                }
            ]
            legacy.write_text(json.dumps(values), encoding="utf-8")
            result = migrate_legacy_shortcut_config(destination, legacy)
            self.assertEqual(result, destination)
            self.assertTrue(destination.exists())
            self.assertTrue(legacy.exists())
            loaded = load_shortcuts(destination)
            self.assertEqual(loaded[0].target, r"D:\\Private\\Work")

    def test_empty_legacy_list_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / ".mdir-p-shortcuts.json"
            destination = root / "Config" / "shortcuts.json"
            legacy.write_text("[]", encoding="utf-8")
            result = migrate_legacy_shortcut_config(destination, legacy)
            self.assertEqual(result, destination)
            self.assertEqual(json.loads(destination.read_text(encoding="utf-8")), [])
            self.assertTrue(legacy.exists())

    def test_environment_override_remains_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            custom = Path(directory) / "my-links.json"
            with patch.dict(os.environ, {CONFIG_ENVIRONMENT_VARIABLE: str(custom)}):
                self.assertEqual(shortcut_config_path(), custom)

    def test_private_shortcut_save_is_atomic(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "Config" / "shortcuts.json"
            save_shortcuts(DEFAULT_SHORTCUTS, destination)
            self.assertTrue(destination.exists())
            self.assertFalse(destination.with_suffix(".json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
