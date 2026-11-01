"""Safety-first, paginated duplicate review; never deletes or moves a file."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Label, Static

from ..duplicate_review import DuplicateReviewStore, export_duplicate_report
from .prompt import CompactPromptScreen


class DuplicateReviewScreen(ModalScreen[Path | None]):
    """Record deliberate copies, request a later review, or flag a candidate.

    Candidate is a note only. No delete, hard-link, relocation, or file
    transformation is available on this screen.
    """

    PAGE_SIZE = 150
    CSS = """
    DuplicateReviewScreen { align: center middle; background: #00000088; }
    #duplicate_dialog {
        width: 97%; height: 92%; border: solid $primary;
        background: $surface; padding: 1 2;
    }
    #duplicate_title { height: 1; color: $foreground; text-style: bold; }
    #duplicate_summary { height: 3; color: $foreground; }
    #duplicate_warnings { height: 2; color: $warning; text-overflow: ellipsis; }
    #duplicate_table { height: 1fr; min-height: 4; }
    #duplicate_page, #duplicate_feedback { height: 1; color: $text-muted; }
    #duplicate_actions_primary, #duplicate_actions_secondary {
        height: 3; align-horizontal: right;
    }
    #duplicate_actions_primary Button,
    #duplicate_actions_secondary Button {
        min-width: 12; height: 3; margin-left: 1;
    }
    """

    def __init__(
        self,
        root: Path,
        results: list[tuple[str, Path, int]],
        exact_groups: int,
        similar_groups: int,
        store_path: Path,
        scan_warnings: list[str] | None = None,
        scan_stats: dict[str, int] | None = None,
    ) -> None:
        super().__init__()
        self.root = root
        self.results = results
        self.exact_groups = exact_groups
        self.similar_groups = similar_groups
        self.store = DuplicateReviewStore(store_path)
        self.scan_warnings = list(scan_warnings or ())
        self.scan_stats = dict(scan_stats or {})
        self.page = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="duplicate_dialog"):
            yield Label("Duplicate Review — NO AUTOMATIC DELETION", id="duplicate_title")
            yield Static(
                f"Recursive scope: {self.root} (root + all accessible subfolders)\n"
                f"Scanned {self.scan_stats.get('files_scanned', 0):,} files; "
                f"SHA-256 hashed {self.scan_stats.get('files_hashed', 0):,}. "
                f"{self.exact_groups:,} exact groups; {self.similar_groups:,} similar "
                f"image groups (max 5,000 images). {len(self.results):,} rows.\n"
                "Keep = intentional copy; Candidate = label only. No automatic deletion.",
                id="duplicate_summary",
            )
            yield Static(
                (
                    f"INCOMPLETE: {len(self.scan_warnings):,} inaccessible file/folder(s) "
                    f"were skipped. First: {self.scan_warnings[0]}"
                    if self.scan_warnings
                    else "Scan finished with no reported filesystem access errors."
                ),
                id="duplicate_warnings",
            )
            yield DataTable(
                id="duplicate_table", cursor_type="row", zebra_stripes=False
            )
            yield Static("", id="duplicate_page")
            yield Static("Select a file to review. Location opens its original folder.", id="duplicate_feedback")
            with Horizontal(id="duplicate_actions_primary"):
                yield Button("Keep", id="duplicate_keep")
                yield Button("Candidate", id="duplicate_candidate")
                yield Button("Review", id="duplicate_review")
                yield Button("Add Note", id="duplicate_note")
                yield Button("Location", id="duplicate_location")
            with Horizontal(id="duplicate_actions_secondary"):
                yield Button("Prev", id="duplicate_prev")
                yield Button("Next", id="duplicate_next")
                yield Button("Export CSV", id="duplicate_export")
                yield Button("Close", id="duplicate_close")

    def on_mount(self) -> None:
        table = self.query_one("#duplicate_table", DataTable)
        table.add_columns("Group", "Status", "File name", "Original folder", "Bytes", "Note")
        self._show_page()
        if self.results:
            table.focus()

    def _show_page(self, *, select_row: int = 0) -> None:
        table = self.query_one("#duplicate_table", DataTable)
        table.clear(columns=False)
        start = self.page * self.PAGE_SIZE
        end = min(start + self.PAGE_SIZE, len(self.results))
        for group, path, size in self.results[start:end]:
            decision = self.store.get(path)
            status = ("REVIEW*" if decision.changed else decision.status.upper())
            table.add_row(
                group, status, path.name, str(path.parent),
                f"{size:,}", decision.note[:55],
            )
        self.query_one("#duplicate_page", Static).update(
            f"Showing {start + 1 if self.results else 0:,}–{end:,} of "
            f"{len(self.results):,} | Page {self.page + 1:,} / "
            f"{max(1, (len(self.results) + self.PAGE_SIZE - 1) // self.PAGE_SIZE):,}"
        )
        self.query_one("#duplicate_prev", Button).disabled = self.page == 0
        self.query_one("#duplicate_next", Button).disabled = end >= len(self.results)
        for button_id in ("duplicate_keep", "duplicate_candidate", "duplicate_review",
                          "duplicate_note", "duplicate_location"):
            self.query_one(f"#{button_id}", Button).disabled = not self.results
        if table.row_count:
            table.move_cursor(row=min(select_row, table.row_count - 1), column=0)

    def _selected(self) -> tuple[str, Path, int] | None:
        table = self.query_one("#duplicate_table", DataTable)
        index = self.page * self.PAGE_SIZE + table.cursor_row
        return self.results[index] if 0 <= index < len(self.results) else None

    def _feedback(self, message: str) -> None:
        self.query_one("#duplicate_feedback", Static).update(message)

    def _label_selected(self, label: str, note: str | None = None) -> None:
        chosen = self._selected()
        if chosen is None:
            return
        try:
            decision = self.store.set(chosen[1], label, note)
        except (OSError, ValueError) as exc:
            self._feedback(f"Could not save review: {exc}")
            return
        selected_row = self.query_one("#duplicate_table", DataTable).cursor_row
        self._show_page(select_row=selected_row)
        self._feedback(
            f"Saved {decision.status.upper()} for {chosen[1].name}. "
            "No file was moved or deleted."
        )

    def _edit_note(self) -> None:
        chosen = self._selected()
        if chosen is None:
            return
        path = chosen[1]
        existing = self.store.get(path)

        def saved(value: str | None) -> None:
            if value is None:
                return
            # Preserve status; notes are stored per full path and file metadata.
            self._label_selected(existing.status, value)

        self.app.push_screen(
            CompactPromptScreen("Reason for keeping / reviewing this copy:", existing.note),
            saved,
        )

    @on(Button.Pressed)
    def button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        button_id = event.button.id
        if button_id in {"duplicate_keep", "duplicate_candidate", "duplicate_review"}:
            self._label_selected(button_id.removeprefix("duplicate_"))
        elif button_id == "duplicate_note":
            self._edit_note()
        elif button_id == "duplicate_location":
            chosen = self._selected()
            if chosen is not None:
                self.dismiss(chosen[1])
        elif button_id == "duplicate_prev" and self.page > 0:
            self.page -= 1
            self._show_page()
        elif button_id == "duplicate_next":
            if (self.page + 1) * self.PAGE_SIZE < len(self.results):
                self.page += 1
                self._show_page()
        elif button_id == "duplicate_export":
            name = datetime.now().strftime("duplicates-%Y%m%d-%H%M%S-%f.csv")
            report = self.store.path.parent / "reports" / name
            try:
                count = export_duplicate_report(report, self.results, self.store)
            except (OSError, ValueError) as exc:
                self._feedback(f"CSV export failed: {exc}")
            else:
                self._feedback(f"Exported {count:,} rows to {report}")
        elif button_id == "duplicate_close":
            self.dismiss(None)

    @on(DataTable.RowSelected, "#duplicate_table")
    def row_selected(self, event: DataTable.RowSelected) -> None:
        event.stop()
        chosen = self._selected()
        if chosen is not None:
            self.dismiss(chosen[1])

    def key_escape(self) -> None:
        self.dismiss(None)
