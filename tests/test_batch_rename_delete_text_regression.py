"""Regression tests for batch removal of matching filename text."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mdir.ui.batch_rename import (
    BatchRenameOptions,
    BatchRenameScreen,
    apply_rename_pairs,
    build_rename_pairs,
)


class BatchDeleteTextTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def create_specs(self):
        items = []
        # The user's 21-file PDF/XLSX pattern: filename contains a redundant
        # "_Document.pdf" fragment before the real extension.
        for i in range(11):
            stem = f"SpecSheet_D{i:08d}_Document.pdf"
            for ext in ((".pdf", ".xlsx") if i < 10 else (".pdf",)):
                p = self.root / (stem + ext)
                p.write_bytes(("file:" + p.name).encode())
                items.append(p)
        return items

    def test_21_files_remove_substring_without_changing_real_extension(self):
        items = self.create_specs()
        options = BatchRenameOptions(
            find_text="_Document.pdf", delete_found_text=True
        )
        pairs, errors = build_rename_pairs(items, options)
        self.assertFalse(errors)
        self.assertEqual(len(pairs), 21)
        for pair in pairs:
            self.assertNotIn("_Document.pdf", pair.target.stem)
            self.assertEqual(pair.target.suffix, pair.source.suffix)
        apply_rename_pairs(pairs)
        self.assertTrue(all(pair.target.is_file() for pair in pairs))
        self.assertTrue(all(not pair.source.exists() for pair in pairs))

    def test_replace_mode_remains_supported(self):
        p = self.root / "foo_old.txt"
        p.touch()
        options = BatchRenameOptions(
            find_text="_old", replace_text="_new", delete_found_text=False
        )
        pairs, errors = build_rename_pairs([p], options)
        self.assertFalse(errors)
        self.assertEqual(pairs[0].target.name, "foo_new.txt")

    def test_default_ui_is_explicit_delete_mode(self):
        screen = BatchRenameScreen([])
        self.assertTrue(screen.delete_found_text)

    def test_collision_blocks_without_renaming_files(self):
        p = self.root / "foo_old.txt"
        conflict = self.root / "foo.txt"
        p.write_bytes(b"original")
        conflict.write_bytes(b"existing")
        pairs, errors = build_rename_pairs(
            [p], BatchRenameOptions(find_text="_old", delete_found_text=True)
        )
        self.assertFalse(pairs)
        self.assertTrue(errors)
        self.assertEqual(p.read_bytes(), b"original")
        self.assertEqual(conflict.read_bytes(), b"existing")


if __name__ == "__main__":
    unittest.main()
