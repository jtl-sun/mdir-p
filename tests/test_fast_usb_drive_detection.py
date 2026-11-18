"""Fast, non-blocking drive-letter discovery regression tests."""
from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from mdir import core
from mdir import fast_app


class WindowsDriveEnumerationTests(unittest.TestCase):
    def test_windows_drive_mask_never_reads_usb_filesystem(self):
        # Simulate three mappings (C, G, H) with one possibly sleeping USB.
        fake_kernel = Mock()
        fake_kernel.GetLogicalDrives.return_value = (
            (1 << 2) | (1 << 6) | (1 << 7)
        )
        with patch.object(core.os, "name", "nt"), \
             patch("ctypes.windll", create=True) as win, \
             patch.object(core.shutil, "disk_usage", side_effect=AssertionError(
                 "drive discovery must never read disk capacity"
             )):
            win.kernel32 = fake_kernel
            self.assertEqual(core.list_windows_drives(), ["C:", "G:", "H:"])
        fake_kernel.GetLogicalDrives.assert_called_once()
        fake_kernel.GetDriveTypeW.assert_not_called()

    def test_empty_or_failed_drive_mask(self):
        fake_kernel = Mock()
        fake_kernel.GetLogicalDrives.return_value = 0
        with patch.object(core.os, "name", "nt"), \
             patch("ctypes.windll", create=True) as win:
            win.kernel32 = fake_kernel
            self.assertEqual(core.list_windows_drives(), [])
        fake_kernel.GetLogicalDrives.side_effect = OSError("win error")
        with patch.object(core.os, "name", "nt"), \
             patch("ctypes.windll", create=True) as win:
            win.kernel32 = fake_kernel
            self.assertEqual(core.list_windows_drives(), [])

    def test_non_windows_has_no_drive_letters(self):
        with patch.object(core.os, "name", "posix"):
            self.assertEqual(core.list_windows_drives(), [])

    def test_hotplug_poll_interval_is_short(self):
        self.assertLessEqual(fast_app.DRIVE_POLL_INTERVAL_SECONDS, 3)


if __name__ == "__main__":
    unittest.main()
