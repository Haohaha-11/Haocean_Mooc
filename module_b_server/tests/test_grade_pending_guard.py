from __future__ import annotations

from pathlib import Path
import tempfile
import time
import unittest

from fastapi import HTTPException

from app import main
from app.main import GradePayload, GradeRequest, get_conn, grade_submission, init_db


class GradePendingGuardTests(unittest.TestCase):
    def test_grade_rejects_non_pending_submission(self) -> None:
        original_db_path = main.DB_PATH
        original_feedback_dir = main.FEEDBACK_DIR
        with tempfile.TemporaryDirectory() as tmp:
            main.DB_PATH = Path(tmp) / "engine.db"
            main.FEEDBACK_DIR = Path(tmp) / "feedback"
            main.FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
            try:
                init_db()
                assignment_id = f"grade_guard_{int(time.time() * 1000)}"
                student_id = "2024001"

                conn = get_conn()
                conn.execute(
                    """
                    INSERT INTO assignments (
                        assignment_id, title, description, deadline,
                        created_by, created_at, status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        assignment_id,
                        "Grade Guard",
                        "Ensure repeat grading is rejected.",
                        "2026-06-01 23:59:59",
                        "T001",
                        "2026-05-28 10:00:00",
                        "open",
                    ),
                )
                cursor = conn.execute(
                    """
                    INSERT INTO submissions (
                        student_id, assignment_id, file_name, file_path,
                        md5, submit_time, status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        student_id,
                        assignment_id,
                        f"{student_id}_{assignment_id}.tar.gz",
                        f"/tmp/{student_id}_{assignment_id}.tar.gz",
                        "abc",
                        "2026-05-28 10:01:00",
                        "graded",
                    ),
                )
                conn.commit()
                submission_id = cursor.lastrowid
                conn.close()

                request = GradeRequest(
                    action="GRADE",
                    timestamp=int(time.time()),
                    payload=GradePayload(
                        submission_id=submission_id,
                        teacher_id="T001",
                        score=90,
                        comment="Repeat grade.",
                        status="graded",
                    ),
                )

                with self.assertRaises(HTTPException) as caught:
                    grade_submission(request)
                self.assertEqual(caught.exception.status_code, 400)
                self.assertEqual(
                    caught.exception.detail["message"],
                    "submission is not pending",
                )
            finally:
                main.DB_PATH = original_db_path
                main.FEEDBACK_DIR = original_feedback_dir


if __name__ == "__main__":
    unittest.main()
