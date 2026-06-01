from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from .models import Submission


SCHEMA = """
CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    student_name TEXT NOT NULL,
    assignment_title TEXT NOT NULL,
    content TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    score REAL,
    comment TEXT,
    reviewed_at TEXT,
    feedback_path TEXT
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database(db_path: Path) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


def _row_to_submission(row: sqlite3.Row) -> Submission:
    return Submission(
        id=row["id"],
        student_id=row["student_id"],
        student_name=row["student_name"],
        assignment_title=row["assignment_title"],
        content=row["content"],
        status=row["status"],
        created_at=row["created_at"],
        score=row["score"],
        comment=row["comment"],
        reviewed_at=row["reviewed_at"],
        feedback_path=row["feedback_path"],
    )


def list_submissions(db_path: Path, status: str | None = None) -> list[Submission]:
    initialize_database(db_path)
    with connect(db_path) as conn:
        if status is None:
            rows = conn.execute(
                """
                SELECT *
                FROM submissions
                ORDER BY created_at ASC, id ASC
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT *
                FROM submissions
                WHERE status = ?
                ORDER BY created_at ASC, id ASC
                """,
                (status,),
            ).fetchall()
    return [_row_to_submission(row) for row in rows]


def list_pending_submissions(db_path: Path) -> list[Submission]:
    return list_submissions(db_path, "pending")


def get_submission(db_path: Path, submission_id: int) -> Submission | None:
    initialize_database(db_path)
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM submissions WHERE id = ?",
            (submission_id,),
        ).fetchone()
    return _row_to_submission(row) if row else None


def approve_submission(
    db_path: Path,
    submission_id: int,
    score: float,
    comment: str,
    feedback_path: Path,
) -> None:
    review_submission(
        db_path,
        submission_id,
        score,
        comment,
        feedback_path,
        "approved",
    )


def review_submission(
    db_path: Path,
    submission_id: int,
    score: float,
    comment: str,
    feedback_path: Path,
    status: str,
) -> None:
    if status not in {"approved", "rejected"}:
        raise ValueError("status must be approved or rejected")
    initialize_database(db_path)
    reviewed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with connect(db_path) as conn:
        result = conn.execute(
            """
            UPDATE submissions
            SET status = ?,
                score = ?,
                comment = ?,
                reviewed_at = ?,
                feedback_path = ?
            WHERE id = ? AND status = 'pending'
            """,
            (status, score, comment, reviewed_at, str(feedback_path), submission_id),
        )
        if result.rowcount != 1:
            raise ValueError(f"Pending submission not found: {submission_id}")


def insert_mock_submissions(db_path: Path, submissions: Iterable[dict[str, str]]) -> int:
    initialize_database(db_path)
    inserted = 0
    with connect(db_path) as conn:
        for item in submissions:
            exists = conn.execute(
                """
                SELECT 1
                FROM submissions
                WHERE student_id = ?
                  AND assignment_title = ?
                  AND created_at = ?
                """,
                (item["student_id"], item["assignment_title"], item["created_at"]),
            ).fetchone()
            if exists:
                continue
            conn.execute(
                """
                INSERT INTO submissions (
                    student_id,
                    student_name,
                    assignment_title,
                    content,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, 'pending', ?)
                """,
                (
                    item["student_id"],
                    item["student_name"],
                    item["assignment_title"],
                    item["content"],
                    item["created_at"],
                ),
            )
            inserted += 1
    return inserted
