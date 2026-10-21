from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import mdir.file_operations as file_operations


class LongPathCopyTests(unittest.TestCase):
    def test_windows_extended_path_prefixes_drive_and_unc(self) -> None:
        with patch.object(file_operations, "_IS_WINDOWS", True):
            self.assertEqual(
                file_operations._windows_extended_path(r"C:\work\deep\file.txt"),
                r"\\?\C:\work\deep\file.txt",
            )
            self.assertEqual(
                file_operations._windows_extended_path(r"\\server\share\deep\file.txt"),
                r"\\?\UNC\server\share\deep\file.txt",
            )

    def test_staging_name_is_short_and_does_not_repeat_target_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / ("VeryLongUnityProjectName" * 4)
            staging = file_operations._temporary_sibling(target, "copy")
            backup = file_operations._temporary_sibling(target, "backup")
            self.assertLessEqual(len(staging.name), 18)
            self.assertLessEqual(len(backup.name), 18)
            self.assertTrue(staging.name.startswith(".~mc-"))
            self.assertTrue(backup.name.startswith(".~mb-"))
            self.assertNotIn(target.name, staging.name)

    def test_copy2_retries_transient_windows_path_error_only(self) -> None:
        class WinPathError(OSError):
            winerror = 3

        calls: list[int] = []

        def flaky_copy(src, dst, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise WinPathError("path temporarily unavailable")
            return dst

        with (
            patch.object(file_operations, "_IS_WINDOWS", True),
            patch.object(file_operations, "_windows_extended_path", side_effect=lambda p: str(p)),
            patch.object(file_operations, "_is_retryable_copy_error", return_value=True),
            patch.object(file_operations.shutil, "copy2", side_effect=flaky_copy),
            patch.object(file_operations, "sleep"),
        ):
            result = file_operations._copy2_with_retry("source", "target")

        self.assertEqual(result, "target")
        self.assertEqual(len(calls), 2)

    def test_normal_copy_does_not_retry_or_sleep(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(file_operations, "sleep") as sleep_mock,
        ):
            root = Path(directory)
            source = root / "source.txt"
            destination = root / "out"
            destination.mkdir()
            source.write_text("data", encoding="utf-8")

            result = file_operations.run_file_operation(
                "copy", (source,), destination
            )

            self.assertEqual(result.completed, 1)
            self.assertFalse(result.errors)
            self.assertEqual((destination / "source.txt").read_text(), "data")
            sleep_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
