from __future__ import annotations

import os
import sys
import tempfile
import unittest
import json
from pathlib import Path

from mdir.app import MDirApp
from mdir.preview.native import (
    PaneLayout,
    WindowRectangle,
    calculate_pane_rectangle,
)
from mdir.text_actions import DEFAULT_VIEW_LIMIT, inspect_safe_text_file
from mdir.shortcuts import (
    DEFAULT_SHORTCUTS,
    ShortcutDefinition,
    ensure_shortcut_config,
    expand_shortcut_text,
    load_shortcuts,
    parse_shortcuts,
    save_shortcuts,
)
from mdir.ui.shortcuts import ShortcutManagerScreen
from mdir import core as legacy


class PackageSmokeTests(unittest.IsolatedAsyncioTestCase):
    def test_current_widgets_are_connected_without_monkey_patching(self) -> None:
        from mdir import core
        from mdir.base import BaseApp
        from mdir.ui.dialogs import CompactConfirmScreen
        from mdir.ui.prompt import CompactPromptScreen
        from mdir.ui.rename import SlowRenameDataTable
        from mdir.ui.viewer import CompactViewerScreen

        self.assertIsNot(core.MDirDataTable, SlowRenameDataTable)
        self.assertIs(BaseApp.PROMPT_SCREEN, CompactPromptScreen)
        self.assertIs(BaseApp.CONFIRM_SCREEN, CompactConfirmScreen)
        self.assertIs(BaseApp.VIEWER_SCREEN, CompactViewerScreen)

    async def test_shift_range_and_fast_right_drag_do_not_skip_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = [root / f"item-{index:02d}.txt" for index in range(10)]
            for path in files:
                path.write_text(path.name, encoding="utf-8")

            app = MDirApp()
            app.left_start = root
            app.right_start = root
            app._save_paths = lambda: None

            async with app.run_test(size=(120, 35)) as pilot:
                for _ in range(100):
                    if app.left.initial_listing_complete:
                        break
                    await pilot.pause(0.02)

                pane = app.left
                start_row = pane.row_by_path[files[1]]
                end_row = pane.row_by_path[files[8]]
                pane.table.move_cursor(row=start_row, column=0)
                pane.reset_shift_selection_anchor()

                app.set_active("left")
                pane.table.focus()
                await pilot.press("shift+down")
                self.assertEqual(
                    pane.marked,
                    {pane.entries[start_row], pane.entries[start_row + 1]},
                )

                pane.marked.clear()
                pane.table.move_cursor(row=start_row, column=0)
                pane.reset_shift_selection_anchor()
                pane.select_range_to(end_row)

                expected = {
                    path
                    for path in pane.entries[start_row : end_row + 1]
                    if path is not None
                }
                self.assertEqual(pane.marked, expected)
                self.assertEqual(pane.table.cursor_row, end_row)

                pane.marked.clear()
                pane.reset_shift_selection_anchor()
                pane.table._drag_rows_seen.clear()
                pane.table._right_drag_last_row = None
                pane.table._toggle_drag_range_to(start_row)
                pane.table._toggle_drag_range_to(end_row)
                self.assertEqual(pane.marked, expected)
                app.exit()

    async def test_right_drag_auto_scroll_continues_selection_beyond_page(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = [root / f"item-{index:03d}.txt" for index in range(80)]
            for path in files:
                path.write_text(path.name, encoding="utf-8")

            app = MDirApp()
            app.left_start = root
            app.right_start = root
            app._save_paths = lambda: None

            async with app.run_test(size=(100, 18)) as pilot:
                for _ in range(100):
                    if app.left.initial_listing_complete:
                        break
                    await pilot.pause(0.02)

                pane = app.left
                table = pane.table
                start_row = pane.row_by_path[files[2]]
                table._right_dragging = True
                table._drag_rows_seen.clear()
                table._right_drag_last_row = None
                table._toggle_drag_range_to(start_row)
                table._right_drag_scroll_direction = 1

                steps = table.size.height + 5
                for _ in range(steps):
                    table._right_drag_auto_scroll_tick()
                    await pilot.pause(0)

                end_row = start_row + steps
                expected = {
                    path
                    for path in pane.entries[start_row : end_row + 1]
                    if path is not None
                }
                self.assertEqual(pane.marked, expected)
                self.assertEqual(table.cursor_row, end_row)
                self.assertGreater(int(table.scroll_offset.y), 0)
                table.end_right_drag()
                app.exit()

    def test_filename_and_extension_are_visually_separated(self) -> None:
        path = Path("sample.design.png")
        self.assertEqual(
            legacy.display_file_title(path, is_directory=False),
            "sample.design",
        )
        self.assertEqual(legacy.display_extension(".png"), "   png")
        self.assertEqual(
            legacy.display_file_title(Path("folder.name"), is_directory=True),
            "folder.name",
        )

    async def test_both_panels_auto_refresh_after_external_delete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            victim = root / "delete-me.txt"
            victim.write_text("temporary", encoding="utf-8")

            app = MDirApp()
            app.left_start = root
            app.right_start = root
            app._save_paths = lambda: None

            async with app.run_test(size=(100, 24)) as pilot:
                for _ in range(100):
                    if (
                        app.left.initial_listing_complete
                        and app.right.initial_listing_complete
                        and victim in app.left.entries
                        and victim in app.right.entries
                    ):
                        break
                    await pilot.pause(0.02)

                self.assertIn(victim, app.left.entries)
                self.assertIn(victim, app.right.entries)
                victim.unlink()

                for _ in range(100):
                    if (
                        victim not in app.left.entries
                        and victim not in app.right.entries
                    ):
                        break
                    await pilot.pause(0.03)

                self.assertNotIn(victim, app.left.entries)
                self.assertNotIn(victim, app.right.entries)
                app.exit()

    async def test_pane_details_remain_visible_below_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "folder"
            folder.mkdir()

            app = MDirApp()
            app.left_start = root
            app.right_start = root
            app._save_paths = lambda: None

            async with app.run_test(size=(100, 22)) as pilot:
                for _ in range(100):
                    if app.left.initial_listing_complete:
                        break
                    await pilot.pause(0.02)

                app.left.table.move_cursor(
                    row=app.left.row_by_path[folder],
                    column=0,
                )
                app.left.update_info()
                await pilot.pause()

                summary = app.left.query_one(".pane_summary")
                details = app.left.query_one(".pane_info")
                summary_text = str(summary.render())
                self.assertTrue(details.visible)
                self.assertEqual(summary.content_region.height, 1)
                self.assertIn("Capacity:", summary_text)
                self.assertIn("Files:", summary_text)
                self.assertIn("Folders:", summary_text)
                self.assertEqual(details.region.height, 3)
                self.assertEqual(details.content_region.height, 3)
                self.assertEqual(details.region.y, summary.region.bottom)
                self.assertLessEqual(details.region.bottom, app.left.region.bottom)
                self.assertIn("Name: folder", str(details.render()))
                self.assertIn(f"Path: {folder}", str(details.render()))
                app.exit()

    async def test_shortcut_bar_and_folder_navigation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "destination"
            destination.mkdir()

            app = MDirApp()
            app.left_start = root
            app.right_start = root
            app.shortcuts = [
                ShortcutDefinition(
                    "Destination",
                    "folder",
                    str(destination),
                    pane="right",
                )
            ]
            app._save_paths = lambda: None

            async with app.run_test(size=(100, 32)) as pilot:
                for _ in range(100):
                    if app.left.initial_listing_complete:
                        break
                    await pilot.pause(0.02)

                button = app.query_one("#shortcut_0")
                self.assertTrue(button.display)
                self.assertEqual(str(button.label), "Destination")

                await app._activate_shortcut(app.shortcuts[0])
                self.assertEqual(app.right.current_path, destination.resolve())
                self.assertEqual(app.active_side, "right")

                await pilot.click("#shortcut_edit")
                await pilot.pause(0.05)
                self.assertIsInstance(app.screen, ShortcutManagerScreen)
                await pilot.click("#shortcut_cancel")
                await pilot.pause(0.05)
                self.assertNotIsInstance(app.screen, ShortcutManagerScreen)
                app.exit()

    async def test_ai_panel_is_loaded_only_when_requested(self) -> None:
        app = MDirApp()
        self.assertNotIn("mdir.ai.panel", sys.modules)

        async with app.run_test(size=(120, 35)) as pilot:
            await pilot.pause(0.05)
            self.assertFalse(list(app.query("#ai_panel")))

            await app.action_toggle_ai_terminal()
            await pilot.pause(0.05)
            self.assertTrue(app.ai_mode)
            self.assertEqual(len(list(app.query("#ai_panel"))), 1)

            await app.action_toggle_ai_terminal()
            await pilot.pause(0.05)
            self.assertFalse(app.ai_mode)
            self.assertTrue(app.right.table.has_focus)
            app.exit()

    async def test_listing_and_theme_switch(self) -> None:
        previous = os.environ.get("MDIR_NATIVE_PREVIEW")
        os.environ["MDIR_NATIVE_PREVIEW"] = "0"
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "folder").mkdir()
                (root / "note.txt").write_text(
                    "hello",
                    encoding="utf-8",
                )

                app = MDirApp()
                app.left_start = root
                app.right_start = root
                app._save_paths = lambda: None

                async with app.run_test(size=(120, 35)) as pilot:
                    for _ in range(100):
                        if (
                            app.left.initial_listing_complete
                            and len(app.left.entries) >= 3
                        ):
                            break
                        await pilot.pause(0.02)

                    self.assertIn(root / "folder", app.left.entries)
                    self.assertIn(root / "note.txt", app.left.entries)
                    self.assertEqual(
                        app.left.styles.background.hex,
                        "#202020",
                    )

                    app.theme = "textual-light"
                    await pilot.pause()
                    await pilot.pause()
                    self.assertEqual(
                        app.left.styles.background.hex,
                        "#E0E0E0",
                    )
                    app.exit()
        finally:
            if previous is None:
                os.environ.pop("MDIR_NATIVE_PREVIEW", None)
            else:
                os.environ["MDIR_NATIVE_PREVIEW"] = previous

    async def test_preview_toggle_preserves_file_navigation(self) -> None:
        previous = os.environ.get("MDIR_NATIVE_PREVIEW")
        os.environ["MDIR_NATIVE_PREVIEW"] = "0"
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                image = root / "preview.png"
                image.write_bytes(b"\x89PNG\r\n\x1a\n")

                app = MDirApp()
                app.left_start = root
                app.right_start = root
                app._save_paths = lambda: None

                async with app.run_test(size=(120, 35)) as pilot:
                    for _ in range(100):
                        if app.left.initial_listing_complete:
                            break
                        await pilot.pause(0.02)

                    app.left.table.move_cursor(
                        row=app.left.row_by_path[image],
                        column=0,
                    )
                    app.set_active("left")
                    app.action_toggle_preview()
                    await pilot.pause(0.05)

                    self.assertTrue(app.preview_enabled)
                    self.assertTrue(app.preview_mode)
                    self.assertTrue(app.left.table.has_focus)
                    self.assertTrue(app.right.disabled)

                    await pilot.pause(0.25)
                    app.action_toggle_preview()
                    await pilot.pause(0.05)
                    self.assertFalse(app.preview_enabled)
                    self.assertFalse(app.preview_mode)
                    self.assertFalse(app.right.disabled)
                    app.exit()
        finally:
            if previous is None:
                os.environ.pop("MDIR_NATIVE_PREVIEW", None)
            else:
                os.environ["MDIR_NATIVE_PREVIEW"] = previous

    def test_safe_text_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            text = root / "note.md"
            image = root / "photo.jpg"
            text.write_text("# MDIR", encoding="utf-8")
            image.write_bytes(b"\xff\xd8\xff\xe0binary")

            self.assertTrue(
                inspect_safe_text_file(
                    text,
                    max_bytes=DEFAULT_VIEW_LIMIT,
                ).allowed
            )
            self.assertEqual(
                inspect_safe_text_file(
                    image,
                    max_bytes=DEFAULT_VIEW_LIMIT,
                ).reason,
                "unsupported_type",
            )

    def test_native_preview_geometry(self) -> None:
        terminal = WindowRectangle(100, 50, 2_100, 1_250)
        pane = PaneLayout(
            x=80,
            y=3,
            width=70,
            height=38,
            columns=150,
            rows=45,
        )
        rectangle = calculate_pane_rectangle(terminal, pane)
        self.assertGreater(rectangle.width, 800)
        self.assertGreater(rectangle.height, 700)

    def test_shortcut_configuration(self) -> None:
        values = [
            {"label": "Docs", "type": "folder", "target": "{home}\\Documents"},
            {"label": "Site", "type": "web", "target": "https://example.com"},
            {"label": "Invalid", "type": "unknown", "target": "ignored"},
        ]
        parsed = parse_shortcuts(values)
        self.assertEqual([item.label for item in parsed], ["Docs", "Site"])

        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "shortcuts.json"
            ensure_shortcut_config(config_path)
            self.assertEqual(load_shortcuts(config_path), list(DEFAULT_SHORTCUTS))

            config_path.write_text(json.dumps(values), encoding="utf-8")
            self.assertEqual(
                [item.label for item in load_shortcuts(config_path)],
                ["Docs", "Site"],
            )
            save_shortcuts(parsed, config_path)
            self.assertEqual(load_shortcuts(config_path), parsed)

        expanded = expand_shortcut_text(
            "{project}|{current}|{left}|{right}",
            current=Path("C:/Current"),
            left=Path("C:/Left"),
            right=Path("D:/Right"),
            project=Path("S:/MDIR"),
        )
        self.assertIn(str(Path("S:/MDIR")), expanded)
        self.assertIn(str(Path("C:/Current")), expanded)


if __name__ == "__main__":
    unittest.main()
