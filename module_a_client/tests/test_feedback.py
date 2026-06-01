from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from module_a.api_client import FeedbackItem
from module_a.feedback import save_feedback_items


class FeedbackTests(unittest.TestCase):
    def test_save_feedback_items_writes_markdown(self) -> None:
        item = FeedbackItem(
            submission_id=1,
            student_id="2024001",
            assignment_id="home/001",
            file_name="submission.tar.gz",
            submit_time="2026-05-27 10:10:00",
            status="graded",
            score=95,
            comment="ok",
            feedback_path="/server/path",
            feedback_markdown="# feedback",
        )

        with tempfile.TemporaryDirectory() as tmp:
            saved = save_feedback_items([item], Path(tmp))

            self.assertEqual(len(saved), 1)
            self.assertTrue(saved[0].exists())
            self.assertEqual(saved[0].read_text(encoding="utf-8"), "# feedback")
            self.assertIn("home_001", saved[0].as_posix())


if __name__ == "__main__":
    unittest.main()
