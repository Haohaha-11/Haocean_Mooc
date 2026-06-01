from __future__ import annotations

from . import db
from .config import Settings
from .feedback import generate_feedback_markdown
from .models import Submission
from .status import service_to_local_status


class SQLiteSubmissionRepository:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def list_submissions(self, status: str | None = None) -> list[Submission]:
        return db.list_submissions(self.settings.db_path, status)

    def get_submission(self, submission_id: int) -> Submission | None:
        return db.get_submission(self.settings.db_path, submission_id)

    def grade_submission(
        self,
        submission_id: int,
        score: float,
        comment: str,
        status: str = "graded",
    ) -> Submission:
        submission = db.get_submission(self.settings.db_path, submission_id)
        if submission is None or submission.status != "pending":
            raise ValueError("Submission is no longer pending")

        local_status = service_to_local_status(status)
        feedback_path = generate_feedback_markdown(
            submission,
            score,
            comment,
            self.settings.feedback_dir,
        )
        stored_path = feedback_path.relative_to(self.settings.project_root)
        db.review_submission(
            self.settings.db_path,
            submission.id,
            score,
            comment,
            stored_path,
            local_status,
        )
        updated = db.get_submission(self.settings.db_path, submission.id)
        if updated is None:
            raise ValueError(f"Submission not found after review: {submission.id}")
        return updated
