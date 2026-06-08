from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest

from controller.tui import StudentStatsScreen, extract_submission_archive, find_readable_submission_file


def test_student_stats_screen_mentions_close_keys() -> None:
    screen = StudentStatsScreen(
        "2024001",
        {
            "summary": {"count": 1, "average": 90, "best": 90, "latest": 90},
            "scores": [],
        },
    )

    assert "Press Enter, Esc, or q to close." in screen._render_stats()


def test_extract_submission_archive_blocks_path_traversal(tmp_path: Path) -> None:
    archive_path = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tar:
        payload = b"unsafe"
        member = tarfile.TarInfo("../escape.txt")
        member.size = len(payload)
        tar.addfile(member, io.BytesIO(payload))

    with pytest.raises(ValueError):
        extract_submission_archive(archive_path)


def test_find_readable_submission_file_prefers_markdown_readme(tmp_path: Path) -> None:
    extracted_dir = tmp_path / "submission"
    extracted_dir.mkdir()
    (extracted_dir / "notes.txt").write_text("notes", encoding="utf-8")
    (extracted_dir / "README.md").write_text("# report", encoding="utf-8")

    assert find_readable_submission_file(extracted_dir) == extracted_dir / "README.md"
