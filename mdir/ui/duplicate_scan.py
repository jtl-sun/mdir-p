"""Visible, cancellable progress for recursive duplicate scans.

Progress display is read-only: pressing Cancel only stops scanning. It never
deletes, relocates, edits or marks any discovered file.
"""
from __future__ import annotations

from pathlib import Path
from threading import Event

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static


class DuplicateScanProgressScreen(ModalScreen[None]):
    CSS = """
    DuplicateScanProgressScreen {
        align: center middle;
        background: #00000088;
    }
    #duplicate_scan_dialog {
        width: 84%;
        max-width: 110;
        height: 19;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }
    #duplicate_scan_title { height: 1; text-style: bold; }
    #duplicate_scan_root { height: 3; color: $text-muted; }
    #duplicate_scan_phase { height: 4; color: $foreground; }
    #duplicate_scan_help { height: 3; color: $text-muted; }
    #duplicate_scan_actions { height: 3; align-horizontal: right; }
    #duplicate_scan_actions Button { min-width: 20; }
    """

    def __init__(self, root: Path, cancel_event: Event) -> None:
        super().__init__()
        self.root = root
        self.cancel_event = cancel_event
        self.progress_count = 0
        self.progress_phase = "Starting recursive file scan..."

    def compose(self) -> ComposeResult:
        with Vertical(id="duplicate_scan_dialog"):
            yield Label("Duplicate Search — IN PROGRESS", id="duplicate_scan_title")
            yield Static(
                f"Search root: {self.root}\nIncludes this directory and all accessible subdirectories.",
                id="duplicate_scan_root",
            )
            yield Static(self.progress_phase, id="duplicate_scan_phase")
            yield Static(
                "The Duplicate Review results window opens automatically after "
                "SHA-256 verification and optional similar-image matching finish.\n"
                "No files will be deleted or changed.",
                id="duplicate_scan_help",
            )
            with Horizontal(id="duplicate_scan_actions"):
                yield Button("Cancel Scan", id="duplicate_scan_cancel", variant="error")

    def on_mount(self) -> None:
        self.query_one("#duplicate_scan_cancel", Button).focus()

    def update_progress(self, count: int, description: str) -> None:
        self.progress_count = count
        self.progress_phase = description
        if self.is_mounted:
            self.query_one("#duplicate_scan_phase", Static).update(description)

    def request_cancel(self) -> None:
        if self.cancel_event.is_set():
            return
        self.cancel_event.set()
        self.progress_phase = (
            "Cancellation requested. Stopping after the current file operation. "
            "No results from an incomplete scan will be used."
        )
        if self.is_mounted:
            self.query_one("#duplicate_scan_phase", Static).update(self.progress_phase)
            self.query_one("#duplicate_scan_cancel", Button).disabled = True

    @on(Button.Pressed, "#duplicate_scan_cancel")
    def cancel_clicked(self, event: Button.Pressed) -> None:
        event.stop()
        self.request_cancel()

    def key_escape(self) -> None:
        self.request_cancel()
