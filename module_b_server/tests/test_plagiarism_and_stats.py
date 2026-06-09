from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
import zipfile

from fastapi import HTTPException

from app import main


def build_archive(path: Path, content: str) -> None:
    source = path.with_suffix(".py")
    source.write_text(content, encoding="utf-8")
    with tarfile.open(path, "w:gz") as tar:
        tar.add(source, arcname="answer.py")


class PlagiarismAndStatsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_db_path = main.DB_PATH
        self.original_auth_required = main.AUTH_REQUIRED
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        main.DB_PATH = self.root / "engine.db"
        main.AUTH_REQUIRED = False
        main.init_db()
        main.init_extra_db()
        main.init_plagiarism_db()

    def tearDown(self) -> None:
        main.DB_PATH = self.original_db_path
        main.AUTH_REQUIRED = self.original_auth_required
        self.tmp.cleanup()

    def test_plagiarism_report_is_created_for_matching_submission(self) -> None:
        first_archive = self.root / "first.tar.gz"
        second_archive = self.root / "second.tar.gz"
        content = "def solve():\n    total = sum(range(10))\n    return total\n"
        build_archive(first_archive, content)
        build_archive(second_archive, content)

        conn = main.get_conn()
        conn.execute(
            """
            INSERT INTO assignments (
                assignment_id, title, description, deadline, created_by, created_at, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            ("home_plagiarism", "Plagiarism", "", "", "T001", main.now_str(), "open"),
        )
        cur = conn.execute(
            """
            INSERT INTO submissions (
                student_id, assignment_id, file_name, file_path, md5, submit_time, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            ("2024001", "home_plagiarism", "first.tar.gz", str(first_archive), "md5a", main.now_str(), "pending"),
        )
        first_id = cur.lastrowid
        main.calculate_plagiarism_for_submission(conn, int(first_id))

        cur = conn.execute(
            """
            INSERT INTO submissions (
                student_id, assignment_id, file_name, file_path, md5, submit_time, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            ("2024002", "home_plagiarism", "second.tar.gz", str(second_archive), "md5b", main.now_str(), "pending"),
        )
        second_id = cur.lastrowid
        report = main.calculate_plagiarism_for_submission(conn, int(second_id))
        conn.commit()
        conn.close()

        self.assertGreaterEqual(report["plagiarism_rate"], 95)
        self.assertEqual(report["matched_submission_id"], first_id)
        self.assertEqual(report["scope"], "current_assignment")

        response = main.list_assignment_plagiarism("home_plagiarism", auth=None)
        reports = response["payload"]["reports"]
        self.assertEqual(reports[0]["submission_id"], second_id)
        self.assertGreaterEqual(reports[0]["plagiarism_rate"], 95)

    def test_ai_plagiarism_requires_deepseek_key(self) -> None:
        original_key = main.DEEPSEEK_API_KEY
        main.DEEPSEEK_API_KEY = ""
        try:
            with self.assertRaises(HTTPException) as caught:
                main.check_plagiarism(
                    main.PlagiarismCheckRequest(
                        action="CHECK_PLAGIARISM",
                        timestamp=1,
                        payload=main.PlagiarismCheckPayload(
                            assignment_id="home_ai",
                            method="hybrid",
                        ),
                    ),
                    auth=None,
                )
        finally:
            main.DEEPSEEK_API_KEY = original_key

        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(
            caught.exception.detail["message"],
            "DEEPSEEK_API_KEY is required for AI plagiarism check",
        )

    def test_plagiarism_check_with_too_few_submissions_returns_complete_payload(self) -> None:
        conn = main.get_conn()
        conn.execute(
            """
            INSERT INTO assignments (
                assignment_id, title, description, deadline, created_by, created_at, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            ("home_too_few", "Too Few", "", "", "T001", main.now_str(), "open"),
        )
        conn.close()

        response = main.check_plagiarism(
            main.PlagiarismCheckRequest(
                action="CHECK_PLAGIARISM",
                timestamp=1,
                payload=main.PlagiarismCheckPayload(
                    assignment_id="home_too_few",
                    method="token",
                    threshold=0.8,
                ),
            ),
            auth=None,
        )

        payload = response["payload"]
        self.assertEqual(payload["method"], "token")
        self.assertEqual(payload["threshold"], 0.8)
        self.assertEqual(payload["submission_count"], 0)
        self.assertEqual(payload["candidate_pair_count"], 0)
        self.assertEqual(payload["suspected_pair_count"], 0)
        self.assertFalse(payload["ai_enabled"])
        self.assertEqual(payload["suspected_pairs"], [])

    def test_plagiarism_check_compares_current_assignment_with_three_year_history(self) -> None:
        current_archive = self.root / "current.tar.gz"
        history_archive = self.root / "history.tar.gz"
        content = "def solve(items):\n    total = 0\n    for item in items:\n        total += item\n    return total\n"
        build_archive(current_archive, content)
        build_archive(history_archive, content)

        conn = main.get_conn()
        for assignment_id, title in [("home_current", "Current"), ("home_history", "History")]:
            conn.execute(
                """
                INSERT INTO assignments (
                    assignment_id, title, description, deadline, created_by, created_at, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (assignment_id, title, "", "", "T001", main.now_str(), "open"),
            )
        for student_id, assignment_id, archive in [
            ("2024001", "home_current", current_archive),
            ("2023001", "home_history", history_archive),
        ]:
            conn.execute(
                """
                INSERT INTO submissions (
                    student_id, assignment_id, file_name, file_path, md5, submit_time, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    student_id,
                    assignment_id,
                    archive.name,
                    str(archive),
                    f"md5-{student_id}",
                    main.now_str(),
                    "pending",
                ),
            )
        conn.commit()
        conn.close()

        response = main.check_plagiarism(
            main.PlagiarismCheckRequest(
                action="CHECK_PLAGIARISM",
                timestamp=1,
                payload=main.PlagiarismCheckPayload(
                    assignment_id="home_current",
                    method="token",
                    threshold=0.8,
                ),
            ),
            auth=None,
        )

        payload = response["payload"]
        self.assertEqual(payload["submission_count"], 1)
        self.assertEqual(payload["historical_submission_count"], 1)
        self.assertEqual(payload["candidate_pair_count"], 1)
        self.assertEqual(payload["suspected_pair_count"], 1)
        pair = payload["suspected_pairs"][0]
        self.assertEqual(pair["assignment_a"], "home_current")
        self.assertEqual(pair["assignment_b"], "home_history")
        self.assertEqual(pair["scope"], "last_three_years")

    def test_hybrid_plagiarism_uses_deepseek_for_prefiltered_pairs(self) -> None:
        first_archive = self.root / "ai_first.tar.gz"
        second_archive = self.root / "ai_second.tar.gz"
        content = "def solve(items):\n    total = 0\n    for item in items:\n        total += item\n    return total\n"
        build_archive(first_archive, content)
        build_archive(second_archive, content)

        conn = main.get_conn()
        conn.execute(
            """
            INSERT INTO assignments (
                assignment_id, title, description, deadline, created_by, created_at, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            ("home_ai", "AI", "", "", "T001", main.now_str(), "open"),
        )
        for student_id, archive in [("2024001", first_archive), ("2024002", second_archive)]:
            conn.execute(
                """
                INSERT INTO submissions (
                    student_id, assignment_id, file_name, file_path, md5, submit_time, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    student_id,
                    "home_ai",
                    archive.name,
                    str(archive),
                    f"md5-{student_id}",
                    main.now_str(),
                    "pending",
                ),
            )
        conn.commit()
        conn.close()

        original_key = main.DEEPSEEK_API_KEY
        original_call = main.call_deepseek_plagiarism_judge
        calls = []

        def fake_deepseek_call(
            *,
            assignment_id: str,
            pair: dict[str, object],
            api_key: str = "",
        ) -> dict[str, object]:
            calls.append((assignment_id, pair, api_key))
            return {
                "ai_similarity": 0.92,
                "likely_plagiarism": True,
                "confidence": 0.88,
                "reason": "AI detected copied structure",
                "evidence": ["same loop and accumulator pattern"],
            }

        main.DEEPSEEK_API_KEY = "test-key"
        main.call_deepseek_plagiarism_judge = fake_deepseek_call
        try:
            response = main.check_plagiarism(
                main.PlagiarismCheckRequest(
                    action="CHECK_PLAGIARISM",
                    timestamp=1,
                    payload=main.PlagiarismCheckPayload(
                        assignment_id="home_ai",
                        method="hybrid",
                        threshold=0.75,
                        ai_prefilter=0.1,
                    ),
                ),
                auth=None,
            )
        finally:
            main.DEEPSEEK_API_KEY = original_key
            main.call_deepseek_plagiarism_judge = original_call

        payload = response["payload"]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][2], "test-key")
        self.assertEqual(payload["method"], "hybrid")
        self.assertEqual(payload["ai_reviewed_count"], 1)
        self.assertEqual(payload["suspected_pair_count"], 1)
        pair = payload["suspected_pairs"][0]
        self.assertEqual(pair["ai_similarity"], 0.92)
        self.assertGreater(pair["local_similarity"], 0)

    def test_hybrid_plagiarism_accepts_teacher_provided_deepseek_key(self) -> None:
        first_archive = self.root / "teacher_key_first.tar.gz"
        second_archive = self.root / "teacher_key_second.tar.gz"
        content = "def solve(items):\n    total = sum(items)\n    return total\n"
        build_archive(first_archive, content)
        build_archive(second_archive, content)

        conn = main.get_conn()
        conn.execute(
            """
            INSERT INTO assignments (
                assignment_id, title, description, deadline, created_by, created_at, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            ("home_teacher_key", "Teacher Key", "", "", "T001", main.now_str(), "open"),
        )
        for student_id, archive in [("2024001", first_archive), ("2024002", second_archive)]:
            conn.execute(
                """
                INSERT INTO submissions (
                    student_id, assignment_id, file_name, file_path, md5, submit_time, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    student_id,
                    "home_teacher_key",
                    archive.name,
                    str(archive),
                    f"md5-{student_id}",
                    main.now_str(),
                    "pending",
                ),
            )
        conn.commit()
        conn.close()

        original_key = main.DEEPSEEK_API_KEY
        original_call = main.call_deepseek_plagiarism_judge
        calls = []

        def fake_deepseek_call(
            *,
            assignment_id: str,
            pair: dict[str, object],
            api_key: str = "",
        ) -> dict[str, object]:
            calls.append(api_key)
            return {
                "ai_similarity": 0.91,
                "likely_plagiarism": True,
                "confidence": 0.9,
                "reason": "teacher key was used",
                "evidence": [],
            }

        main.DEEPSEEK_API_KEY = ""
        main.call_deepseek_plagiarism_judge = fake_deepseek_call
        try:
            response = main.check_plagiarism(
                main.PlagiarismCheckRequest(
                    action="CHECK_PLAGIARISM",
                    timestamp=1,
                    payload=main.PlagiarismCheckPayload(
                        assignment_id="home_teacher_key",
                        method="hybrid",
                        threshold=0.75,
                        ai_prefilter=0.1,
                    ),
                ),
                auth=None,
                x_deepseek_api_key="teacher-key",
            )
        finally:
            main.DEEPSEEK_API_KEY = original_key
            main.call_deepseek_plagiarism_judge = original_call

        self.assertEqual(calls, ["teacher-key"])
        self.assertEqual(response["payload"]["suspected_pair_count"], 1)

    def test_score_stats_and_student_history(self) -> None:
        conn = main.get_conn()
        for assignment_id, title in [("home_stats_1", "Stats 1"), ("home_stats_2", "Stats 2")]:
            conn.execute(
                """
                INSERT INTO assignments (
                    assignment_id, title, description, deadline, created_by, created_at, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (assignment_id, title, "", "", "T001", main.now_str(), "open"),
            )

        rows = [
            ("2024001", "home_stats_1", 95, None),
            ("2024002", "home_stats_1", 85, 88.0),
            ("2024003", "home_stats_1", 55, None),
            ("2024001", "home_stats_2", 90, None),
        ]
        for student_id, assignment_id, score, final_score in rows:
            conn.execute(
                """
                INSERT INTO submissions (
                    student_id, assignment_id, file_name, file_path, md5,
                    submit_time, status, score, final_score
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    student_id,
                    assignment_id,
                    "answer.tar.gz",
                    str(self.root / "answer.tar.gz"),
                    "md5",
                    main.now_str(),
                    "graded",
                    score,
                    final_score,
                ),
            )
        conn.commit()
        conn.close()

        stats = main.get_assignment_score_stats("home_stats_1", auth=None)["payload"]["summary"]
        self.assertEqual(stats["count"], 3)
        self.assertEqual(stats["average"], 79.33)
        self.assertEqual(stats["median"], 88.0)
        self.assertEqual(stats["distribution"]["90_100"], 1)
        self.assertEqual(stats["distribution"]["80_89"], 1)
        self.assertEqual(stats["distribution"]["below_60"], 1)

        history = main.get_student_score_history("2024001", auth=None)["payload"]
        self.assertEqual(history["summary"]["count"], 2)
        self.assertEqual(history["summary"]["latest"], 90.0)
        self.assertEqual([item["assignment_id"] for item in history["scores"]], ["home_stats_1", "home_stats_2"])

    def test_assignment_weight_and_close_peer_bonus_are_in_score_outputs(self) -> None:
        conn = main.get_conn()
        conn.execute(
            """
            INSERT INTO assignments (
                assignment_id, title, description, deadline, created_by, created_at, status,
                assignment_weight, teacher_weight, peer_weight, bonus_threshold_1
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            ("home_weighted", "Weighted", "", "", "T001", main.now_str(), "open", 2.0, 0.7, 0.3, 5),
        )
        submission_ids: dict[str, int] = {}
        for student_id, score in [("2024001", 80), ("2024002", 90), ("2024003", 70)]:
            cur = conn.execute(
                """
                INSERT INTO submissions (
                    student_id, assignment_id, file_name, file_path, md5,
                    submit_time, status, score
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    student_id,
                    "home_weighted",
                    "answer.tar.gz",
                    str(self.root / "answer.tar.gz"),
                    f"md5-{student_id}",
                    main.now_str(),
                    "graded",
                    score,
                ),
            )
            submission_ids[student_id] = int(cur.lastrowid)
        for reviewed_student_id, peer_score in [("2024002", 91), ("2024003", 72)]:
            conn.execute(
                """
                INSERT INTO peer_reviews (
                    assignment_id, submission_id, reviewer_student_id, score, comment, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    "home_weighted",
                    submission_ids[reviewed_student_id],
                    "2024001",
                    peer_score,
                    "Close to teacher score.",
                    main.now_str(),
                ),
            )
        conn.commit()
        conn.close()

        results = main.recalculate_assignment_scores("home_weighted")
        student_row = next(item for item in results if item["student_id"] == "2024001")

        self.assertEqual(student_row["peer_bonus"], 1.0)
        self.assertEqual(student_row["final_score"], 81.0)
        self.assertEqual(student_row["assignment_weight"], 2.0)
        self.assertEqual(student_row["weighted_score"], 162.0)

        stats_scores = main.get_assignment_score_stats("home_weighted", auth=None)["payload"]["scores"]
        stats_row = next(item for item in stats_scores if item["student_id"] == "2024001")
        self.assertEqual(stats_row["teacher_score"], 80)
        self.assertIsNone(stats_row["peer_avg_score"])
        self.assertEqual(stats_row["peer_bonus"], 1.0)
        self.assertEqual(stats_row["assignment_weight"], 2.0)
        self.assertEqual(stats_row["weighted_score"], 162.0)

    def test_teacher_assignment_reports_are_scoped_to_own_assignments(self) -> None:
        conn = main.get_conn()
        for assignment_id, teacher_id in [("own_scope", "T001"), ("other_scope", "T002")]:
            conn.execute(
                """
                INSERT INTO assignments (
                    assignment_id, title, description, deadline, created_by, created_at, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (assignment_id, assignment_id, "", "", teacher_id, main.now_str(), "open"),
            )
        for student_id, assignment_id, score in [
            ("2024001", "own_scope", 95),
            ("2024001", "other_scope", 70),
        ]:
            cur = conn.execute(
                """
                INSERT INTO submissions (
                    student_id, assignment_id, file_name, file_path, md5,
                    submit_time, status, score, final_score
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    student_id,
                    assignment_id,
                    "answer.tar.gz",
                    str(self.root / "answer.tar.gz"),
                    f"md5-{assignment_id}",
                    main.now_str(),
                    "graded",
                    score,
                    float(score),
                ),
            )
            submission_id = int(cur.lastrowid)
            conn.execute(
                """
                INSERT INTO plagiarism_reports (
                    submission_id, assignment_id, student_id, plagiarism_rate,
                    scope, checked_at
                )
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    submission_id,
                    assignment_id,
                    student_id,
                    99,
                    "current_assignment",
                    main.now_str(),
                ),
            )
        conn.commit()
        conn.close()

        teacher_one = main.AuthContext(
            email="t1@example.com",
            role=main.ROLE_TEACHER,
            display_id="T001",
        )

        own_stats = main.get_assignment_score_stats("own_scope", auth=teacher_one)["payload"]
        self.assertEqual(own_stats["summary"]["count"], 1)

        history = main.get_student_score_history("2024001", auth=teacher_one)["payload"]["scores"]
        self.assertEqual([row["assignment_id"] for row in history], ["own_scope"])

        guarded_calls = [
            lambda: main.get_assignment_score_stats("other_scope", auth=teacher_one),
            lambda: main.list_final_scores("other_scope", auth=teacher_one),
            lambda: main.calculate_final_scores("other_scope", auth=teacher_one),
            lambda: main.list_assignment_plagiarism("other_scope", auth=teacher_one),
            lambda: main.check_plagiarism(
                main.PlagiarismCheckRequest(
                    action="CHECK_PLAGIARISM",
                    timestamp=1,
                    payload=main.PlagiarismCheckPayload(
                        assignment_id="other_scope",
                        method="token",
                    ),
                ),
                auth=teacher_one,
            ),
            lambda: main.config_peer_review(
                main.PeerReviewConfigRequest(
                    action="CONFIG_PEER_REVIEW",
                    timestamp=1,
                    payload=main.PeerReviewConfigPayload(
                        assignment_id="other_scope",
                        enabled=True,
                    ),
                ),
                auth=teacher_one,
            ),
        ]
        for call in guarded_calls:
            with self.assertRaises(HTTPException) as caught:
                call()
            self.assertEqual(caught.exception.status_code, 403)

    def test_ai_grading_report_uses_local_fallback_without_key(self) -> None:
        archive_path = self.root / "ai_report.tar.gz"
        build_archive(archive_path, "def solve():\n    return 42\n")
        materials_path = self.root / "requirements.zip"
        with zipfile.ZipFile(materials_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                "spec.md",
                "# Requirements\n- Implement solve().\n- Return integer 42.\n",
            )
        conn = main.get_conn()
        conn.execute(
            """
            INSERT INTO assignments (
                assignment_id, title, description, deadline, created_by, created_at, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            ("home_ai_report", "AI Report", "Solve the task.", "", "T001", main.now_str(), "open"),
        )
        conn.execute(
            """
            INSERT INTO assignment_materials (
                assignment_id, file_name, file_path, md5, file_size, uploaded_by, uploaded_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                "home_ai_report",
                materials_path.name,
                str(materials_path),
                "materials-md5",
                materials_path.stat().st_size,
                "T001",
                main.now_str(),
            ),
        )
        cur = conn.execute(
            """
            INSERT INTO submissions (
                student_id, assignment_id, file_name, file_path, md5,
                submit_time, status, score, comment
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                "2024001",
                "home_ai_report",
                archive_path.name,
                str(archive_path),
                "md5",
                main.now_str(),
                "graded",
                95,
                "Good solution.",
            ),
        )
        submission_id = int(cur.lastrowid)
        conn.commit()
        conn.close()

        original_key = main.DEEPSEEK_API_KEY
        main.DEEPSEEK_API_KEY = ""
        try:
            payload = main.get_submission_ai_grade_report(submission_id, auth=None)["payload"]
        finally:
            main.DEEPSEEK_API_KEY = original_key

        self.assertEqual(payload["source"], "local")
        self.assertEqual(payload["model"], "local-summary")
        self.assertIn("report_text", payload["report"])
        self.assertIn("Requirement Checks:", payload["report"]["report_text"])
        self.assertIn("Return integer 42", payload["report"]["requirements_excerpt"])
        self.assertIn("def solve", payload["report"]["submission_excerpt"])

    def test_ai_grading_report_refreshes_stale_cached_schema(self) -> None:
        archive_path = self.root / "ai_report_stale.tar.gz"
        build_archive(archive_path, "def solve():\n    return 42\n")
        conn = main.get_conn()
        conn.execute(
            """
            INSERT INTO assignments (
                assignment_id, title, description, deadline, created_by, created_at, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            ("home_ai_stale", "AI Report", "Return integer 42.", "", "T001", main.now_str(), "open"),
        )
        cur = conn.execute(
            """
            INSERT INTO submissions (
                student_id, assignment_id, file_name, file_path, md5, submit_time, status,
                score, comment
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                "2024001",
                "home_ai_stale",
                archive_path.name,
                str(archive_path),
                "md5",
                main.now_str(),
                "graded",
                90,
                "Good.",
            ),
        )
        submission_id = int(cur.lastrowid)
        conn.execute(
            """
            INSERT INTO ai_grading_reports (
                submission_id, assignment_id, student_id, model, source, generated_at, report_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                submission_id,
                "home_ai_stale",
                "2024001",
                "local-summary",
                "local",
                main.now_str(),
                json.dumps({"summary": "old cached report"}, ensure_ascii=False),
            ),
        )
        conn.commit()
        conn.close()

        original_key = main.DEEPSEEK_API_KEY
        main.DEEPSEEK_API_KEY = ""
        try:
            payload = main.get_submission_ai_grade_report(submission_id, auth=None)["payload"]
        finally:
            main.DEEPSEEK_API_KEY = original_key

        self.assertEqual(payload["source"], "local")
        self.assertEqual(payload["report"]["schema_version"], main.AI_GRADING_REPORT_SCHEMA_VERSION)
        self.assertIn("Requirement Checks:", payload["report"]["report_text"])
        self.assertIn("Return integer 42", payload["report"]["requirements_excerpt"])

    def test_deepseek_grading_prompt_includes_assignment_requirements(self) -> None:
        captured: dict[str, object] = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self) -> bytes:
                return json.dumps(
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": json.dumps(
                                        {
                                            "summary": "按题目要求完成了 solve。",
                                            "requirement_checks": [
                                                {
                                                    "requirement": "Return integer 42",
                                                    "status": "met",
                                                    "evidence": "submission_excerpt 中 solve() 返回 42",
                                                    "suggestion": "补充边界测试。",
                                                }
                                            ],
                                            "strengths": ["函数返回值符合要求"],
                                            "concerns": [],
                                            "suggestions": ["增加测试说明"],
                                            "score_rationale": "代码满足核心要求。",
                                        },
                                        ensure_ascii=False,
                                    )
                                }
                            }
                        ]
                    },
                    ensure_ascii=False,
                ).encode("utf-8")

        def fake_urlopen(request, timeout):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return FakeResponse()

        original_urlopen = main.urllib.request.urlopen
        main.urllib.request.urlopen = fake_urlopen
        try:
            report = main.call_deepseek_grading_report(
                {
                    "submission_id": 1,
                    "student_id": "2024001",
                    "assignment_id": "home_ai_report",
                    "assignment_title": "AI Report",
                    "assignment_description": "Solve the task.",
                    "score": 95,
                    "comment": "Good solution.",
                    "status": "graded",
                },
                "def solve():\n    return 42\n",
                "## spec.md\n- Return integer 42.",
                api_key="test-key",
            )
        finally:
            main.urllib.request.urlopen = original_urlopen

        body = captured["body"]
        user_payload = json.loads(body["messages"][1]["content"])
        self.assertIn("Return integer 42", user_payload["assignment_requirements"])
        self.assertEqual(report["schema_version"], main.AI_GRADING_REPORT_SCHEMA_VERSION)
        self.assertEqual(report["requirement_checks"][0]["status"], "met")
        self.assertIn("Requirement Checks:", report["report_text"])

    def test_peer_review_stage_and_auto_tasks_gate_reviews(self) -> None:
        conn = main.get_conn()
        conn.execute(
            """
            INSERT INTO assignments (
                assignment_id, title, description, deadline, created_by,
                created_at, status, peer_review_enabled, peer_review_stage
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            ("home_peer", "Peer", "", "", "T001", main.now_str(), "open", 1, "setup"),
        )
        for student_id in ["2024001", "2024002"]:
            conn.execute(
                """
                INSERT INTO submissions (
                    student_id, assignment_id, file_name, file_path, md5,
                    submit_time, status, score
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    student_id,
                    "home_peer",
                    "answer.tar.gz",
                    str(self.root / "answer.tar.gz"),
                    "md5",
                    main.now_str(),
                    "graded",
                    90,
                ),
            )
        conn.commit()
        conn.close()

        main.set_peer_review_stage(
            "home_peer",
            main.PeerReviewStageRequest(
                action="SET_PEER_REVIEW_STAGE",
                timestamp=1,
                payload=main.PeerReviewStagePayload(stage="peer_review"),
            ),
            auth=None,
        )
        assigned_payload = main.auto_assign_peer_review_tasks("home_peer", auth=None)["payload"]
        self.assertEqual(assigned_payload["student_count"], 2)
        self.assertEqual(assigned_payload["reviews_per_student"], 1)
        tasks = assigned_payload["tasks"]
        self.assertEqual(len(tasks), 2)

        my_tasks = main.list_my_peer_review_tasks(student_id="2024001", auth=None)["payload"]["tasks"]
        self.assertEqual(len(my_tasks), 1)
        assigned_submission_id = my_tasks[0]["submission_id"]

        response = main.submit_peer_review(
            main.PeerReviewRequest(
                action="SUBMIT_PEER_REVIEW",
                timestamp=2,
                payload=main.PeerReviewPayload(
                    reviewer_student_id="2024001",
                    submission_id=assigned_submission_id,
                    score=91,
                    comment="Good.",
                ),
            ),
            auth=None,
        )
        self.assertEqual(response["payload"]["score"], 91)

        own_submission_id = next(task["submission_id"] for task in tasks if task["reviewer_student_id"] == "2024002")
        with self.assertRaises(HTTPException) as caught:
            main.submit_peer_review(
                main.PeerReviewRequest(
                    action="SUBMIT_PEER_REVIEW",
                    timestamp=3,
                    payload=main.PeerReviewPayload(
                        reviewer_student_id="2024001",
                        submission_id=own_submission_id,
                        score=91,
                    ),
                ),
                auth=None,
            )
        self.assertEqual(caught.exception.status_code, 400)

    def test_auto_assign_peer_review_tasks_defaults_to_two_per_student(self) -> None:
        conn = main.get_conn()
        conn.execute(
            """
            INSERT INTO assignments (
                assignment_id, title, description, deadline, created_by,
                created_at, status, peer_review_enabled, peer_review_stage
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            ("home_peer_two", "Peer Two", "", "", "T001", main.now_str(), "open", 1, "peer_review"),
        )
        owners_by_submission_id: dict[int, str] = {}
        for index, student_id in enumerate(["2024001", "2024002", "2024003", "2024004"], start=1):
            cur = conn.execute(
                """
                INSERT INTO submissions (
                    student_id, assignment_id, file_name, file_path, md5,
                    submit_time, status, score
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    student_id,
                    "home_peer_two",
                    "answer.tar.gz",
                    str(self.root / "answer.tar.gz"),
                    f"md5-{student_id}",
                    f"2026-06-08 00:00:0{index}",
                    "graded",
                    90,
                ),
            )
            owners_by_submission_id[int(cur.lastrowid)] = student_id
        conn.commit()
        conn.close()

        payload = main.auto_assign_peer_review_tasks("home_peer_two", auth=None)["payload"]
        tasks = payload["tasks"]

        self.assertEqual(payload["student_count"], 4)
        self.assertEqual(payload["reviews_per_student"], 2)
        self.assertEqual(len(tasks), 8)
        self.assertEqual(Counter(task["reviewer_student_id"] for task in tasks), {
            "2024001": 2,
            "2024002": 2,
            "2024003": 2,
            "2024004": 2,
        })
        self.assertEqual(Counter(task["submission_id"] for task in tasks), {
            submission_id: 2 for submission_id in owners_by_submission_id
        })
        for task in tasks:
            self.assertNotEqual(
                task["reviewer_student_id"],
                owners_by_submission_id[task["submission_id"]],
            )


if __name__ == "__main__":
    unittest.main()
