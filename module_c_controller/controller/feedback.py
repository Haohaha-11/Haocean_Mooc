from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re

from .models import Submission


def _safe_filename_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return cleaned.strip("_") or "submission"


def generate_feedback_markdown(
    submission: Submission,
    score: float,
    comment: str,
    feedback_dir: Path,
) -> Path:
    if not comment.strip():
        raise ValueError("Comment must not be empty")

    feedback_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    filename = (
        f"submission_{submission.id}_"
        f"{_safe_filename_part(submission.student_id)}_feedback.md"
    )
    output_path = feedback_dir / filename
    content = f"""# Assignment Feedback

## Submission

- Submission ID: {submission.id}
- Student ID: {submission.student_id}
- Student Name: {submission.student_name}
- Assignment: {submission.assignment_title}
- Score: {score:g}
- Reviewed At: {generated_at}

## Comment

{comment.strip()}

## Original Submission

{submission.content.strip()}
"""
    output_path.write_text(content, encoding="utf-8")
    return output_path
