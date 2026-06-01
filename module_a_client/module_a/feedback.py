from __future__ import annotations

from pathlib import Path
import re

from .api_client import FeedbackItem


def _safe_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return cleaned or "unknown"


def save_feedback_items(feedback_items: list[FeedbackItem], feedback_dir: Path) -> list[Path]:
    feedback_dir.mkdir(parents=True, exist_ok=True)
    saved_paths: list[Path] = []

    for item in feedback_items:
        if not item.feedback_markdown:
            continue
        assignment_id = _safe_part(item.assignment_id)
        path = feedback_dir / assignment_id / f"submission_{item.submission_id}_feedback.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item.feedback_markdown, encoding="utf-8")
        saved_paths.append(path)

    return saved_paths
