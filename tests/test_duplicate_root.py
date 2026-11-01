"""Drive-root duplicate finder scope and inaccessible-subtree regressions."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from mdir.advanced import find_exact_duplicates
from mdir.base import BaseApp


class DuplicateRootSelectionTests(unittest.TestCase):
    def test_drive_root_scope_does_not_follow_highlighted_child(self):
        # Runs on Windows CI and Linux: the action must pass its *current*
        # directory, not the selected subfolder, to the worker.
        root = Path("G:\\")
        child = root / "Music"
        pane = SimpleNamespace(current_path=root, selected_path=Mock(return_value=child))
        caller = SimpleNamespace(
            active=pane, active_side="left",
            CONFIRM_SCREEN=Mock(return_value=object()),
            push_screen=Mock(), set_status=Mock(),
            _run_duplicate_search=Mock(),
        )
        BaseApp.action_find_duplicates(caller)
        message = caller.CONFIRM_SCREEN.call_args.args[0]
        self.assertIn(str(root), message)
        self.assertIn("ALL subfolders", message)
        callback = caller.push_screen.call_args.args[1]
        callback(True)
        caller._run_duplicate_search.assert_called_once_with(root, "left")
        pane.selected_path.assert_not_called()

    def test_nested_active_folder_still_searches_its_own_descendants(self):
        root = Path("G:\\") / "Music" / "Classical"
        pane = SimpleNamespace(current_path=root, selected_path=Mock(return_value=root / "Mozart"))
        caller = SimpleNamespace(
            active=pane, active_side="right",
            CONFIRM_SCREEN=Mock(return_value=object()),
            push_screen=Mock(), set_status=Mock(),
            _run_duplicate_search=Mock(),
        )
        BaseApp.action_find_duplicates(caller)
        caller.push_screen.call_args.args[1](True)
        caller._run_duplicate_search.assert_called_once_with(root, "right")
        pane.selected_path.assert_not_called()


class RecursiveDuplicateEngineTests(unittest.TestCase):
    def test_searches_root_siblings_and_deep_descendants(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            one = root / "Music" / "Classical"
            two = root / "AudioBooks" / "Narration"
            one.mkdir(parents=True)
            two.mkdir(parents=True)
            files = (root / "track.m4a", one / "another-name.mp3", two / "same-content.bin")
            for file in files:
                file.write_bytes(b"same bytes across folder depths")
            (two / "unique.txt").write_bytes(b"unique")
            stats = {}
            errors = []
            groups = find_exact_duplicates(root, scan_stats=stats, scan_errors=errors)
            self.assertEqual(len(groups), 1)
            self.assertEqual(set(groups[0]), set(files))
            self.assertEqual(stats["files_scanned"], 4)
            self.assertEqual(stats["files_hashed"], 3)
            self.assertEqual(errors, [])

    def test_reports_unreadable_subfolders_instead_of_silent_success(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            item = root / "available.txt"
            item.write_bytes(b"available")
            blocked = root / "System Volume Information"

            def fake_walk(start, *, onerror, followlinks):
                self.assertEqual(start, root)
                self.assertFalse(followlinks)
                onerror(PermissionError(13, "Access is denied", str(blocked)))
                yield str(root), [], [item.name]

            errors = []
            stats = {}
            with patch("mdir.advanced.os.walk", side_effect=fake_walk):
                groups = find_exact_duplicates(root, scan_errors=errors, scan_stats=stats)
            self.assertFalse(groups)
            self.assertEqual(stats["files_scanned"], 1)
            self.assertEqual(len(errors), 1)
            self.assertIn("System Volume Information", errors[0])

    def test_missing_root_is_reported_not_silently_empty(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(NotADirectoryError):
                find_exact_duplicates(Path(folder) / "missing-drive")


if __name__ == "__main__":
    unittest.main()
