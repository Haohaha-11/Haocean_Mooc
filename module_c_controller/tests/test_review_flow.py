from __future__ import annotations

from pathlib import Path

from controller.db import (
    approve_submission,
    get_submission,
    insert_mock_submissions,
    list_pending_submissions,
)
from controller.feedback import generate_feedback_markdown


def test_complete_review_flow(tmp_path: Path) -> None:
    db_path = tmp_path / "mock.db"
    feedback_dir = tmp_path / "feedback_outbox"
    insert_mock_submissions(
        db_path,
        [
            {
                "student_id": "S2",
                "student_name": "Ben",
                "assignment_title": "SQLite Joins",
                "content": "Joined tables and explained query results.",
                "created_at": "2026-05-21T00:00:00+00:00",
            }
        ],
    )
    submission = list_pending_submissions(db_path)[0]

    feedback_path = generate_feedback_markdown(
        submission,
        87.5,
        "Correct joins with minor formatting issues.",
        feedback_dir,
    )
    approve_submission(
        db_path,
        submission.id,
        87.5,
        "Correct joins with minor formatting issues.",
        feedback_path.relative_to(tmp_path),
    )

    updated = get_submission(db_path, submission.id)

    assert feedback_path.exists()
    assert updated is not None
    assert updated.status == "approved"
    assert updated.score == 87.5
    assert updated.feedback_path == "feedback_outbox/submission_1_S2_feedback.md"
    assert list_pending_submissions(db_path) == []
