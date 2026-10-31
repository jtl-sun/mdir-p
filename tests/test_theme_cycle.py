"""Regression coverage for rapid theme cycling and active-pane contrast."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mdir.app import MDirApp
from mdir.theme import (
    THEME_NAME,
    OLD_M_THEME_NAME,
    NORTON_THEME_NAME,
    MDIR_THEME,
    install_file_colors,
    selection_colors,
)


EXPECTED_BACKGROUNDS = {
    THEME_NAME: ("#191919", "#292929"),
    OLD_M_THEME_NAME: ("#000000", "#202020"),
    NORTON_THEME_NAME: ("#171752", "#0000aa"),
}
EXPECTED_SKINS = {
    THEME_NAME: "skin-modern",
    OLD_M_THEME_NAME: "skin-original",
    NORTON_THEME_NAME: "skin-norton",
    "textual-light": "skin-light",
}
ALL_SKINS = frozenset(EXPECTED_SKINS.values())


class ThemeCycleTests(unittest.IsolatedAsyncioTestCase):
    def tearDown(self) -> None:
        # The file renderer is shared at module scope across application tests.
        install_file_colors(MDIR_THEME)

    def assert_active_pane_colors(self, app: MDirApp, theme_name: str) -> None:
        self.assertEqual(app.theme, theme_name)
        expected_skin = EXPECTED_SKINS.get(theme_name)
        for pane in (app.left, app.right):
            self.assertEqual(
                {skin for skin in ALL_SKINS if pane.has_class(skin)},
                {expected_skin} if expected_skin else set(),
            )
        if theme_name not in EXPECTED_BACKGROUNDS:
            return
        active_color, passive_color = EXPECTED_BACKGROUNDS[theme_name]
        active = app.left if app.active_side == "left" else app.right
        passive = app.right if app.active_side == "left" else app.left
        self.assertEqual(active.styles.background.hex.lower(), active_color)
        self.assertEqual(passive.styles.background.hex.lower(), passive_color)
        self.assertEqual(active.table.styles.background.hex.lower(), active_color)
        self.assertEqual(passive.table.styles.background.hex.lower(), passive_color)

    async def test_rapid_switches_keep_last_skin_and_focus_contrast(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "folder").mkdir()
            (root / "test.zip").write_bytes(b"data")
            with (
                patch("mdir.app.load_theme_name", return_value=THEME_NAME),
                patch("mdir.app.save_theme_name") as save_theme,
            ):
                app = MDirApp()
                app.left_start = root
                app.right_start = root
                app._save_paths = lambda: None

                async with app.run_test(size=(120, 35)) as pilot:
                    for _ in range(100):
                        if app.left.initial_listing_complete:
                            break
                        await pilot.pause(0.02)

                    self.assert_active_pane_colors(app, THEME_NAME)

                    # Exercise the custom skins, built-ins, and their return
                    # paths. Previously the custom pane surfaces could revert.
                    for name in (
                        NORTON_THEME_NAME, "dracula", OLD_M_THEME_NAME,
                        "ansi-light", THEME_NAME, "tokyo-night",
                        OLD_M_THEME_NAME, "rose-pine", NORTON_THEME_NAME,
                        "textual-light", THEME_NAME,
                    ):
                        app.theme = name
                        await pilot.pause()
                        await pilot.pause()
                        self.assert_active_pane_colors(app, name)

                    # Switch without an intervening frame: queued callbacks
                    # for older selections must not restore obsolete skins.
                    for name in (
                        OLD_M_THEME_NAME, NORTON_THEME_NAME, "gruvbox",
                        THEME_NAME, "nord", OLD_M_THEME_NAME,
                    ):
                        app.theme = name
                    await pilot.pause()
                    await pilot.pause()
                    self.assert_active_pane_colors(app, OLD_M_THEME_NAME)
                    self.assertEqual(selection_colors(active=True)[0], "#ff5a61")
                    self.assertEqual(save_theme.call_args.args[0], OLD_M_THEME_NAME)

                    # Both the pane background and filename selection should
                    # follow the new focus side without changing the theme.
                    app.set_active("right")
                    await pilot.pause()
                    self.assert_active_pane_colors(app, OLD_M_THEME_NAME)

                    app.theme = NORTON_THEME_NAME
                    await pilot.pause()
                    await pilot.pause()
                    self.assert_active_pane_colors(app, NORTON_THEME_NAME)
                    self.assertEqual(selection_colors(active=True)[0], "#55ffff")

                    app.set_active("left")
                    await pilot.pause()
                    self.assert_active_pane_colors(app, NORTON_THEME_NAME)
                    app.exit()


if __name__ == "__main__":
    unittest.main()
