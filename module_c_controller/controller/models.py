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
    assignment_id: str = ""
    class_id: str | None = None
    class_name: str | None = None
    file_name: str | None = None
    download_url: str | None = None
    score: float | None = None
    comment: str | None = None
    reviewed_at: str | None = None
    feedback_path: str | None = None
    peer_avg_score: float | None = None
    peer_bonus: float | None = None
    final_score: float | None = None
    assignment_weight: float | None = None
    weighted_score: float | None = None
