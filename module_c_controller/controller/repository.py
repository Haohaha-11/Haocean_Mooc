from __future__ import annotations

from typing import Protocol

from .config import Settings
from .models import Submission


class SubmissionRepository(Protocol):
    def list_submissions(
        self,
        status: str | None = None,
        assignment_id: str | None = None,
    ) -> list[Submission]:
        ...

    def get_submission(self, submission_id: int) -> Submission | None:
        ...

    def grade_submission(
        self,
        submission_id: int,
        score: float,
        comment: str,
        status: str = "graded",
    ) -> Submission:
        ...


def build_repository(settings: Settings) -> SubmissionRepository:
    if settings.source == "http":
        from .api_client import ModuleBRepository

        return ModuleBRepository(
            base_url=settings.api_base_url,
            teacher_id=settings.teacher_id,
            auth_token=settings.auth_token,
            timeout=settings.request_timeout_seconds,
        )

    from .sqlite_repo import SQLiteSubmissionRepository

    return SQLiteSubmissionRepository(settings)
