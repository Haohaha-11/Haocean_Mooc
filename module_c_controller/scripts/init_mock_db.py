from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from controller.config import load_settings
from controller.db import insert_mock_submissions


MOCK_SUBMISSIONS = [
    {
        "student_id": "S2026001",
        "student_name": "Lin Chen",
        "assignment_title": "Python Data Pipeline",
        "content": "Implemented CSV ingestion, basic validation, and a summary report.",
        "created_at": "2026-05-20T09:15:00+00:00",
    },
    {
        "student_id": "S2026002",
        "student_name": "Maya Patel",
        "assignment_title": "SQLite Practice",
        "content": "Created normalized tables and wrote queries for aggregate metrics.",
        "created_at": "2026-05-20T10:30:00+00:00",
    },
    {
        "student_id": "S2026003",
        "student_name": "Owen Brooks",
        "assignment_title": "Textual UI Prototype",
        "content": "Built a terminal dashboard with keyboard navigation and detail panes.",
        "created_at": "2026-05-21T08:45:00+00:00",
    },
    {
        "student_id": "S2026004",
        "student_name": "Nora Wang",
        "assignment_title": "Feedback Generator",
        "content": "Generated Markdown reports from review records and submission metadata.",
        "created_at": "2026-05-21T14:05:00+00:00",
    },
]


def main() -> None:
    settings = load_settings(PROJECT_ROOT)
    inserted = insert_mock_submissions(settings.db_path, MOCK_SUBMISSIONS)
    print(f"Database: {settings.db_path.relative_to(settings.project_root)}")
    print(f"Inserted mock submissions: {inserted}")


if __name__ == "__main__":
    main()
