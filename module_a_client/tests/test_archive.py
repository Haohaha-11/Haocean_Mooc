from __future__ import annotations

import tarfile
import tempfile
from pathlib import Path
import unittest

from module_a.archive import build_assignment_archive, calc_md5, preview_assignment_archive


class ArchiveTests(unittest.TestCase):
    def test_build_assignment_archive_creates_tar_gz_and_md5(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assignment_dir = root / "workspace" / "home_001"
            assignment_dir.mkdir(parents=True)
            (assignment_dir / "answer.txt").write_text("hello", encoding="utf-8")

            archive = build_assignment_archive(
                assignment_dir=assignment_dir,
                cache_dir=root / "archives",
                student_id="2024001",
                assignment_id="home_001",
                allow_zip=False,
                timestamp=123,
            )

            self.assertTrue(archive.path.exists())
            self.assertEqual(archive.file_name, "2024001_home_001.tar.gz")
            self.assertEqual(archive.md5, calc_md5(archive.path))

            with tarfile.open(archive.path, "r:gz") as tar:
                self.assertIn("assignment_home_001/answer.txt", tar.getnames())

    def test_preview_filters_cache_archives_and_system_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assignment_dir = root / "workspace" / "A1"
            assignment_dir.mkdir(parents=True)
            (assignment_dir / "main.py").write_text("print('ok')\n", encoding="utf-8")
            (assignment_dir / "report.pdf").write_bytes(b"%PDF-1.4")
            (assignment_dir / "README.md").write_text("# report\n", encoding="utf-8")
            (assignment_dir / "old_submit.zip").write_bytes(b"zip")
            (assignment_dir / "debug.log").write_text("log\n", encoding="utf-8")
            (assignment_dir / "test.db").write_text("db\n", encoding="utf-8")
            (assignment_dir / "__pycache__").mkdir()
            (assignment_dir / "__pycache__" / "x.pyc").write_bytes(b"x")
            (assignment_dir / ".git").mkdir()
            (assignment_dir / ".git" / "config").write_text("cfg\n", encoding="utf-8")
            (assignment_dir / ".venv").mkdir()
            (assignment_dir / ".venv" / "bin").mkdir(parents=True)
            (assignment_dir / ".venv" / "bin" / "python").write_text("bin\n", encoding="utf-8")
            (assignment_dir / "node_modules").mkdir()
            (assignment_dir / "node_modules" / "x.js").write_text("x\n", encoding="utf-8")

            preview = preview_assignment_archive(
                assignment_dir=assignment_dir,
                cache_dir=root / "archives",
                student_id="2024001",
                assignment_id="A1",
                allow_zip=False,
                timestamp=123,
            )

            self.assertEqual(
                preview.included_files,
                ["README.md", "main.py", "report.pdf"],
            )
            excluded_reasons = {item.relative_path: item.reason for item in preview.excluded_files}
            self.assertIn("old_submit.zip", excluded_reasons)
            self.assertTrue(excluded_reasons["old_submit.zip"].startswith("archive_requires_allow_zip"))
            self.assertIn("debug.log", excluded_reasons)
            self.assertIn("test.db", excluded_reasons)
            self.assertIn("__pycache__/x.pyc", excluded_reasons)
            self.assertIn(".git/config", excluded_reasons)
            self.assertIn(".venv/bin/python", excluded_reasons)
            self.assertIn("node_modules/x.js", excluded_reasons)
            self.assertTrue(all(not member.startswith("/") for member in preview.archive_members))
            self.assertTrue(all(".." not in member for member in preview.archive_members))
            self.assertTrue(all(member.startswith("assignment_A1/") for member in preview.archive_members))

    def test_build_assignment_archive_excludes_nested_archives_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assignment_dir = root / "workspace" / "A2"
            assignment_dir.mkdir(parents=True)
            (assignment_dir / "main.py").write_text("print('ok')\n", encoding="utf-8")
            (assignment_dir / "nested.tar.gz").write_bytes(b"archive")

            archive = build_assignment_archive(
                assignment_dir=assignment_dir,
                cache_dir=root / "archives",
                student_id="2024001",
                assignment_id="A2",
                allow_zip=False,
                timestamp=124,
            )
            with tarfile.open(archive.path, "r:gz") as tar:
                names = tar.getnames()
            self.assertIn("assignment_A2/main.py", names)
            self.assertNotIn("assignment_A2/nested.tar.gz", names)

    def test_build_assignment_archive_includes_nested_archives_when_allow_zip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assignment_dir = root / "workspace" / "A3"
            assignment_dir.mkdir(parents=True)
            (assignment_dir / "main.py").write_text("print('ok')\n", encoding="utf-8")
            (assignment_dir / "old_submit.zip").write_bytes(b"archive")

            archive = build_assignment_archive(
                assignment_dir=assignment_dir,
                cache_dir=root / "archives",
                student_id="2024001",
                assignment_id="A3",
                allow_zip=True,
                timestamp=125,
            )
            with tarfile.open(archive.path, "r:gz") as tar:
                names = tar.getnames()
            self.assertIn("assignment_A3/main.py", names)
            self.assertIn("assignment_A3/old_submit.zip", names)


if __name__ == "__main__":
    unittest.main()
