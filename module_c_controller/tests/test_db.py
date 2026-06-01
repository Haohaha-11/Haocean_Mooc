from __future__ import annotations

from pathlib import Path

import pytest

from controller.db import (
    approve_submission,
    get_submission,
    insert_mock_submissions,
    list_pending_submissions,
    list_submissions,
)


def test_insert_and_list_pending_submissions(tmp_path: Path) -> None:
    db_path = tmp_path / "mock.db"
    inserted = insert_mock_submissions(
        db_path,
        [
            {
                "student_id": "S1",
                "student_name": "Ada",
                "assignment_title": "Loops",
                "content": "Solved all loop exercises.",
                "created_at": "2026-05-20T00:00:00+00:00",
            }
        ],
    )

    pending = list_pending_submissions(db_path)

    assert inserted == 1
    assert len(pending) == 1
    assert pending[0].student_id == "S1"
    assert pending[0].status == "pending"


def test_insert_mock_submissions_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "mock.db"
    item = {
        "student_id": "S1",
        "student_name": "Ada",
        "assignment_title": "Loops",
        "content": "Solved all loop exercises.",
        "created_at": "2026-05-20T00:00:00+00:00",
    }

    assert insert_mock_submissions(db_path, [item]) == 1
    assert insert_mock_submissions(db_path, [item]) == 0
    assert len(list_pending_submissions(db_path)) == 1


def test_list_submissions_filters_by_status(tmp_path: Path) -> None:
    db_path = tmp_path / "mock.db"
    insert_mock_submissions(
        db_path,
        [
            {
                "student_id": "S1",
                "student_name": "Ada",
                "assignment_title": "Loops",
                "content": "Solved all loop exercises.",
                "created_at": "2026-05-20T00:00:00+00:00",
            },
            {
                "student_id": "S2",
                "student_name": "Grace",
                "assignment_title": "Functions",
                "content": "Completed function exercises.",
                "created_at": "2026-05-21T00:00:00+00:00",
            },
        ],
    )
    first_submission = list_pending_submissions(db_path)[0]
    approve_submission(
        db_path,
        first_submission.id,
        95,
        "Strong work.",
        Path("feedback_outbox/submission_1_feedback.md"),
    )

    pending = list_submissions(db_path, "pending")
    approved = list_submissions(db_path, "approved")
    all_submissions = list_submissions(db_path, None)
    pending_via_legacy_api = list_pending_submissions(db_path)

    assert [submission.status for submission in pending] == ["pending"]
    assert [submission.status for submission in approved] == ["approved"]
    assert [submission.status for submission in all_submissions] == ["approved", "pending"]
    assert pending_via_legacy_api == pending


def test_approve_submission_updates_status_and_review_fields(tmp_path: Path) -> None:
    db_path = tmp_path / "mock.db"
    insert_mock_submissions(
        db_path,
        [
            {
                "student_id": "S1",
                "student_name": "Ada",
                "assignment_title": "Loops",
                "content": "Solved all loop exercises.",
                "created_at": "2026-05-20T00:00:00+00:00",
            }
        ],
    )
    submission = list_pending_submissions(db_path)[0]

    approve_submission(
        db_path,
        submission.id,
        95,
        "Strong work.",
        Path("feedback_outbox/submission_1_feedback.md"),
    )
    updated = get_submission(db_path, submission.id)

    assert updated is not None
    assert updated.status == "approved"
    assert updated.score == 95
    assert updated.comment == "Strong work."
    assert updated.reviewed_at is not None
    assert updated.feedback_path == "feedback_outbox/submission_1_feedback.md"
    assert list_pending_submissions(db_path) == []


def test_approve_missing_pending_submission_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        approve_submission(
            tmp_path / "mock.db",
            999,
            88,
            "Reviewed.",
            Path("feedback.md"),
        )
