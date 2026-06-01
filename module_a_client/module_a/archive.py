from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import tarfile
import time


EXCLUDED_DIR_NAMES = {".git", "__pycache__", ".pytest_cache"}


@dataclass(frozen=True)
class ArchiveResult:
    path: Path
    md5: str
    file_name: str


def calc_md5(file_path: Path) -> str:
    md5 = hashlib.md5()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            md5.update(chunk)
    return md5.hexdigest()


def _tar_filter(tar_info: tarfile.TarInfo) -> tarfile.TarInfo | None:
    parts = Path(tar_info.name).parts
    if any(part in EXCLUDED_DIR_NAMES for part in parts):
        return None
    return tar_info


def build_assignment_archive(
    assignment_dir: Path,
    cache_dir: Path,
    student_id: str,
    assignment_id: str,
    timestamp: int | None = None,
) -> ArchiveResult:
    source = assignment_dir.resolve()
    if not source.exists() or not source.is_dir():
        raise FileNotFoundError(f"Assignment directory not found: {source}")

    cache_dir.mkdir(parents=True, exist_ok=True)
    archive_time = int(timestamp or time.time())
    file_name = f"{student_id}_{assignment_id}.tar.gz"
    archive_path = cache_dir / f"{archive_time}_{file_name}"

    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(source, arcname=assignment_id, filter=_tar_filter)

    return ArchiveResult(
        path=archive_path,
        md5=calc_md5(archive_path),
        file_name=file_name,
    )
