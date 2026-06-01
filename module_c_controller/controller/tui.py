from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, Label, ListItem, ListView, Static, TextArea

from .config import Settings
from .models import Submission
from .repository import SubmissionRepository, build_repository
from .status import is_reviewed_status


class ReviewScreen(ModalScreen[tuple[float, str] | None]):
    CSS = """
    ReviewScreen {
        align: center middle;
    }

    #dialog {
        width: 70;
        height: auto;
        padding: 1 2;
        border: solid $accent;
        background: $surface;
    }

    #comment {
        height: 8;
    }

    #actions {
        height: auto;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+s", "submit", "Submit"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("Score")
            yield Input(placeholder="Numeric score, e.g. 92", id="score")
            yield Label("Comment")
            yield TextArea(id="comment")
            yield Static("Ctrl+s Submit, Esc Cancel, Tab Move Focus", classes="muted")
            with Horizontal(id="actions"):
                yield Button("Approve", id="approve", variant="success")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#score", Input).focus()

    def action_submit(self) -> None:
        self._submit_review()

    def action_cancel(self) -> None:
        self._cancel_review()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self._cancel_review()
            return

        if event.button.id == "approve":
            self._submit_review()

    def _cancel_review(self) -> None:
        self.dismiss(None)

    def _submit_review(self) -> None:
        score_input = self.query_one("#score", Input)
        comment_input = self.query_one("#comment", TextArea)
        try:
            score = float(score_input.value.strip())
        except ValueError:
            self.notify("Score must be a number", severity="error")
            score_input.focus()
            return

        comment = comment_input.text.strip()
        if not comment:
            self.notify("Comment is required", severity="error")
            comment_input.focus()
            return

        self.dismiss((score, comment))


class ApprovalApp(App[None]):
    CSS = """
    Screen {
        layout: vertical;
    }

    #body {
        height: 1fr;
    }

    #list-pane {
        width: 34;
        min-width: 24;
        border-right: solid $primary;
    }

    #detail-pane {
        width: 1fr;
        padding: 1 2;
    }

    #title {
        text-style: bold;
        margin-bottom: 1;
    }

    ListView {
        height: 1fr;
    }

    .muted {
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("p", "show_pending", "Pending"),
        Binding("a", "show_approved", "Approved"),
        Binding("l", "show_all", "All"),
        Binding("j,down", "cursor_down", "Down"),
        Binding("k,up", "cursor_up", "Up"),
        Binding("enter", "review_selected", "Review", priority=True),
    ]

    VIEW_TITLES = {
        "pending": "Pending Submissions",
        "approved": "Approved Submissions",
        "all": "All Submissions",
    }

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings
        self.repository: SubmissionRepository = build_repository(settings)
        self.submissions: list[Submission] = []
        self.current_view = "pending"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="body"):
            with Vertical(id="list-pane"):
                yield Static("Pending Submissions", id="title")
                yield ListView(id="submission-list")
            with Vertical(id="detail-pane"):
                yield Static("Select a submission", id="detail")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_submissions()

    def action_refresh(self) -> None:
        self.refresh_submissions()
        self.notify(f"{self.VIEW_TITLES[self.current_view]} refreshed")

    def action_show_pending(self) -> None:
        self.set_view("pending")

    def action_show_approved(self) -> None:
        self.set_view("approved")

    def action_show_all(self) -> None:
        self.set_view("all")

    def action_cursor_down(self) -> None:
        list_view = self.query_one("#submission-list", ListView)
        list_view.action_cursor_down()

    def action_cursor_up(self) -> None:
        list_view = self.query_one("#submission-list", ListView)
        list_view.action_cursor_up()

    def action_review_selected(self) -> None:
        selected = self.selected_submission
        if selected is None:
            self.notify("No submission selected", severity="warning")
            return
        if selected.status != "pending":
            self.notify("Only pending submissions can be reviewed.", severity="warning")
            return
        self.push_screen(ReviewScreen(), lambda result: self._handle_review(selected.id, result))

    @property
    def selected_submission(self) -> Submission | None:
        list_view = self.query_one("#submission-list", ListView)
        if list_view.index is None:
            return None
        if list_view.index < 0 or list_view.index >= len(self.submissions):
            return None
        return self.submissions[list_view.index]

    def set_view(self, view: str) -> None:
        self.current_view = view
        self.refresh_submissions()

    def refresh_submissions(self) -> None:
        status = None if self.current_view == "all" else self.current_view
        try:
            self.submissions = self.repository.list_submissions(status)
        except Exception as exc:
            self.notify(f"Failed to load submissions: {exc}", severity="error")
            self.submissions = []
        self.query_one("#title", Static).update(self.VIEW_TITLES[self.current_view])
        list_view = self.query_one("#submission-list", ListView)
        list_view.clear()
        for submission in self.submissions:
            label = f"{submission.id} | {submission.student_name} | {submission.assignment_title}"
            if self.current_view == "all":
                label = f"{label} | {submission.status}"
            list_view.append(ListItem(Label(label)))
        if self.submissions:
            list_view.index = 0
            self.render_detail(self.submissions[0])
        else:
            self.render_empty()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id != "submission-list":
            return
        selected = self.selected_submission
        if selected:
            self.render_detail(selected)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.id != "submission-list":
            return
        selected = self.selected_submission
        if selected:
            self.render_detail(selected)

    def render_empty(self) -> None:
        title = self.VIEW_TITLES[self.current_view].lower()
        self.query_one("#detail", Static).update(
            f"[b]No {title}[/b]\n\nPress p/a/l to switch views, r to refresh, or q to quit."
        )

    def render_detail(self, submission: Submission) -> None:
        review_detail = ""
        if is_reviewed_status(submission.status) or self.current_view == "approved":
            review_detail = f"""
Score: {submission.score}
Comment: {submission.comment}
Reviewed At: {submission.reviewed_at}
Feedback Path: {submission.feedback_path}
"""

        detail = f"""[b]{submission.assignment_title}[/b]

Submission ID: {submission.id}
Student ID: {submission.student_id}
Student Name: {submission.student_name}
Status: {submission.status}
Created At: {submission.created_at}
{review_detail}

[b]Content[/b]
{submission.content}
"""
        self.query_one("#detail", Static).update(detail)

    def _handle_review(
        self,
        submission_id: int,
        result: tuple[float, str] | None,
    ) -> None:
        if result is None:
            return
        score, comment = result
        submission = self.repository.get_submission(submission_id)
        if submission is None or submission.status != "pending":
            self.notify("Submission is no longer pending", severity="error")
            self.refresh_submissions()
            return

        try:
            updated = self.repository.grade_submission(
                submission.id,
                score,
                comment,
                status="graded",
            )
        except Exception as exc:
            self.notify(f"Failed to grade submission: {exc}", severity="error")
            self.refresh_submissions()
            return

        self.notify(f"Approved submission {updated.id}")
        self.refresh_submissions()
