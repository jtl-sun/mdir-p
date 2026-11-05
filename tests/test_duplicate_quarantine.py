"""Tests for duplicate quarantine: keeper protection, collisions and journals."""
from __future__ import annotations

import csv
import hashlib
import tempfile
import unittest
from pathlib import Path

from mdir.duplicate_quarantine import (
    move_marked_to_quarantine, next_quarantine_path, smart_select_duplicates,
)
from mdir.duplicate_review import DuplicateReviewStore


class QuarantineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "files"
        self.root.mkdir()
        self.quarantine = Path(self.temp.name) / "quarantine"
        self.quarantine.mkdir()
        self.store = DuplicateReviewStore(Path(self.temp.name) / "reviews.json")

    def make_group(self, count=3, name="Track.mp3"):
        rows = []
        for index in range(count):
            folder = self.root / f"source{index}"
            folder.mkdir(exist_ok=True)
            path = folder / name
            path.write_bytes(b"same identical content")
            rows.append(("Exact 1", path, path.stat().st_size))
        return rows

    def test_smart_select_keeps_one(self):
        rows = self.make_group()
        picked = smart_select_duplicates(rows, self.store)
        self.assertEqual(len(picked), 2)
        self.assertEqual(len([row for row in rows if row not in picked]), 1)

    def test_explicit_keep_wins(self):
        rows = self.make_group()
        self.store.set(rows[2][1], "keep")
        picked = smart_select_duplicates(rows, self.store)
        self.assertEqual({row[1] for row in picked}, {rows[0][1], rows[1][1]})

    def test_unique_names_and_preserve_original(self):
        rows = self.make_group()
        (self.quarantine / "Track.mp3").write_bytes(b"already there")
        (self.quarantine / "Track-(01).mp3").write_bytes(b"already there too")
        selected = smart_select_duplicates(rows, self.store)
        moved, errors, journal = move_marked_to_quarantine(
            self.root, rows, selected, self.store, self.quarantine
        )
        self.assertEqual(errors, [])
        self.assertEqual(len(moved), 2)
        self.assertTrue((self.quarantine / "Track-(02).mp3").is_file())
        self.assertTrue((self.quarantine / "Track-(03).mp3").is_file())
        self.assertEqual((self.quarantine / "Track.mp3").read_bytes(), b"already there")
        self.assertEqual(sum(int(row[1].is_file()) for row in rows), 1)
        with journal.open(encoding="utf-8-sig", newline="") as stream:
            entries = list(csv.DictReader(stream))
        self.assertEqual(len(entries), 2)
        self.assertEqual({e["status"] for e in entries}, {"MOVED"})
        self.assertEqual({e["original_path"] for e in entries},
                         {str(row[1]) for row in selected})

    def test_all_copies_marked_is_blocked(self):
        rows = self.make_group(2)
        with self.assertRaises(ValueError):
            move_marked_to_quarantine(
                self.root, rows, rows, self.store, self.quarantine
            )
        self.assertTrue(all(row[1].exists() for row in rows))

    def test_changed_file_is_not_moved(self):
        rows = self.make_group(2)
        selected = smart_select_duplicates(rows, self.store)
        selected[0][1].write_bytes(b"not equal anymore")
        moved, failures, _ = move_marked_to_quarantine(
            self.root, rows, selected, self.store, self.quarantine
        )
        self.assertEqual(moved, [])
        self.assertTrue(failures)
        self.assertTrue(all(row[1].is_file() for row in rows))

    def test_similar_images_are_never_selected(self):
        rows = self.make_group(2)
        rows = [("Similar 1", p, size) for _, p, size in rows]
        self.assertEqual(smart_select_duplicates(rows, self.store), [])

    def test_quarantine_tree_is_excluded_from_future_scans(self):
        from mdir.advanced import find_exact_duplicates
        rows = self.make_group()
        selected = smart_select_duplicates(rows, self.store)
        moved, failures, _journal = move_marked_to_quarantine(
            self.root, rows, selected, self.store, self.root / "Quarantine"
        )
        self.assertFalse(failures)
        self.assertEqual(len(moved), 2)
        self.assertTrue((self.root / "Quarantine" / ".mdir-quarantine-folder").exists())
        self.assertEqual(find_exact_duplicates(self.root), [])

    def test_collision_suffix_preserves_extension(self):
        file = self.root / "archive.tar.gz"
        (self.quarantine / file.name).write_bytes(b"x")
        self.assertEqual(next_quarantine_path(self.quarantine, file).name,
                         "archive.tar-(01).gz")


if __name__ == "__main__":
    unittest.main()
