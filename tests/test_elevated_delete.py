from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import mdir.elevation as elevation
from mdir.elevation import (
    _FOFX_RECYCLEONDELETE,
    _FOFX_REQUIREELEVATION,
    _FOFX_SHOWELEVATIONPROMPT,
    _GUID,
    _guid,
    _operation_flags,
    _partition_delete_paths,
)
from mdir.file_operations import (
    RecycleBinError,
    is_access_denied_error,
    recycle_bin_error_message,
    run_file_operation,
)


class ElevatedDeleteTests(unittest.TestCase):
    def test_shell_code_0x78_is_administrator_permission(self) -> None:
        message = recycle_bin_error_message(0x78)
        self.assertIn("Administrator permission", message)
        self.assertTrue(
            is_access_denied_error(RecycleBinError(0x78, message))
        )

    def test_delete_collects_access_denied_separately(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            victim = Path(temp) / "protected.txt"
            victim.write_text("protected", encoding="utf-8")
            with patch(
                "mdir.file_operations.send_to_recycle_bin",
                side_effect=RecycleBinError(
                    0x78,
                    "Administrator permission is required",
                ),
            ):
                result = run_file_operation("delete", [victim])

            self.assertEqual(result.completed, 0)
            self.assertEqual(result.errors, [])
            self.assertEqual(result.access_denied_items, [victim])
            self.assertEqual(result.access_denied_permanent_items, [])
            self.assertTrue(victim.exists())

    def test_elevated_policy_partitions_recycle_and_permanent(self) -> None:
        recycle = Path("protected-small.dat")
        permanent = Path("protected-huge.dat")
        recycle_batch, permanent_batch, keys = _partition_delete_paths(
            (recycle, permanent),
            (permanent,),
        )
        self.assertEqual(recycle_batch, (recycle,))
        self.assertEqual(permanent_batch, (permanent,))
        self.assertIn(
            __import__("os").path.normcase(__import__("os").path.abspath(permanent)),
            keys,
        )

    def test_recycle_flags_request_native_uac_and_recycle_bin(self) -> None:
        flags = _operation_flags(recycle=True)
        self.assertTrue(flags & _FOFX_SHOWELEVATIONPROMPT)
        self.assertTrue(flags & _FOFX_REQUIREELEVATION)
        self.assertTrue(flags & _FOFX_RECYCLEONDELETE)

    def test_permanent_flags_do_not_request_recycle_bin(self) -> None:
        flags = _operation_flags(recycle=False)
        self.assertTrue(flags & _FOFX_SHOWELEVATIONPROMPT)
        self.assertTrue(flags & _FOFX_REQUIREELEVATION)
        self.assertFalse(flags & _FOFX_RECYCLEONDELETE)

    def test_com_guid_layout_is_native_16_bytes(self) -> None:
        self.assertEqual(__import__("ctypes").sizeof(_GUID), 16)
        self.assertEqual(_guid(elevation._IID_IFILE_OPERATION).Data1, 0x947AAB5F)

    def test_administrator_retry_no_longer_uses_powershell(self) -> None:
        source = inspect.getsource(elevation).lower()
        self.assertNotIn("powershell.exe", source)
        self.assertNotIn("encodedcommand", source)
        self.assertIn("elevation:administrator!new:", source)
        self.assertIn("cogetobject", source)
        self.assertIn("shcreateitemfromparsingname", source)

    def test_uac_broker_is_owned_by_mdir_window(self) -> None:
        source = inspect.getsource(elevation._create_elevated_file_operation)
        self.assertIn("owner_hwnd", source)
        self.assertIn("options.hwnd = owner_hwnd or None", source)
        self.assertIn("_prepare_elevation_owner", source)

    def test_owner_window_is_forwarded_to_native_delete(self) -> None:
        signature = inspect.signature(elevation.run_elevated_delete)
        self.assertIn("owner_hwnd", signature.parameters)
        source = inspect.getsource(elevation.run_elevated_delete)
        self.assertGreaterEqual(source.count("owner_hwnd=owner_hwnd"), 2)

    def test_native_file_operation_sets_same_owner_window(self) -> None:
        source = inspect.getsource(elevation._run_native_shell_delete)
        self.assertIn("_IFILEOP_SET_OWNER_WINDOW", source)
        self.assertIn("operation_owner", source)


if __name__ == "__main__":
    unittest.main()
