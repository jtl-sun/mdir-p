from pathlib import Path
import json
import os
import tempfile
import unittest
from unittest.mock import patch

import mdir.shortcuts as shortcuts_module
from mdir.shortcuts import (
    CONFIG_ENVIRONMENT_VARIABLE,
    INSTALL_ROOT_ENVIRONMENT_VARIABLE,
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

    def test_default_config_is_inside_install_root(self):
        with tempfile.TemporaryDirectory() as directory:
            local_app_data = Path(directory)
            with patch.dict(
                os.environ,
                {
                    "LOCALAPPDATA": str(local_app_data),
                    CONFIG_ENVIRONMENT_VARIABLE: "",
                    INSTALL_ROOT_ENVIRONMENT_VARIABLE: "",
                },
                clear=False,
            ):
                self.assertEqual(
                    shortcut_config_path(),
                    local_app_data / "mDIR" / "Config" / "shortcuts.json",
                )

    def test_22637_private_location_migrates_before_home_legacy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous = root / "mDIR-P" / "Config" / "shortcuts.json"
            legacy = root / ".mdir-p-shortcuts.json"
            destination = root / "mDIR" / "Config" / "shortcuts.json"
            previous.parent.mkdir(parents=True)
            previous.write_text(
                json.dumps([
                    {
                        "label": "Previous",
                        "type": "folder",
                        "target": r"E:\\Work",
                        "args": [],
                        "pane": "active",
                    }
                ]),
                encoding="utf-8",
            )
            legacy.write_text(
                json.dumps([
                    {
                        "label": "Older",
                        "type": "folder",
                        "target": r"D:\\Old",
                        "args": [],
                        "pane": "active",
                    }
                ]),
                encoding="utf-8",
            )
            with patch.object(
                shortcuts_module,
                "previous_private_config_path",
                return_value=previous,
            ), patch.object(shortcuts_module, "LEGACY_CONFIG_PATH", legacy):
                result = migrate_legacy_shortcut_config(destination)
            self.assertEqual(result, destination)
            loaded = load_shortcuts(destination)
            self.assertEqual(loaded[0].label, "Previous")
            self.assertTrue(previous.exists())
            self.assertTrue(legacy.exists())

    def test_environment_override_remains_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            custom = Path(directory) / "my-links.json"
            with patch.dict(os.environ, {CONFIG_ENVIRONMENT_VARIABLE: str(custom)}):
                self.assertEqual(shortcut_config_path(), custom)

    def test_installer_and_link_manager_expose_config_folder(self):
        root = Path(__file__).resolve().parents[1]
        installer = (root / "install_windows.ps1").read_text(encoding="utf-8")
        manager = (root / "mdir" / "ui" / "shortcuts.py").read_text(encoding="utf-8")
        self.assertIn('$ConfigRoot = Join-Path $InstallRoot "Config"', installer)
        self.assertIn("ensure_shortcut_config", installer)
        self.assertIn("Open Config Folder", manager)
        self.assertIn("Config: {self.config_path}", manager)

    def test_private_shortcut_save_is_atomic(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "Config" / "shortcuts.json"
            save_shortcuts(DEFAULT_SHORTCUTS, destination)
            self.assertTrue(destination.exists())
            self.assertFalse(destination.with_suffix(".json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
