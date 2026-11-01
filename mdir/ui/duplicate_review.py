"""Paginated duplicate review with confirmed, recycle-bin-only single deletion."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from threading import Event
from rich.text import Text
from textual.binding import Binding

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Label, Static

from ..duplicate_review import DuplicateReviewStore, export_duplicate_report
from ..duplicate_cleanup import (
    recycle_selected_exact_duplicate,
    plan_marked_exact_duplicates,
    recycle_marked_exact_duplicates,
)
from .dialogs import CompactConfirmScreen
from .prompt import CompactPromptScreen


class DuplicateReviewScreen(ModalScreen[Path | None]):
    """Compare exact copies, label them, or safely recycle one selected copy.

    Candidate and Keep are notes only; recycling needs a separate confirmation.
    Similar-image matches and final remaining copies cannot be recycled here.
    """

    PAGE_SIZE = 150
    MAX_BATCH = 100
    BINDINGS = [
        Binding("space", "toggle_mark", "Mark file", show=False, priority=True),
        Binding("shift+up", "mark_up", "Extend marks up", show=False, priority=True),
        Binding("shift+down", "mark_down", "Extend marks down", show=False, priority=True),
    ]
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
    #duplicate_feedback { height: 4; color: $foreground; }
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
        self._batch_running = False
        self._predelete_report: Path | None = None
        self._marked: set[tuple[str, Path]] = set()
        self._batch_stop = Event()
        self._operation_message = ""

    def compose(self) -> ComposeResult:
        with Vertical(id="duplicate_dialog"):
            yield Label("Duplicate Review — CONFIRMED RECYCLE BIN ONLY", id="duplicate_title")
            yield Static(
                f"Recursive scope: {self.root} (root + all accessible subfolders)\n"
                f"Scanned {self.scan_stats.get('files_scanned', 0):,} files; "
                f"SHA-256 hashed {self.scan_stats.get('files_hashed', 0):,}. "
                f"{self.exact_groups:,} exact groups; {self.similar_groups:,} similar "
                f"image groups (max 5,000 images). {len(self.results):,} rows.\n"
                "Keep is protected. Click rows or press Space to mark; "
                "Shift+Up/Down marks a range. No automatic deletion.",
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
                yield Button("Mark Row", id="duplicate_mark")
                yield Button("Clear Marks", id="duplicate_clear_marks")
                yield Button("Delete Marked", id="duplicate_delete_marked", variant="error")
                yield Button("Stop Cleanup", id="duplicate_stop_cleanup")
                yield Button("Prev", id="duplicate_prev")
                yield Button("Next", id="duplicate_next")
                yield Button("Export CSV", id="duplicate_export")
                yield Button("Close", id="duplicate_close")

    def on_mount(self) -> None:
        table = self.query_one("#duplicate_table", DataTable)
        table.add_column("Mark", width=8)
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
                Text("✓ MARK", style="bold green") if (group, path) in self._marked
                else Text("—", style="dim"),
                group, status,
                Text(path.name, style="bold" if (group, path) in self._marked else ""),
                str(path.parent),
                f"{size:,}", decision.note[:55],
            )
        self.query_one("#duplicate_page", Static).update(
            f"Showing {start + 1 if self.results else 0:,}–{end:,} of "
            f"{len(self.results):,} | Marked: {len(self._marked):,} | "
            f"Page {self.page + 1:,} / "
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
        """Keep important warnings visible; highlighting a row must not erase them."""
        self._operation_message = message
        self.query_one("#duplicate_feedback", Static).update(message)

    def _show_selected_details(self) -> None:
        chosen = self._selected()
        button = self.query_one("#duplicate_delete", Button)
        batch_button = self.query_one("#duplicate_delete_marked", Button)
        batch_button.disabled = self._recycling or not self._marked
        batch_button.label = f"Delete Marked ({len(self._marked):,})"
        self.query_one("#duplicate_mark", Button).disabled = self._recycling or chosen is None
        self.query_one("#duplicate_clear_marks", Button).disabled = (
            self._recycling or not self._marked
        )
        self.query_one("#duplicate_stop_cleanup", Button).disabled = not self._batch_running
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
        safe, blocked = plan_marked_exact_duplicates(
            self.results, self._marked, self.store
        ) if self._marked else ([], [])
        summary = (
            f"Marked: {len(self._marked):,} | Eligible to recycle: {len(safe):,} "
            f"| Protected/unavailable: {len(self._marked) - len(safe):,}"
        )
        warning = (
            " | All selected copies in a group? Unmark one to keep."
            if self._marked and not safe else ""
        )
        details = (
            f"Selected: {group} | {path}\n"
            f"{summary}{warning}\n"
            f"Other available copies for this row: {other_copies:,}. "
            "Keep an unmarked copy per group."
        )
        self.query_one("#duplicate_feedback", Static).update(
            f"{self._operation_message}\n{details}"
            if self._operation_message else details
        )

    def _toggle_marked_row(self, row: tuple[str, Path, int] | None) -> bool:
        """Mark one exact duplicate for a later explicitly confirmed batch."""
        if self._recycling or row is None:
            return False
        group, path, _size = row
        key = (group, path)
        if key in self._marked:
            self._marked.remove(key)
            return True
        decision = self.store.get(path)
        if not group.startswith("Exact "):
            self._feedback("Similar images are not byte-identical. Cannot mark for deletion.")
            return False
        if decision.status == "keep" or decision.changed:
            self._feedback("KEEP or changed files are protected. Review first.")
            return False
        if not path.is_file() or path.is_symlink():
            self._feedback(f"File is missing or a symlink: {path}")
            return False
        self._marked.add(key)
        return True

    def action_toggle_mark(self) -> None:
        if self.focused is not self.query_one("#duplicate_table", DataTable) and (
            self.focused is not self.query_one("#duplicate_mark", Button)
        ):
            # Space is reserved for the result list, not other buttons.
            return
        table = self.query_one("#duplicate_table", DataTable)
        row = table.cursor_row
        if self._toggle_marked_row(self._selected()):
            self._operation_message = ""
            self._show_page(select_row=row)

    def _mark_direction(self, step: int) -> None:
        table = self.query_one("#duplicate_table", DataTable)
        if self.focused is not table or self._recycling or not table.row_count:
            return
        current = table.cursor_row
        dest = max(0, min(current + step, table.row_count - 1))
        selected = self._selected()
        if selected is not None and (selected[0], selected[1]) not in self._marked:
            self._toggle_marked_row(selected)
        index = self.page * self.PAGE_SIZE + dest
        if index < len(self.results):
            next_row = self.results[index]
            if (next_row[0], next_row[1]) not in self._marked:
                self._toggle_marked_row(next_row)
        self._operation_message = ""
        self._show_page(select_row=dest)

    def action_mark_up(self) -> None:
        self._mark_direction(-1)

    def action_mark_down(self) -> None:
        self._mark_direction(1)

    def _confirm_recycle_marked(self) -> None:
        if self._recycling or not self._marked:
            return
        safe, skipped = plan_marked_exact_duplicates(
            self.results, self._marked, self.store
        )
        if not safe:
            self._feedback(
                f"Nothing can be recycled: {skipped[0] if skipped else 'No safe rows.'}"
            )
            return
        if len(safe) > self.MAX_BATCH:
            self._feedback(
                f"Marked {len(safe):,} eligible files. Maximum is "
                f"{self.MAX_BATCH} per confirmation; unmark some first."
            )
            return
        total_bytes = sum(row[2] for row in safe)
        paths = "\n".join(str(row[1]) for row in safe[:8])
        more = f"\n... plus {len(safe) - 8} more marked paths" if len(safe) > 8 else ""
        warning = (
            f"\n{len(skipped)} selected files will NOT be recycled. "
            f"First: {skipped[0]}"
            if skipped else ""
        )
        message = (
            f"Recycle {len(safe):,} MARKED EXACT files ({total_bytes:,} bytes)?\n"
            "Each group MUST retain at least one UNMARKED file.\n"
            "Selected files (first 8; all paths saved to CSV):\n"
            f"{paths}{more}{warning}\n"
            "Each file is reverified with SHA-256 before recycling.\n"
            "Windows Recycle Bin only. Links to old paths may break.\n"
            "Do you want to continue?"
        )
        def confirmed(ok: bool) -> None:
            if not ok:
                return
            self._batch_stop.clear()
            self._recycling = True
            self._batch_running = True
            self._show_selected_details()
            self._feedback(f"Recycling 0/{len(safe):,} marked files ...")
            self._run_recycle_marked(tuple(safe))

        self.app.push_screen(
            CompactConfirmScreen(
                message, title="Recycle Marked Exact Duplicates?",
                yes_label="Recycle Marked", cancel_label="Cancel",
            ),
            confirmed,
        )

    def _batch_progress(self, done: int, total: int, path: Path) -> None:
        self._feedback(
            f"Recycling marked duplicates: {done:,}/{total:,} "
            f"({100 * done / total:.1f}%)\nLast processed: {path}"
        )

    @work(
        thread=True, exclusive=True, group="duplicate-marked-recycle",
        exit_on_error=False,
    )
    def _run_recycle_marked(self, chosen: tuple[tuple[str, Path, int], ...]) -> None:
        try:
            report = self.store.path.parent / "reports" / (
                "duplicate-precleanup-batch-"
                + datetime.now().strftime("%Y%m%d-%H%M%S-%f")
                + ".csv"
            )
            export_duplicate_report(report, self.results, self.store)
            self._predelete_report = report
            succeeded, failed = recycle_marked_exact_duplicates(
                self.root, self.results, chosen, self.store,
                cancel_event=self._batch_stop,
                on_progress=lambda index, total, path: self.app.call_from_thread(
                    self._batch_progress, index, total, path
                ),
            )
        except (OSError, ValueError) as exc:
            self.app.call_from_thread(self._recycle_failed, str(exc))
            return
        self.app.call_from_thread(
            self._batch_completed, succeeded, failed, report,
        )

    def _batch_completed(
        self,
        succeeded: list[tuple[str, Path, int]],
        failures: list[str],
        report: Path,
    ) -> None:
        self._recycling = False
        self._batch_running = False
        row_position = self.query_one("#duplicate_table", DataTable).cursor_row
        for row in succeeded:
            try:
                self.results.remove(row)
            except ValueError:
                pass
            self._marked.discard((row[0], row[1]))
        self.page = min(
            self.page, max(0, (len(self.results) - 1) // self.PAGE_SIZE)
        )
        self._show_page(select_row=row_position)
        self._feedback(
            f"Batch complete: {len(succeeded):,} recycled, "
            f"{len(failures):,} not recycled. CSV: {report}\n"
            + (f"First issue: {failures[0]}" if failures else
               "Remaining original copies were protected.")
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
        if decision.status == "keep":
            self._marked.discard((chosen[0], chosen[1]))
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
            f"Move THIS ONE FILE to the Windows Recycle Bin?\n"
            f"File: {path}\n"
            f"Size: {size:,} bytes | Group: {group}\n"
            f"Another copy to keep: {others[0]}\n"
            "The content will be verified again. Other files remain untouched.\n"
            "A CSV report of all scanned duplicates is saved first.\n"
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
        self._batch_running = False
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
        self._marked.discard((chosen[0], chosen[1]))
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
        if self._recycling and button_id != "duplicate_stop_cleanup":
            self._feedback("Recycling is still in progress; review controls are locked.")
            return
        if button_id in {"duplicate_keep", "duplicate_candidate", "duplicate_review"}:
            self._label_selected(button_id.removeprefix("duplicate_"))
        elif button_id == "duplicate_note":
            self._edit_note()
        elif button_id == "duplicate_delete":
            self._confirm_recycle_selected()
        elif button_id == "duplicate_mark":
            self.action_toggle_mark()
        elif button_id == "duplicate_clear_marks":
            self._marked.clear()
            self._show_page(
                select_row=self.query_one("#duplicate_table", DataTable).cursor_row
            )
        elif button_id == "duplicate_delete_marked":
            self._confirm_recycle_marked()
        elif button_id == "duplicate_stop_cleanup":
            self._batch_stop.set()
            self._feedback("Stop requested: finishing the current file safely.")
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
        # Click/Enter toggles a marked file without leaving the result screen.
        event.stop()
        self.action_toggle_mark()

    @on(DataTable.RowHighlighted, "#duplicate_table")
    def row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        event.stop()
        self._show_selected_details()

    def key_escape(self) -> None:
        if not self._recycling:
            self.dismiss(None)
