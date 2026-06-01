from __future__ import annotations

import tarfile
import tempfile
from pathlib import Path
import unittest

from module_a.archive import build_assignment_archive, calc_md5


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
                timestamp=123,
            )

            self.assertTrue(archive.path.exists())
            self.assertEqual(archive.file_name, "2024001_home_001.tar.gz")
            self.assertEqual(archive.md5, calc_md5(archive.path))

            with tarfile.open(archive.path, "r:gz") as tar:
                self.assertIn("home_001/answer.txt", tar.getnames())


if __name__ == "__main__":
    unittest.main()
