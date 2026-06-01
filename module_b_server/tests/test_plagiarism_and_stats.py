from __future__ import annotations

from pathlib import Path
import tarfile
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
