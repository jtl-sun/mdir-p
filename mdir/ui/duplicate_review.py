"""Paginated duplicate review with confirmed, recycle-bin-only single deletion."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Label, Static

from ..duplicate_review import DuplicateReviewStore, export_duplicate_report
from ..duplicate_cleanup import recycle_selected_exact_duplicate
from .dialogs import CompactConfirmScreen
from .prompt import CompactPromptScreen


class DuplicateReviewScreen(ModalScreen[Path | None]):
    """Compare exact copies, label them, or safely recycle one selected copy.

    Candidate and Keep are notes only; recycling needs a separate confirmation.
    Similar-image matches and final remaining copies cannot be recycled here.
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
    #duplicate_page { height: 1; color: $text-muted; }
    #duplicate_feedback { height: 2; color: $text-muted; }
    #duplicate_actions_primary, #duplicate_actions_secondary {
        height: 3; align-horizontal: right;
    }
    #duplicate_actions_primary Button,
    #duplicate_actions_secondary Button {
        min-width: 11; height: 3; margin-left: 1;
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
        self._recycling = False
        self._predelete_report: Path | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="duplicate_dialog"):
            yield Label("Duplicate Review — CONFIRMED RECYCLE BIN ONLY", id="duplicate_title")
            yield Static(
                f"Recursive scope: {self.root} (root + all accessible subfolders)\n"
                f"Scanned {self.scan_stats.get('files_scanned', 0):,} files; "
                f"SHA-256 hashed {self.scan_stats.get('files_hashed', 0):,}. "
                f"{self.exact_groups:,} exact groups; {self.similar_groups:,} similar "
                f"image groups (max 5,000 images). {len(self.results):,} rows.\n"
                "Keep = protected; Candidate = label only; Delete Selected needs confirmation.",
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
            yield Static("Select a row to compare its full path. Only confirmed Exact duplicates can be recycled.", id="duplicate_feedback")
            with Horizontal(id="duplicate_actions_primary"):
                yield Button("Keep", id="duplicate_keep")
                yield Button("Candidate", id="duplicate_candidate")
                yield Button("Review", id="duplicate_review")
                yield Button("Add Note", id="duplicate_note")
                yield Button("Location", id="duplicate_location")
                yield Button("Delete Selected", id="duplicate_delete", variant="error")
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
        self._show_selected_details()

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
        self._show_selected_details()

    def _selected(self) -> tuple[str, Path, int] | None:
        table = self.query_one("#duplicate_table", DataTable)
        index = self.page * self.PAGE_SIZE + table.cursor_row
        return self.results[index] if 0 <= index < len(self.results) else None

    def _feedback(self, message: str) -> None:
        self.query_one("#duplicate_feedback", Static).update(message)

    def _show_selected_details(self) -> None:
        chosen = self._selected()
        button = self.query_one("#duplicate_delete", Button)
        button.disabled = self._recycling or chosen is None
        if chosen is None:
            return
        group, path, _ = chosen
        decision = self.store.get(path)
        other_copies = sum(
            1 for item_group, other, _ in self.results
            if item_group == group and other != path and other.is_file()
        )
        button.disabled = (
            self._recycling or not group.startswith("Exact ")
            or decision.status == "keep" or decision.changed
            or other_copies == 0
        )
        self._feedback(
            f"Selected: {group} | {path}\n"
            f"Other listed copies: {other_copies} | "
            "Delete sends this file to Windows Recycle Bin after verification."
        )

    def _label_selected(self, label: str, note: str | None = None) -> None:
        if self._recycling:
            self._feedback("A selected duplicate is being recycled; finish first.")
            return
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

    def _confirm_recycle_selected(self) -> None:
        chosen = self._selected()
        if chosen is None or self._recycling:
            return
        group, path, size = chosen
        if not group.startswith("Exact "):
            self._feedback("Only SHA-256 verified Exact groups can be recycled.")
            return
        if self.store.get(path).status == "keep":
            self._feedback("This file is KEEP. Change it to Review or Candidate first.")
            return
        others = [
            candidate for other_group, candidate, _ in self.results
            if other_group == group and candidate != path and candidate.is_file()
        ]
        if not others:
            self._feedback("Cannot recycle the last remaining copy in a group.")
            return
        message = (
            f"Move THIS ONE FILE to the Windows Recycle Bin?\\n"
            f"File: {path}\\n"
            f"Size: {size:,} bytes | Group: {group}\\n"
            f"Another copy to keep: {others[0]}\\n"
            "The content will be verified again. Other files remain untouched.\\n"
            "A CSV report of all scanned duplicates is saved first.\\n"
            "This may break applications that reference the selected path."
        )
        def confirmed(ok: bool) -> None:
            if ok:
                self._recycling = True
                self._show_selected_details()
                self._feedback(f"Verifying content and moving to Recycle Bin: {path}")
                self._run_recycle_selected(chosen)

        self.app.push_screen(
            CompactConfirmScreen(
                message, title="Recycle Selected Duplicate?",
                yes_label="Recycle", cancel_label="Cancel",
            ),
            confirmed,
        )

    @work(thread=True, exclusive=True, group="duplicate-selected-recycle", exit_on_error=False)
    def _run_recycle_selected(self, chosen: tuple[str, Path, int]) -> None:
        try:
            if self._predelete_report is None:
                report = self.store.path.parent / "reports" / (
                    "duplicate-precleanup-"
                    + datetime.now().strftime("%Y%m%d-%H%M%S-%f")
                    + ".csv"
                )
                export_duplicate_report(report, self.results, self.store)
                self._predelete_report = report
            survivor = recycle_selected_exact_duplicate(
                self.root, self.results, chosen, self.store
            )
        except (OSError, ValueError) as exc:
            self.app.call_from_thread(self._recycle_failed, str(exc))
            return
        self.app.call_from_thread(self._recycle_completed, chosen, survivor)

    def _recycle_failed(self, message: str) -> None:
        self._recycling = False
        self._show_selected_details()
        self._feedback(f"NOT RECYCLED: {message}")

    def _recycle_completed(
        self, chosen: tuple[str, Path, int], survivor: Path
    ) -> None:
        self._recycling = False
        selected_row = self.query_one("#duplicate_table", DataTable).cursor_row
        try:
            self.results.remove(chosen)
        except ValueError:
            pass
        max_page = max(0, (len(self.results) - 1) // self.PAGE_SIZE)
        self.page = min(self.page, max_page)
        self._show_page(select_row=selected_row)
        self._feedback(
            f"Moved to Recycle Bin: {chosen[1]}\n"
            f"Remaining verified copy: {survivor} | "
            f"Pre-cleanup CSV: {self._predelete_report}"
        )

    @on(Button.Pressed)
    def button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        button_id = event.button.id
        if button_id in {"duplicate_keep", "duplicate_candidate", "duplicate_review"}:
            self._label_selected(button_id.removeprefix("duplicate_"))
        elif button_id == "duplicate_note":
            self._edit_note()
        elif button_id == "duplicate_delete":
            self._confirm_recycle_selected()
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
        # Selecting a row stays in Duplicate Review. Only Location navigates.
        event.stop()
        self._show_selected_details()

    @on(DataTable.RowHighlighted, "#duplicate_table")
    def row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        event.stop()
        self._show_selected_details()

    def key_escape(self) -> None:
        self.dismiss(None)
