from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys
import tarfile

from rich.markup import escape
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, Label, ListItem, ListView, Static, TextArea

from .config import Settings
from .models import Submission
from .repository import SubmissionRepository, build_repository
from .status import is_reviewed_status


@dataclass(frozen=True)
class DownloadedSubmission:
    archive_path: Path
    content_path: Path


READABLE_SUBMISSION_EXTENSIONS = {".md", ".txt"}
MAX_TUI_FILE_PREVIEW_CHARS = 200_000


def extract_submission_archive(archive_path: Path) -> Path:
    target_dir = archive_path.with_suffix("").with_suffix("")
    target_dir.mkdir(parents=True, exist_ok=True)
    resolved_target = target_dir.resolve()

    with tarfile.open(archive_path, "r:*") as tar:
        safe_members = []
        for member in tar.getmembers():
            member_path = (target_dir / member.name).resolve()
            if member_path != resolved_target and resolved_target not in member_path.parents:
                raise ValueError(f"Refusing to extract unsafe path: {member.name}")
            safe_members.append(member)
        tar.extractall(target_dir, members=safe_members)

    return target_dir


def open_path_in_system(path: Path) -> None:
    resolved = path.resolve()
    if sys.platform.startswith("win"):
        os.startfile(str(resolved))  # type: ignore[attr-defined]
        return

    command = ["open", str(resolved)] if sys.platform == "darwin" else ["xdg-open", str(resolved)]
    subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def find_readable_submission_file(content_path: Path) -> Path | None:
    if content_path.is_file():
        return content_path if content_path.suffix.lower() in READABLE_SUBMISSION_EXTENSIONS else None
    if not content_path.is_dir():
        return None

    candidates = [
        path
        for path in content_path.rglob("*")
        if path.is_file() and path.suffix.lower() in READABLE_SUBMISSION_EXTENSIONS
    ]
    if not candidates:
        return None

    def score(path: Path) -> tuple[int, int, str]:
        name = path.name.lower()
        priority = 0 if name in {"readme.md", "report.md", "answer.md"} else 1
        suffix_priority = 0 if path.suffix.lower() == ".md" else 1
        return (priority, suffix_priority, str(path.relative_to(content_path)).lower())

    return sorted(candidates, key=score)[0]


def read_preview_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if len(text) <= MAX_TUI_FILE_PREVIEW_CHARS:
        return text
    return (
        text[:MAX_TUI_FILE_PREVIEW_CHARS]
        + "\n\n[... file truncated for TUI preview ...]\n"
        + f"Full path: {path}"
    )


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

    def __init__(self, submission: Submission) -> None:
        super().__init__()
        self.submission = submission

    def compose(self) -> ComposeResult:
        assignment_label = self.submission.assignment_id or self.submission.assignment_title
        with Vertical(id="dialog"):
            yield Static(
                f"Submission {self.submission.id} | {assignment_label} | {self.submission.student_id}"
            )
            yield Label("Score")
            yield Input(placeholder="Numeric score, e.g. 92", id="score")
            yield Label("Comment")
            yield TextArea(id="comment")
            yield Static("Ctrl+s Submit, Esc Cancel, Tab Move Focus", classes="muted")
            with Horizontal(id="actions"):
                yield Button("Save Grade", id="approve", variant="success")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        score_input = self.query_one("#score", Input)
        comment_input = self.query_one("#comment", TextArea)
        if self.submission.score is not None:
            score_input.value = f"{self.submission.score:g}"
        if self.submission.comment:
            comment_input.text = self.submission.comment
        score_input.focus()

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


class StudentStatsScreen(ModalScreen[None]):
    CSS = """
    StudentStatsScreen {
        align: center middle;
    }

    #stats-dialog {
        width: 92;
        max-width: 95%;
        height: auto;
        max-height: 90%;
        padding: 1 2;
        border: solid $accent;
        background: $surface;
    }

    #stats-body {
        height: auto;
        max-height: 22;
        overflow-y: auto;
    }

    #stats-actions {
        height: auto;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close", priority=True),
        Binding("enter", "close", "Close", priority=True),
        Binding("q", "close", "Close", priority=True),
    ]

    def __init__(self, student_id: str, payload: dict[str, object]) -> None:
        super().__init__()
        self.student_id = student_id
        self.payload = payload

    def compose(self) -> ComposeResult:
        with Vertical(id="stats-dialog"):
            yield Static(self._render_stats(), id="stats-body")
            with Horizontal(id="stats-actions"):
                yield Button("Close", id="close-stats")

    def action_close(self) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.key in {"escape", "enter", "q"}:
            event.stop()
            event.prevent_default()
            self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-stats":
            self.dismiss(None)

    def _render_stats(self) -> str:
        summary = self.payload.get("summary") if isinstance(self.payload, dict) else {}
        if not isinstance(summary, dict):
            summary = {}
        lines = [
            f"[b]Student Score Stats: {self.student_id}[/b]",
            "",
            (
                f"Count={summary.get('count')} Avg={summary.get('average')} "
                f"Best={summary.get('best')} Latest={summary.get('latest')}"
            ),
            "",
            "Assignment\tTeacher\tPeer Avg\tBonus\tFinal\tWeight\tWeighted",
        ]
        scores = self.payload.get("scores") if isinstance(self.payload, dict) else []
        if not isinstance(scores, list) or not scores:
            lines.append("No graded scores.")
            lines.extend(["", "Press Enter, Esc, or q to close."])
            return "\n".join(lines)
        for item in scores:
            if not isinstance(item, dict):
                continue
            lines.append(
                "{assignment}\t{teacher}\t{peer}\t{bonus}\t{final}\t{weight}\t{weighted}".format(
                    assignment=item.get("assignment_id"),
                    teacher=item.get("teacher_score"),
                    peer=item.get("peer_avg_score"),
                    bonus=item.get("peer_bonus"),
                    final=item.get("final_score"),
                    weight=item.get("assignment_weight"),
                    weighted=item.get("weighted_score"),
                )
            )
        lines.extend(["", "Press Enter, Esc, or q to close."])
        return "\n".join(lines)


class ReportScreen(ModalScreen[None]):
    CSS = """
    ReportScreen {
        align: center middle;
    }

    #report-dialog {
        width: 110;
        max-width: 96%;
        height: 82%;
        padding: 1 2;
        border: solid $accent;
        background: $surface;
    }

    #report-title {
        text-style: bold;
        margin-bottom: 1;
    }

    #report-body {
        height: 1fr;
        overflow-y: auto;
    }

    #report-actions {
        height: auto;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close", priority=True),
        Binding("enter", "close", "Close", priority=True),
        Binding("q", "close", "Close", priority=True),
    ]

    def __init__(self, title: str, content: str) -> None:
        super().__init__()
        self.title = title
        self.content = content

    def compose(self) -> ComposeResult:
        with Vertical(id="report-dialog"):
            yield Static(escape(self.title), id="report-title")
            with ScrollableContainer(id="report-body"):
                yield Static(escape(self.content))
            yield Static("Press Enter, Esc, or q to close.", classes="muted")
            with Horizontal(id="report-actions"):
                yield Button("Close", id="close-report")

    def action_close(self) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.key in {"escape", "enter", "q"}:
            event.stop()
            event.prevent_default()
            self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-report":
            self.dismiss(None)


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
        Binding("d", "download_selected", "Download"),
        Binding("o", "open_downloaded_submission", "Open"),
        Binding("g", "show_ai_report", "AI Report"),
        Binding("c", "show_plagiarism_report", "Plagiarism"),
        Binding("s", "show_student_stats", "Stats"),
        Binding("j,down", "cursor_down", "Down"),
        Binding("k,up", "cursor_up", "Up"),
        Binding("enter", "review_selected", "Grade", priority=True),
    ]

    VIEW_TITLES = {
        "pending": "Pending Submissions",
        "approved": "Approved Submissions",
        "all": "All Submissions",
    }

    def __init__(self, settings: Settings, assignment_id: str = "") -> None:
        super().__init__()
        self.settings = settings
        self.assignment_id = assignment_id.strip()
        self.repository: SubmissionRepository = build_repository(settings)
        self.submissions: list[Submission] = []
        self.current_view = "pending"
        self._ai_report_cache: dict[int, dict[str, object]] = {}
        self._plagiarism_cache: dict[int, dict[str, object] | None] = {}
        self._plagiarism_check_cache: dict[str, dict[str, object]] = {}
        self._download_cache: dict[int, DownloadedSubmission] = {}

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
        self.push_screen(ReviewScreen(selected), lambda result: self._handle_review(selected.id, result))

    def action_download_selected(self) -> None:
        selected = self.selected_submission
        if selected is None:
            self.notify("No submission selected", severity="warning")
            return
        try:
            downloaded = self._ensure_downloaded_submission(selected)
        except Exception as exc:
            self.notify(f"Failed to download submission: {exc}", severity="error")
            return
        self.notify(f"Saved to {downloaded.archive_path}. Content: {downloaded.content_path}. Press o to view/open.")
        self.render_detail(selected)

    def action_open_downloaded_submission(self) -> None:
        selected = self.selected_submission
        if selected is None:
            self.notify("No submission selected", severity="warning")
            return
        try:
            downloaded = self._ensure_downloaded_submission(selected)
        except Exception as exc:
            self.notify(f"Failed to prepare submission content: {exc}", severity="error")
            return
        readable_file = find_readable_submission_file(downloaded.content_path)
        if readable_file is not None:
            try:
                preview = read_preview_text(readable_file)
            except Exception as exc:
                self.notify(f"Failed to read {readable_file}: {exc}", severity="error")
                return
            self.push_screen(
                ReportScreen(
                    f"Submission Content | {selected.student_id} | {readable_file.name}",
                    f"Path: {readable_file}\n\n{preview}",
                )
            )
            return
        try:
            open_path_in_system(downloaded.content_path)
        except Exception as exc:
            self.notify(f"Could not open automatically: {exc}. Path: {downloaded.content_path}", severity="warning")
            return
        self.notify(f"Opened {downloaded.content_path}")

    def action_show_ai_report(self) -> None:
        selected = self.selected_submission
        if selected is None:
            self.notify("No submission selected", severity="warning")
            return
        self.push_screen(
            ReportScreen(
                f"AI Grading Report | {selected.student_id} | Submission {selected.id}",
                self._render_ai_report(selected),
            )
        )

    def action_show_plagiarism_report(self) -> None:
        selected = self.selected_submission
        if selected is None:
            self.notify("No submission selected", severity="warning")
            return
        self.push_screen(
            ReportScreen(
                f"Plagiarism Report | {selected.student_id} | Submission {selected.id}",
                self._render_ai_assisted_plagiarism_report(selected),
            )
        )

    def action_show_student_stats(self) -> None:
        selected = self.selected_submission
        if selected is None:
            self.notify("No submission selected", severity="warning")
            return
        history = getattr(self.repository, "get_student_history", None)
        if history is None:
            self.notify("Current repository does not support score history", severity="warning")
            return
        try:
            payload = history(selected.student_id)
        except Exception as exc:
            self.notify(f"Failed to load score stats: {exc}", severity="error")
            return
        self.push_screen(StudentStatsScreen(selected.student_id, payload))

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
            self.submissions = self.repository.list_submissions(status, self.assignment_id or None)
        except Exception as exc:
            self.notify(f"Failed to load submissions: {exc}", severity="error")
            self.submissions = []
        title = self.VIEW_TITLES[self.current_view]
        if self.assignment_id:
            title = f"{title} | {self.assignment_id}"
        self.query_one("#title", Static).update(title)
        list_view = self.query_one("#submission-list", ListView)
        list_view.clear()
        for submission in self.submissions:
            assignment = submission.assignment_id or submission.assignment_title
            title = submission.assignment_title
            if title and title != assignment:
                assignment = f"{assignment} {title}"
            label = f"{submission.id} | {submission.student_id} | {assignment} | {submission.status}"
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
        class_label = submission.class_name or submission.class_id or "global"
        assignment_id = submission.assignment_id or submission.assignment_title
        title_line = (
            f"Assignment Title: {submission.assignment_title}\n"
            if submission.assignment_title and submission.assignment_title != assignment_id
            else ""
        )

        ai_report = self._render_ai_report(submission)
        plagiarism_report = self._render_plagiarism_report(submission)
        downloaded = self._download_cache.get(submission.id)
        local_content = ""
        if downloaded is not None:
            local_content = f"""Local Archive: {downloaded.archive_path}
Local Content: {downloaded.content_path}
"""

        detail = f"""[b]{assignment_id}[/b]

Submission ID: {submission.id}
Student ID: {submission.student_id}
Student Name: {submission.student_name}
Assignment ID: {assignment_id}
{title_line}Class: {class_label}
Status: {submission.status}
Created At: {submission.created_at}
File Name: {submission.file_name or ''}
Download URL: {submission.download_url or ''}
{local_content}Teacher Score: {submission.score}
Peer Avg Score: {submission.peer_avg_score}
Peer Bonus: {submission.peer_bonus}
Final Score: {submission.final_score}
Assignment Weight: {submission.assignment_weight}
Weighted Score: {submission.weighted_score}
{review_detail}

[b]Content[/b]
{submission.content}

[b]AI Grading Report[/b]
{ai_report}

[b]Plagiarism Report[/b]
{plagiarism_report}

Press Enter to grade/update score. d download/extract, o view/open content, g AI report, c plagiarism, s stats.
"""
        self.query_one("#detail", Static).update(detail)

    def _ensure_downloaded_submission(self, submission: Submission) -> DownloadedSubmission:
        cached = self._download_cache.get(submission.id)
        if cached and cached.archive_path.exists() and cached.content_path.exists():
            return cached

        download = getattr(self.repository, "download_submission", None)
        if download is None:
            raise RuntimeError("Current repository does not support downloads")

        archive_path = Path(
            download(
                submission.id,
                Path(self.settings.download_dir),
                submission.file_name or f"submission_{submission.id}.tar.gz",
            )
        )
        content_path = archive_path
        try:
            is_archive = tarfile.is_tarfile(archive_path)
        except (OSError, tarfile.TarError):
            is_archive = False
        if is_archive:
            content_path = extract_submission_archive(archive_path)

        downloaded = DownloadedSubmission(archive_path=archive_path, content_path=content_path)
        self._download_cache[submission.id] = downloaded
        return downloaded

    def _render_ai_report(self, submission: Submission) -> str:
        if submission.id not in self._ai_report_cache:
            loader = getattr(self.repository, "get_ai_grade_report", None)
            if loader is None:
                return "AI grading report is not available for this repository."
            try:
                self._ai_report_cache[submission.id] = loader(submission.id)
            except Exception as exc:
                return f"Failed to load AI grading report: {exc}"
        payload = self._ai_report_cache[submission.id]
        report = payload.get("report") if isinstance(payload, dict) else {}
        if not isinstance(report, dict):
            return "AI grading report is empty."
        source = payload.get("source") or report.get("source") or "unknown"
        model = payload.get("model") or report.get("model") or ""
        excerpt = str(report.get("submission_excerpt") or "").strip()
        text = str(report.get("report_text") or report.get("summary") or "").strip()
        lines = [f"Source: {source} {model}".strip()]
        if text:
            lines.append(text)
        if excerpt:
            lines.extend(["", "Submission Excerpt:", excerpt])
        return "\n".join(lines).strip() or "AI grading report is empty."

    def _render_plagiarism_report(self, submission: Submission) -> str:
        if submission.id not in self._plagiarism_cache:
            loader = getattr(self.repository, "get_submission_plagiarism", None)
            if loader is None:
                return "Plagiarism report is not available for this repository."
            try:
                self._plagiarism_cache[submission.id] = loader(submission.id)
            except Exception:
                self._plagiarism_cache[submission.id] = None
        payload = self._plagiarism_cache[submission.id]
        if not payload:
            return "No plagiarism report."
        return (
            f"Rate: {payload.get('plagiarism_rate')}% | "
            f"Matched Submission: {payload.get('matched_submission_id')} | "
            f"Matched Student: {payload.get('matched_student_id')} | "
            f"Scope: {payload.get('scope')} | Checked: {payload.get('checked_at')}"
        )

    def _render_ai_assisted_plagiarism_report(self, submission: Submission) -> str:
        lines = [
            "Submission baseline report:",
            self._render_plagiarism_report(submission),
            "",
            "AI-assisted assignment check:",
        ]
        assignment_id = submission.assignment_id or self.assignment_id
        if not assignment_id:
            lines.append("Assignment ID is not available; cannot run assignment-level plagiarism check.")
            return "\n".join(lines)

        checker = getattr(self.repository, "check_plagiarism", None)
        if checker is None:
            lines.append("Current repository does not support AI-assisted plagiarism checks.")
            return "\n".join(lines)

        if assignment_id not in self._plagiarism_check_cache:
            try:
                self._plagiarism_check_cache[assignment_id] = checker(
                    assignment_id,
                    method="hybrid",
                    threshold=0.75,
                )
            except Exception as exc:
                lines.append(f"Failed to run hybrid plagiarism check: {exc}")
                return "\n".join(lines)

        payload = self._plagiarism_check_cache[assignment_id]
        lines.extend(
            [
                f"Assignment: {payload.get('assignment_id')}",
                f"Method: {payload.get('method')} | Threshold: {payload.get('threshold')}",
                (
                    f"Submissions: current={payload.get('submission_count')} "
                    f"history={payload.get('historical_submission_count')} "
                    f"pairs={payload.get('candidate_pair_count')}"
                ),
                f"AI reviewed: {payload.get('ai_reviewed_count')} / limit={payload.get('ai_limit')}",
                "",
            ]
        )

        pairs = payload.get("suspected_pairs")
        if not isinstance(pairs, list):
            pairs = []
        relevant_pairs = [
            pair
            for pair in pairs
            if isinstance(pair, dict)
            and (
                int(pair.get("submission_a") or -1) == submission.id
                or int(pair.get("submission_b") or -1) == submission.id
            )
        ]
        if not relevant_pairs:
            lines.append("No AI-assisted suspected pairs for this submission.")
            return "\n".join(lines)

        lines.append("Suspected pairs involving this submission:")
        for pair in relevant_pairs:
            lines.append(
                "{a}:{student_a} ({assignment_a}) <-> {b}:{student_b} ({assignment_b}) "
                "scope={scope} score={score} local={local} reason={reason}".format(
                    a=pair.get("submission_a"),
                    student_a=pair.get("student_a"),
                    assignment_a=pair.get("assignment_a"),
                    b=pair.get("submission_b"),
                    student_b=pair.get("student_b"),
                    assignment_b=pair.get("assignment_b"),
                    scope=pair.get("scope"),
                    score=pair.get("similarity"),
                    local=pair.get("local_similarity"),
                    reason=pair.get("reason"),
                )
            )
            evidence = pair.get("evidence")
            if isinstance(evidence, list) and evidence:
                lines.extend(f"  - {item}" for item in evidence if str(item).strip())
        return "\n".join(lines)

    def _handle_review(
        self,
        submission_id: int,
        result: tuple[float, str] | None,
    ) -> None:
        if result is None:
            return
        score, comment = result
        submission = self.repository.get_submission(submission_id)
        if submission is None:
            self.notify("Submission is no longer available", severity="error")
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

        self.notify(f"Saved grade for submission {updated.id}")
        self._ai_report_cache.pop(updated.id, None)
        self.refresh_submissions()
