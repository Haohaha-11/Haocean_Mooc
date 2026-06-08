from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from fastapi import HTTPException
from fastapi.responses import FileResponse

from app import main


class ClassesAndDownloadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_db_path = main.DB_PATH
        self.original_auth_required = main.AUTH_REQUIRED
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        main.DB_PATH = self.root / "engine.db"
        main.AUTH_REQUIRED = True
        main.init_db()
        main.init_extra_db()

    def tearDown(self) -> None:
        main.DB_PATH = self.original_db_path
        main.AUTH_REQUIRED = self.original_auth_required
        self.tmp.cleanup()

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


if __name__ == "__main__":
    unittest.main()
