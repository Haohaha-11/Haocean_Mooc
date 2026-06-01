from __future__ import annotations

from pathlib import Path

import pytest

from controller.feedback import generate_feedback_markdown
from controller.models import Submission


def make_submission() -> Submission:
    return Submission(
        id=7,
        student_id="S2026007",
        student_name="Grace Lee",
        assignment_title="Markdown Report",
        content="The submitted assignment body.",
        status="pending",
        created_at="2026-05-20T00:00:00+00:00",
    )


def test_generate_feedback_markdown_writes_expected_content(tmp_path: Path) -> None:
    output_path = generate_feedback_markdown(
        make_submission(),
        91,
        "Clear result and readable explanation.",
        tmp_path,
    )

    content = output_path.read_text(encoding="utf-8")

    assert output_path.name == "submission_7_S2026007_feedback.md"
    assert "Submission ID: 7" in content
    assert "Student Name: Grace Lee" in content
    assert "Assignment: Markdown Report" in content
    assert "Score: 91" in content
    assert "Clear result and readable explanation." in content
    assert "The submitted assignment body." in content


def test_generate_feedback_requires_comment(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        generate_feedback_markdown(make_submission(), 90, "   ", tmp_path)
