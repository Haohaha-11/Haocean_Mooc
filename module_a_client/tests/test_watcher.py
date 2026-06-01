from __future__ import annotations

import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from module_a.api_client import Assignment, FeedbackItem, SubmissionResult
from module_a.watcher import AssignmentWatcher, snapshot_directory


class FakeClient:
    def __init__(self) -> None:
        self.submissions: list[dict[str, object]] = []

    def list_open_assignments(self) -> list[Assignment]:
        return [
            Assignment(
                assignment_id="home_001",
                title="Homework 1",
            )
        ]

    def submit_assignment(
        self,
        student_id: str,
        assignment_id: str,
        archive_path: Path,
        md5: str,
        file_name: str,
    ) -> SubmissionResult:
        self.submissions.append(
            {
                "student_id": student_id,
                "assignment_id": assignment_id,
                "archive_path": archive_path,
                "md5": md5,
                "file_name": file_name,
            }
        )
        return SubmissionResult(
            submission_id=1,
            student_id=student_id,
            assignment_id=assignment_id,
            file_name=file_name,
            md5=md5,
            status="pending",
            archive_path=str(archive_path),
        )

    def list_feedback(self, student_id: str) -> list[FeedbackItem]:
        return []


class WatcherTests(unittest.TestCase):
    def test_snapshot_directory_detects_file_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("a", encoding="utf-8")

            snapshot = snapshot_directory(root)

            self.assertIn("a.txt", snapshot)
            self.assertEqual(snapshot["a.txt"].size, 1)

    def test_sync_once_submits_only_after_debounce(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            assignment_dir = workspace / "home_001"
            assignment_dir.mkdir(parents=True)
            (assignment_dir / "answer.txt").write_text("first", encoding="utf-8")

            client = FakeClient()
            watcher = AssignmentWatcher(
                client=client,  # type: ignore[arg-type]
                student_id="2024001",
                workspace_dir=workspace,
                cache_dir=root / "archives",
                feedback_dir=root / "feedback",
                debounce_seconds=3,
                poll_interval_seconds=1,
            )

            with patch("module_a.watcher.time.monotonic", return_value=10):
                watcher.sync_once()
            self.assertEqual(len(client.submissions), 0)

            with patch("module_a.watcher.time.monotonic", return_value=14):
                watcher.sync_once()
            self.assertEqual(len(client.submissions), 1)

            with patch("module_a.watcher.time.monotonic", return_value=20):
                watcher.sync_once()
            self.assertEqual(len(client.submissions), 1)

    def test_sync_until_stable_waits_and_submits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            assignment_dir = workspace / "home_001"
            assignment_dir.mkdir(parents=True)
            (assignment_dir / "answer.txt").write_text("first", encoding="utf-8")

            client = FakeClient()
            watcher = AssignmentWatcher(
                client=client,  # type: ignore[arg-type]
                student_id="2024001",
                workspace_dir=workspace,
                cache_dir=root / "archives",
                feedback_dir=root / "feedback",
                debounce_seconds=3,
                poll_interval_seconds=1,
            )

            with (
                patch("module_a.watcher.time.monotonic", side_effect=[10, 10, 14, 14]),
                patch("module_a.watcher.time.sleep"),
            ):
                watcher.sync_until_stable(max_wait_seconds=10)

            self.assertEqual(len(client.submissions), 1)


if __name__ == "__main__":
    unittest.main()
