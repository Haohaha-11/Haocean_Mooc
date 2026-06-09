from __future__ import annotations

import asyncio
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from fastapi import HTTPException
from fastapi import UploadFile
from fastapi.responses import FileResponse

from app import main


class ClassesAndDownloadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_db_path = main.DB_PATH
        self.original_auth_required = main.AUTH_REQUIRED
        self.original_tmp_dir = main.TMP_DIR
        self.original_materials_dir = main.ASSIGNMENT_MATERIALS_DIR
        self.original_submissions_dir = main.SUBMISSIONS_DIR
        self.original_feedback_dir = main.FEEDBACK_DIR
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        main.DB_PATH = self.root / "engine.db"
        main.TMP_DIR = self.root / "tmp"
        main.ASSIGNMENT_MATERIALS_DIR = self.root / "assignment_materials"
        main.SUBMISSIONS_DIR = self.root / "submissions"
        main.FEEDBACK_DIR = self.root / "feedback"
        main.TMP_DIR.mkdir(parents=True, exist_ok=True)
        main.ASSIGNMENT_MATERIALS_DIR.mkdir(parents=True, exist_ok=True)
        main.SUBMISSIONS_DIR.mkdir(parents=True, exist_ok=True)
        main.FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
        main.AUTH_REQUIRED = True
        main.init_db()
        main.init_extra_db()

    def tearDown(self) -> None:
        main.DB_PATH = self.original_db_path
        main.AUTH_REQUIRED = self.original_auth_required
        main.TMP_DIR = self.original_tmp_dir
        main.ASSIGNMENT_MATERIALS_DIR = self.original_materials_dir
        main.SUBMISSIONS_DIR = self.original_submissions_dir
        main.FEEDBACK_DIR = self.original_feedback_dir
        self.tmp.cleanup()

    def _upload_submission(self, student_id: str, assignment_id: str, content: bytes) -> dict:
        metadata = {
            "action": "SUBMIT",
            "timestamp": 1,
            "payload": {
                "student_id": student_id,
                "assignment_id": assignment_id,
                "md5": hashlib.md5(content).hexdigest(),
                "file_name": "answer.tar.gz",
            },
        }
        return asyncio.run(
            main.create_submission(
                metadata=json.dumps(metadata),
                file=UploadFile(
                    filename="answer.tar.gz",
                    file=io.BytesIO(content),
                ),
                auth=main.AuthContext(
                    email=f"{student_id.lower()}@example.com",
                    role=main.ROLE_STUDENT,
                    display_id=student_id,
                ),
            )
        )["payload"]

    def test_student_sees_class_assignment_after_joining(self) -> None:
        teacher = main.AuthContext(
            email="teacher@example.com",
            role=main.ROLE_TEACHER,
            display_id="T001",
        )
        student = main.AuthContext(
            email="student@example.com",
            role=main.ROLE_STUDENT,
            display_id="2024001",
        )

        created = main.create_class(
            main.CreateClassRequest(
                action="CREATE_CLASS",
                timestamp=1,
                payload=main.CreateClassPayload(
                    teacher_id="T001",
                    class_id="cs101",
                    class_name="CS101 Spring",
                    course_id="course_cs",
                    course_title="Computer Science",
                    join_code="JOIN101",
                ),
            ),
            auth=teacher,
        )["payload"]

        created_assignment = main.create_assignment(
            main.AssignmentRequest(
                action="CREATE_ASSIGNMENT",
                timestamp=2,
                payload=main.AssignmentPayload(
                    teacher_id="T001",
                    assignment_id="home_class",
                    title="Class Homework",
                    class_id=created["class_id"],
                    assignment_weight=2.5,
                    peer_review_enabled=True,
                    teacher_weight=0.8,
                    peer_weight=0.2,
                ),
            ),
            auth=teacher,
        )["payload"]

        self.assertTrue(created_assignment["peer_review_enabled"])
        self.assertEqual(created_assignment["peer_review_stage"], "submission")
        self.assertEqual(created_assignment["teacher_weight"], 0.8)
        self.assertEqual(created_assignment["peer_weight"], 0.2)
        conn = main.get_conn()
        assignment_row = conn.execute(
            """
            SELECT peer_review_enabled, peer_review_stage, teacher_weight, peer_weight
            FROM assignments
            WHERE assignment_id = ?;
            """,
            ("home_class",),
        ).fetchone()
        conn.close()
        self.assertEqual(assignment_row["peer_review_enabled"], 1)
        self.assertEqual(assignment_row["peer_review_stage"], "submission")
        self.assertEqual(assignment_row["teacher_weight"], 0.8)
        self.assertEqual(assignment_row["peer_weight"], 0.2)

        before_join = main.list_open_assignments(auth=student)["payload"]["assignments"]
        self.assertEqual(before_join, [])

        joined = main.join_class(
            main.JoinClassRequest(
                action="JOIN_CLASS",
                timestamp=3,
                payload=main.JoinClassPayload(
                    student_id="2024001",
                    join_code="JOIN101",
                ),
            ),
            auth=student,
        )["payload"]
        self.assertEqual(joined["class_id"], "cs101")

        after_join = main.list_open_assignments(auth=student)["payload"]["assignments"]
        self.assertEqual(after_join[0]["assignment_id"], "home_class")
        self.assertEqual(after_join[0]["class_id"], "cs101")
        self.assertEqual(after_join[0]["assignment_weight"], 2.5)

    def test_create_class_rejects_duplicate_name_for_same_teacher(self) -> None:
        teacher = main.AuthContext(
            email="teacher@example.com",
            role=main.ROLE_TEACHER,
            display_id="T001",
        )
        payload = main.CreateClassPayload(
            teacher_id="T001",
            class_id="cs101",
            class_name="CS101 Spring",
            course_id="course_cs101",
            course_title="Computer Science",
            join_code="JOIN101",
        )
        main.create_class(
            main.CreateClassRequest(
                action="CREATE_CLASS",
                timestamp=1,
                payload=payload,
            ),
            auth=teacher,
        )

        with self.assertRaises(HTTPException) as caught:
            main.create_class(
                main.CreateClassRequest(
                    action="CREATE_CLASS",
                    timestamp=2,
                    payload=main.CreateClassPayload(
                        teacher_id="T001",
                        class_id="cs102",
                        class_name="CS101 Spring",
                        course_id="course_cs102",
                        course_title="Computer Science",
                        join_code="JOIN102",
                    ),
                ),
                auth=teacher,
            )

        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(
            caught.exception.detail["message"],
            "class_name already exists for this teacher: CS101 Spring",
        )

    def test_submission_download_checks_teacher_ownership(self) -> None:
        archive_path = self.root / "answer.tar.gz"
        archive_path.write_bytes(b"payload")
        conn = main.get_conn()
        conn.execute(
            """
            INSERT INTO assignments (
                assignment_id, title, description, deadline,
                created_by, class_id, created_at, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            ("home_download", "Download", "", "", "T001", None, main.now_str(), "open"),
        )
        cur = conn.execute(
            """
            INSERT INTO submissions (
                student_id, assignment_id, file_name, file_path,
                md5, submit_time, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                "2024001",
                "home_download",
                "answer.tar.gz",
                str(archive_path),
                "md5",
                main.now_str(),
                "pending",
            ),
        )
        submission_id = int(cur.lastrowid)
        conn.commit()
        conn.close()

        response = main.download_submission(
            submission_id,
            auth=main.AuthContext(
                email="teacher@example.com",
                role=main.ROLE_TEACHER,
                display_id="T001",
            ),
        )
        self.assertIsInstance(response, FileResponse)

        with self.assertRaises(HTTPException) as caught:
            main.download_submission(
                submission_id,
                auth=main.AuthContext(
                    email="other@example.com",
                    role=main.ROLE_TEACHER,
                    display_id="T999",
                ),
            )
        self.assertEqual(caught.exception.status_code, 403)

    def test_assignment_materials_upload_and_student_download_respect_class_membership(self) -> None:
        teacher = main.AuthContext(
            email="teacher@example.com",
            role=main.ROLE_TEACHER,
            display_id="T001",
        )
        student = main.AuthContext(
            email="student@example.com",
            role=main.ROLE_STUDENT,
            display_id="2024001",
        )
        outsider = main.AuthContext(
            email="outsider@example.com",
            role=main.ROLE_STUDENT,
            display_id="2024999",
        )

        created = main.create_class(
            main.CreateClassRequest(
                action="CREATE_CLASS",
                timestamp=1,
                payload=main.CreateClassPayload(
                    teacher_id="T001",
                    class_id="cs101",
                    class_name="CS101 Spring",
                    course_id="course_cs",
                    course_title="Computer Science",
                    join_code="JOIN101",
                ),
            ),
            auth=teacher,
        )["payload"]
        main.create_assignment(
            main.AssignmentRequest(
                action="CREATE_ASSIGNMENT",
                timestamp=2,
                payload=main.AssignmentPayload(
                    teacher_id="T001",
                    assignment_id="home_materials",
                    title="Materials Homework",
                    class_id=created["class_id"],
                ),
            ),
            auth=teacher,
        )
        main.join_class(
            main.JoinClassRequest(
                action="JOIN_CLASS",
                timestamp=3,
                payload=main.JoinClassPayload(
                    student_id="2024001",
                    join_code="JOIN101",
                ),
            ),
            auth=student,
        )

        uploaded = asyncio.run(
            main.upload_assignment_materials(
                "home_materials",
                file=UploadFile(
                    filename="spec.pdf",
                    file=io.BytesIO(b"assignment spec"),
                ),
                auth=teacher,
            )
        )["payload"]

        self.assertEqual(uploaded["file_name"], "spec.pdf")
        assignments = main.list_open_assignments(auth=student)["payload"]["assignments"]
        self.assertTrue(assignments[0]["has_materials"])
        self.assertEqual(assignments[0]["materials_file_name"], "spec.pdf")

        response = main.download_assignment_materials("home_materials", auth=student)
        self.assertIsInstance(response, FileResponse)

        with self.assertRaises(HTTPException) as caught:
            main.download_assignment_materials("home_materials", auth=outsider)
        self.assertEqual(caught.exception.status_code, 403)

    def test_student_resubmission_overwrites_latest_submission_row(self) -> None:
        conn = main.get_conn()
        conn.execute(
            """
            INSERT INTO assignments (
                assignment_id, title, description, deadline, created_by, created_at, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            ("home_overwrite", "Overwrite", "", "2999-01-01 23:59:59", "T001", main.now_str(), "open"),
        )
        conn.commit()
        conn.close()

        first = self._upload_submission("2024001", "home_overwrite", b"first submission")

        conn = main.get_conn()
        conn.execute(
            """
            UPDATE submissions
            SET status = 'graded', score = 88, comment = 'old', feedback_path = 'old.md'
            WHERE submission_id = ?;
            """,
            (first["submission_id"],),
        )
        conn.commit()
        conn.close()

        second = self._upload_submission("2024001", "home_overwrite", b"second submission")

        self.assertEqual(second["submission_id"], first["submission_id"])

        conn = main.get_conn()
        rows = conn.execute(
            """
            SELECT submission_id, md5, status, score, comment, feedback_path
            FROM submissions
            WHERE student_id = ?
              AND assignment_id = ?;
            """,
            ("2024001", "home_overwrite"),
        ).fetchall()
        conn.close()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "pending")
        self.assertIsNone(rows[0]["score"])
        self.assertIsNone(rows[0]["comment"])
        self.assertIsNone(rows[0]["feedback_path"])
        self.assertEqual(rows[0]["md5"], hashlib.md5(b"second submission").hexdigest())
        self.assertEqual(Path(second["archive_path"]).read_bytes(), b"second submission")

    def test_submission_after_deadline_is_rejected(self) -> None:
        conn = main.get_conn()
        conn.execute(
            """
            INSERT INTO assignments (
                assignment_id, title, description, deadline, created_by, created_at, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            ("home_closed", "Closed", "", "2000-01-01 00:00:00", "T001", main.now_str(), "open"),
        )
        conn.commit()
        conn.close()

        with self.assertRaises(HTTPException) as caught:
            self._upload_submission("2024001", "home_closed", b"late submission")

        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(caught.exception.detail["message"], "assignment deadline has passed")


if __name__ == "__main__":
    unittest.main()
