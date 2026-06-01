from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Submission:
    id: int
    student_id: str
    student_name: str
    assignment_title: str
    content: str
    status: str
    created_at: str
    score: float | None = None
    comment: str | None = None
    reviewed_at: str | None = None
    feedback_path: str | None = None
