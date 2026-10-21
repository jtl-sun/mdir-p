from __future__ import annotations

import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from mdir import office_pdf_preview as office


def write_valid_pdf(path: Path) -> None:
    # Enough structure for the cache validator; page rendering is tested by the
    # existing Preview tests with real PyMuPDF fixtures.
    path.write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF\n")


class _FakeSession:
    def __init__(self):
        self.stage = "startup"
        self.error = ""
        self.calls = []
        self.stopped = False

    def render(self, source, target, *, cancel=None, timeout=None, layout=True):
        self.calls.append((Path(source), Path(target), layout))
        self.stage = "export"
        if cancel is not None and cancel.is_set():
            self.error = "cancelled"
            return False
        write_valid_pdf(Path(target))
        return True

    def stop(self):
        self.stopped = True


class OfficePdfPreviewTests(unittest.TestCase):
    def setUp(self):
        office.shutdown_office_pdf_preview()
        diagnostic = patch.object(office, '_diagnostic')
        diagnostic.start()
        self.addCleanup(diagnostic.stop)

    def tearDown(self):
        office.shutdown_office_pdf_preview()

    def test_cache_key_changes_when_source_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "sample.xlsx"
            source.write_bytes(b"first")
            with patch.dict(os.environ, {"LOCALAPPDATA": str(root)}):
                first = office.office_pdf_cache_path(source)
                time.sleep(0.002)
                source.write_bytes(b"second-version")
                os.utime(source, None)
                second = office.office_pdf_cache_path(source)
            self.assertNotEqual(first, second)

    def test_cached_pdf_is_reused_without_starting_office(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "cached.docx"
            source.write_bytes(b"word")
            with patch.dict(os.environ, {"LOCALAPPDATA": str(root)}):
                cached = office.office_pdf_cache_path(source)
                cached.parent.mkdir(parents=True, exist_ok=True)
                write_valid_pdf(cached)
                with patch.object(office, "_get_session") as get_session:
                    result = office.render_office_pdf_cached(source)
                self.assertTrue(result.ok)
                self.assertTrue(result.from_cache)
                self.assertEqual(result.backend, "cache")
                self.assertEqual(result.pdf_path, cached)
                get_session.assert_not_called()

    def test_first_excel_render_publishes_cache_and_next_is_cache_hit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "book.xlsx"
            source.write_bytes(b"xlsx-placeholder")
            fake = _FakeSession()
            with patch.dict(os.environ, {"LOCALAPPDATA": str(root)}), patch.object(
                office, "_SESSION", fake
            ):
                first = office.render_office_pdf_cached(source)
                second = office.render_office_pdf_cached(source)
            self.assertTrue(first.ok)
            self.assertFalse(first.from_cache)
            self.assertEqual(first.backend, "Microsoft Excel")
            self.assertEqual(len(fake.calls), 1)
            self.assertTrue(second.ok)
            self.assertTrue(second.from_cache)
            self.assertEqual(second.pdf_path, first.pdf_path)

    def test_powerpoint_uses_same_cached_pdf_pipeline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "deck.pptx"
            source.write_bytes(b"pptx-placeholder")
            fake = _FakeSession()
            with patch.dict(os.environ, {"LOCALAPPDATA": str(root)}), patch.object(
                office, "_SESSION", fake
            ):
                first = office.render_office_pdf_cached(source)
                second = office.render_office_pdf_cached(source)
            self.assertEqual(office.office_kind(source), "powerpoint")
            self.assertTrue(first.ok)
            self.assertFalse(first.from_cache)
            self.assertEqual(first.backend, "Microsoft PowerPoint")
            self.assertEqual(len(fake.calls), 1)
            self.assertTrue(second.from_cache)
            self.assertEqual(second.pdf_path, first.pdf_path)

    def test_cancel_function_signals_active_conversion(self):
        event = threading.Event()
        with office._ACTIVE_LOCK:
            office._ACTIVE_CANCELS.add(event)
        try:
            office.cancel_office_pdf_preview()
            self.assertTrue(event.is_set())
        finally:
            with office._ACTIVE_LOCK:
                office._ACTIVE_CANCELS.discard(event)


if __name__ == "__main__":
    unittest.main()
