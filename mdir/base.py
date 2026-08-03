from __future__ import annotations

import os
import shutil
from typing import Optional

from . import core as legacy
from .ime import enable_windows_korean_width_compatibility
from .shell import AIShellApp
from .ui.dialogs import (
    CompactConfirmScreen,
    CompactCopyScreen,
    CompactDriveScreen,
    CopyRequest,
)
from .ui.prompt import CompactPromptScreen
from .ui.viewer import CompactViewerScreen


KOREAN_WIDTH_COMPATIBILITY = enable_windows_korean_width_compatibility()

def windows_volume_label(drive: str) -> str:
    """Return a Windows volume label without querying drive capacity."""
    if os.name != "nt":
        return ""

    try:
        import ctypes

        label_buffer = ctypes.create_unicode_buffer(261)
        success = ctypes.windll.kernel32.GetVolumeInformationW(
            f"{drive.rstrip(chr(92))}\\",
            label_buffer,
            len(label_buffer),
            None,
            None,
            None,
            None,
            0,
        )
        if success:
            return label_buffer.value.strip()
    except Exception:
        pass
    return ""


class BaseApp(AIShellApp):
    """Application layer that selects the current dialogs explicitly."""

    PROMPT_SCREEN = CompactPromptScreen
    CONFIRM_SCREEN = CompactConfirmScreen
    VIEWER_SCREEN = CompactViewerScreen
    TITLE = "MDIR-P"
    SUB_TITLE = "Dual Pane File Manager / Codex AI / Visible Korean IME Cursor"

    def action_copy(self) -> None:
        """Copy selected items, with Save As support for a single item."""
        items = self.active.selected_items()
        if not items:
            self.set_status("Nothing selected.")
            return

        destination = self.passive.current_path

        def copy_requested(request: Optional[CopyRequest]) -> None:
            if request is None:
                self.set_status("Copy cancelled.")
                return

            errors: list[str] = []
            copied_names: list[str] = []
            for src in items:
                target_name = (
                    request.new_name
                    if len(items) == 1 and request.new_name
                    else src.name
                )
                dst = destination / target_name
                try:
                    if src.resolve() == dst.resolve():
                        errors.append(
                            f"{src.name}: source and destination are identical"
                        )
                        continue
                    if src.is_dir():
                        shutil.copytree(src, dst, dirs_exist_ok=True)
                    else:
                        shutil.copy2(src, dst)
                    copied_names.append(target_name)
                except Exception as exc:
                    errors.append(f"{src.name}: {exc}")

            self.active.marked.clear()
            self.active.refresh_listing()
            self.passive.refresh_listing(
                keep_name=copied_names[0] if len(copied_names) == 1 else None
            )

            if errors:
                self.set_status("Copy errors: " + " | ".join(errors[:2]))
            else:
                self.set_status(
                    f"Copied {len(items)} item(s) to {destination}"
                )

        self.push_screen(
            CompactCopyScreen(items, destination),
            copy_requested,
        )

    def _prompt_drive(self, pane: legacy.FilePane) -> None:
        """Select an available drive from a dropdown instead of typing it."""
        drives = legacy.list_windows_drives()
        if drives:
            self.available_drives = drives
            self._sync_drive_buttons()
            self.update_hidden_buttons()
        else:
            drives = list(self.available_drives)

        if not drives:
            self.set_status("No available drives were found.")
            return

        current_drive = (pane.current_path.drive or drives[0]).upper()
        choices = [
            (
                f"{drive}  {windows_volume_label(drive) or '(No label)'}",
                drive,
            )
            for drive in drives
        ]

        def drive_selected(drive: Optional[str]) -> None:
            if not drive:
                self.set_status("Drive selection cancelled.")
                return
            self.switch_pane_to_drive(pane, drive)

        self.push_screen(
            CompactDriveScreen(choices, current_drive),
            drive_selected,
        )
