from __future__ import annotations

from pathlib import Path
import re
import tarfile
import tempfile
import unittest
import zipfile

from app import main


def add_file_to_tar(tar: tarfile.TarFile, path: Path, arcname: str) -> None:
    tar.add(path, arcname=arcname)


class ArchiveExportBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_db_path = main.DB_PATH
        self.original_archive_dir = main.ARCHIVE_DIR
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        main.DB_PATH = self.root / "engine.db"
        main.ARCHIVE_DIR = self.root / "archives"
        main.ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        main.init_db()
        main.init_extra_db()

    def tearDown(self) -> None:
        main.DB_PATH = self.original_db_path
        main.ARCHIVE_DIR = self.original_archive_dir
        self.tmp.cleanup()

    def _build_submission_archive(
        self,
        archive_name: str,
        file_mapping: dict[str, bytes],
    ) -> Path:
        archive_path = self.root / archive_name
        with tarfile.open(archive_path, "w:gz") as tar:
            for arcname, content in file_mapping.items():
                temp_file = self.root / f"tmp_{archive_name.replace('.', '_')}_{len(content)}"
                temp_file.write_bytes(content)
                add_file_to_tar(tar, temp_file, arcname)
        return archive_path

    def _build_submission_zip(
        self,
        archive_name: str,
        file_mapping: dict[str, bytes],
    ) -> Path:
        archive_path = self.root / archive_name
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for arcname, content in file_mapping.items():
                zf.writestr(arcname, content)
        return archive_path

    def test_course_archive_exports_flat_filtered_homework_bundle(self) -> None:
        first_archive = self._build_submission_archive(
            "s1.tar.gz",
            {
                "src/main.py": b"print('student1')\n",
                "src/include/math.hpp": b"#pragma once\n",
                "tests/main.py": b"print('student1 test')\n",
                ".git/config": b"ignored",
                "logs/run.log": b"ignored",
                "cache/data.db": b"ignored",
                "report .md": b"# report\n",
            },
        )
        second_archive = self._build_submission_archive(
            "s2.tar.gz",
            {
                "main.py": b"print('student2')\n",
                "slides/final.pptx": b"PPTX",
                "notes/Thumbs.db": b"ignored",
                "__pycache__/x.pyc": b"ignored",
                "venv/bin/python": b"ignored",
                ".mypy_cache/1.json": b"ignored",
                ".pytest_cache/v/cache": b"ignored",
                "实验 报告.py": b"print('unicode file')\n",
            },
        )
        third_archive = self._build_submission_zip(
            "s3.zip",
            {
                "report/main.py": b"print('zip submission')\n",
                "report/old_submit.zip": b"nested zip should be ignored",
                "report/debug.log": b"log should be ignored",
            },
        )

        conn = main.get_conn()
        conn.execute(
            """
            INSERT INTO assignments (
                assignment_id, title, description, deadline, created_by, created_at, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            ("A1", "Homework A1", "", "", "T001", main.now_str(), "open"),
        )
        conn.execute(
            """
            INSERT INTO submissions (
                student_id, assignment_id, file_name, file_path, md5, submit_time, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            ("20240001", "A1", "s1.tar.gz", str(first_archive), "m1", main.now_str(), "pending"),
        )
        conn.execute(
            """
            INSERT INTO submissions (
                student_id, assignment_id, file_name, file_path, md5, submit_time, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            ("20240002", "A1", "s2.tar.gz", str(second_archive), "m2", main.now_str(), "pending"),
        )
        conn.execute(
            """
            INSERT INTO submissions (
                student_id, assignment_id, file_name, file_path, md5, submit_time, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            ("20240003", "A1", "s3.zip", str(third_archive), "m3", main.now_str(), "pending"),
        )
        conn.commit()
        conn.close()

        response = main.create_course_archive(
            main.ArchiveRequest(
                action="CREATE_COURSE_ARCHIVE",
                timestamp=1,
                payload=main.ArchivePayload(
                    archive_name="course_bundle.zip",
                    note="bundle",
                    include_submissions=True,
                ),
            ),
            auth=None,
        )

        zip_path = Path(response["payload"]["archive_path"])
        self.assertTrue(zip_path.exists())

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()

        self.assertTrue(names, "archive should contain exported homework files")
        self.assertTrue(
            all(name.startswith("assignment_A1_homework_files/") for name in names),
            "all files should be in one flat assignment folder",
        )
        self.assertTrue(all(name.count("/") == 1 for name in names), "zip should be flat under one folder")
        self.assertTrue(
            all(
                "__pycache__" not in name
                and ".git" not in name
                and "venv" not in name
                and ".mypy_cache" not in name
                and ".pytest_cache" not in name
                for name in names
            ),
            "excluded directories must not appear in archive",
        )
        self.assertTrue(
            all(not name.endswith((".db", ".log", ".pyc")) for name in names),
            "excluded system/cache files must not appear in archive",
        )
        self.assertTrue(
            any(name.endswith("_main.py") and "_20240001_" in name for name in names),
            "student 1 main.py should be prefixed and exported",
        )
        self.assertTrue(
            any(name.endswith("_main.py") and "_20240002_" in name for name in names),
            "student 2 main.py should be prefixed and exported",
        )
        self.assertTrue(
            any("_main_2.py" in name for name in names),
            "duplicate basename from same submission should be deduplicated",
        )
        self.assertTrue(
            any(name.endswith(".py") and "_20240002_" in name for name in names),
            "unicode/space filename should be sanitized and exported",
        )
        self.assertTrue(
            any(name.endswith(".hpp") and "_20240001_" in name for name in names),
            "allowed code headers should be exported",
        )
        self.assertTrue(
            any(name.endswith(".pptx") and "_20240002_" in name for name in names),
            "allowed office files should be exported",
        )
        self.assertTrue(
            any(name.endswith("_main.py") and "_20240003_" in name for name in names),
            "zip submission should be unpacked and exported as regular homework files",
        )
        self.assertFalse(
            any(name.endswith((".zip", ".tar", ".gz")) for name in names),
            "teacher archive must not include nested archives",
        )
        for name in names:
            base_name = Path(name).name
            self.assertIsNotNone(
                re.fullmatch(r"[A-Za-z0-9._-]+", base_name),
                "exported file names should be safe for unzip on teacher machines",
            )


if __name__ == "__main__":
    unittest.main()
