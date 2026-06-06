from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path, PurePosixPath
import re
import tarfile
import time


EXCLUDED_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
}
EXCLUDED_FILE_NAMES = {".DS_Store", "Thumbs.db"}
EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".log",
    ".tmp",
    ".db",
    ".sqlite",
    ".sqlite3",
}
ARCHIVE_SUFFIXES = {".zip", ".tar", ".gz", ".7z", ".rar"}
ALLOWED_SUFFIXES = {
    ".py",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".java",
    ".js",
    ".html",
    ".css",
    ".md",
    ".txt",
    ".pdf",
    ".docx",
    ".xlsx",
    ".pptx",
    ".ipynb",
    ".png",
    ".jpg",
    ".jpeg",
}


@dataclass(frozen=True)
class ArchiveResult:
    path: Path
    md5: str
    file_name: str


@dataclass(frozen=True)
class ExcludedFile:
    relative_path: str
    reason: str


@dataclass(frozen=True)
class ArchivePreview:
    assignment_id: str
    workspace_path: Path
    included_files: list[str]
    excluded_files: list[ExcludedFile]
    archive_path: Path
    archive_members: list[str]


def calc_md5(file_path: Path) -> str:
    md5 = hashlib.md5()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            md5.update(chunk)
    return md5.hexdigest()


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()).strip("_") or "assignment"


def _collect_assignment_files(
    assignment_dir: Path,
    *,
    allow_zip: bool,
) -> tuple[list[Path], list[ExcludedFile]]:
    included: list[Path] = []
    excluded: list[ExcludedFile] = []
    for file_path in sorted(p for p in assignment_dir.rglob("*") if p.is_file()):
        rel_path = file_path.relative_to(assignment_dir)
        rel_posix = rel_path.as_posix()
        parts = PurePosixPath(rel_posix).parts

        excluded_dir = next((part for part in parts[:-1] if part in EXCLUDED_DIR_NAMES), None)
        if excluded_dir is not None:
            excluded.append(ExcludedFile(rel_posix, f"excluded_directory:{excluded_dir}"))
            continue

        file_name = file_path.name
        if file_name in EXCLUDED_FILE_NAMES:
            excluded.append(ExcludedFile(rel_posix, f"excluded_file:{file_name}"))
            continue

        suffix = file_path.suffix.lower()
        if suffix in EXCLUDED_SUFFIXES:
            excluded.append(ExcludedFile(rel_posix, f"excluded_suffix:{suffix}"))
            continue

        if suffix in ARCHIVE_SUFFIXES and not allow_zip:
            excluded.append(ExcludedFile(rel_posix, f"archive_requires_allow_zip:{suffix}"))
            continue

        if suffix in ALLOWED_SUFFIXES or (allow_zip and suffix in ARCHIVE_SUFFIXES):
            included.append(file_path)
            continue

        excluded.append(ExcludedFile(rel_posix, f"unsupported_suffix:{suffix or '<none>'}"))
    return included, excluded


def _build_archive(
    assignment_dir: Path,
    cache_dir: Path,
    student_id: str,
    assignment_id: str,
    *,
    allow_zip: bool,
    timestamp: int | None = None,
) -> tuple[ArchiveResult, list[str], list[ExcludedFile], list[str]]:
    included_paths, excluded_files = _collect_assignment_files(
        assignment_dir,
        allow_zip=allow_zip,
    )

    cache_dir.mkdir(parents=True, exist_ok=True)
    archive_time = int(timestamp or time.time())
    file_name = f"{student_id}_{assignment_id}.tar.gz"
    archive_path = cache_dir / f"{archive_time}_{file_name}"
    archive_root = f"assignment_{_safe_name(assignment_id)}"

    included_rel_paths: list[str] = []
    archive_members: list[str] = []
    with tarfile.open(archive_path, "w:gz") as tar:
        for path in included_paths:
            rel_path = path.relative_to(assignment_dir).as_posix()
            arcname = f"{archive_root}/{rel_path}"
            tar.add(path, arcname=arcname)
            included_rel_paths.append(rel_path)
            archive_members.append(arcname)

    return (
        ArchiveResult(
            path=archive_path,
            md5=calc_md5(archive_path),
            file_name=file_name,
        ),
        included_rel_paths,
        excluded_files,
        archive_members,
    )


def build_assignment_archive(
    assignment_dir: Path,
    cache_dir: Path,
    student_id: str,
    assignment_id: str,
    allow_zip: bool = False,
    timestamp: int | None = None,
) -> ArchiveResult:
    source = assignment_dir.resolve()
    if not source.exists() or not source.is_dir():
        raise FileNotFoundError(f"Assignment directory not found: {source}")
    result, _included, _excluded, _members = _build_archive(
        source,
        cache_dir,
        student_id,
        assignment_id,
        allow_zip=allow_zip,
        timestamp=timestamp,
    )
    return result


def preview_assignment_archive(
    assignment_dir: Path,
    cache_dir: Path,
    student_id: str,
    assignment_id: str,
    *,
    allow_zip: bool = False,
    timestamp: int | None = None,
) -> ArchivePreview:
    source = assignment_dir.resolve()
    if not source.exists() or not source.is_dir():
        raise FileNotFoundError(f"Assignment directory not found: {source}")

    result, included, excluded, members = _build_archive(
        source,
        cache_dir,
        student_id,
        assignment_id,
        allow_zip=allow_zip,
        timestamp=timestamp,
    )
    return ArchivePreview(
        assignment_id=assignment_id,
        workspace_path=source,
        included_files=included,
        excluded_files=excluded,
        archive_path=result.path,
        archive_members=members,
    )
