from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import time

from .api_client import Assignment, ModuleBClient
from .archive import build_assignment_archive
from .feedback import save_feedback_items


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class FileState:
    mtime_ns: int
    size: int


def assignment_dir(workspace_dir: Path, assignment_id: str) -> Path:
    return workspace_dir / assignment_id


def snapshot_directory(directory: Path) -> dict[str, FileState]:
    if not directory.exists():
        return {}

    snapshot: dict[str, FileState] = {}
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        try:
            stat = path.stat()
        except FileNotFoundError:
            continue
        rel_path = path.relative_to(directory).as_posix()
        snapshot[rel_path] = FileState(mtime_ns=stat.st_mtime_ns, size=stat.st_size)
    return snapshot


class AssignmentWatcher:
    def __init__(
        self,
        client: ModuleBClient,
        student_id: str,
        workspace_dir: Path,
        cache_dir: Path,
        feedback_dir: Path,
        debounce_seconds: float = 3.0,
        poll_interval_seconds: float = 1.0,
        assignment_filter: str = "",
        allow_zip: bool = False,
    ) -> None:
        if not student_id:
            raise ValueError("student_id is required")
        self.client = client
        self.student_id = student_id
        self.workspace_dir = workspace_dir
        self.cache_dir = cache_dir
        self.feedback_dir = feedback_dir
        self.debounce_seconds = debounce_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.assignment_filter = assignment_filter.strip()
        self.allow_zip = allow_zip
        self._last_snapshots: dict[str, dict[str, FileState]] = {}
        self._dirty_since: dict[str, float] = {}
        self._last_submitted: dict[str, dict[str, FileState]] = {}

    def sync_once(self) -> None:
        assignments = self.client.list_open_assignments()
        if self.assignment_filter:
            assignments = [
                assignment
                for assignment in assignments
                if assignment.assignment_id == self.assignment_filter
            ]
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        for assignment in assignments:
            current_snapshot = self._snapshot_assignment(assignment)
            assignment_id = assignment.assignment_id
            previous_snapshot = self._last_snapshots.get(assignment_id)

            if current_snapshot != previous_snapshot:
                self._last_snapshots[assignment_id] = current_snapshot
                if current_snapshot:
                    self._dirty_since[assignment_id] = time.monotonic()
                    LOGGER.info("change detected: assignment_id=%s", assignment_id)

            self._submit_if_stable(assignment, current_snapshot)

        saved_paths = save_feedback_items(
            self.client.list_feedback(self.student_id),
            self.feedback_dir,
        )
        for path in saved_paths:
            LOGGER.info("feedback saved: path=%s", path)

    def run_forever(self) -> None:
        LOGGER.info("module A watcher started: workspace=%s", self.workspace_dir)
        while True:
            try:
                self.sync_once()
            except Exception:
                LOGGER.exception("sync failed")
            time.sleep(self.poll_interval_seconds)

    def sync_until_stable(self, max_wait_seconds: float | None = None) -> None:
        wait_seconds = max_wait_seconds
        if wait_seconds is None:
            wait_seconds = self.debounce_seconds + self.poll_interval_seconds + 1.0
        deadline = time.monotonic() + wait_seconds

        while True:
            self.sync_once()
            if not self._dirty_since:
                return
            if time.monotonic() >= deadline:
                LOGGER.warning("sync stopped before all changes became stable")
                return
            time.sleep(self.poll_interval_seconds)

    def _snapshot_assignment(self, assignment: Assignment) -> dict[str, FileState]:
        directory = assignment_dir(self.workspace_dir, assignment.assignment_id)
        if not directory.exists():
            LOGGER.info("assignment workspace missing: assignment_id=%s path=%s", assignment.assignment_id, directory)
            return {}
        return snapshot_directory(directory)

    def _submit_if_stable(
        self,
        assignment: Assignment,
        current_snapshot: dict[str, FileState],
    ) -> None:
        assignment_id = assignment.assignment_id
        dirty_at = self._dirty_since.get(assignment_id)
        if not dirty_at or not current_snapshot:
            return
        if time.monotonic() - dirty_at < self.debounce_seconds:
            return
        if self._last_submitted.get(assignment_id) == current_snapshot:
            self._dirty_since.pop(assignment_id, None)
            return

        directory = assignment_dir(self.workspace_dir, assignment_id)
        archive = build_assignment_archive(
            assignment_dir=directory,
            cache_dir=self.cache_dir,
            student_id=self.student_id,
            assignment_id=assignment_id,
            allow_zip=self.allow_zip,
        )
        result = self.client.submit_assignment(
            student_id=self.student_id,
            assignment_id=assignment_id,
            archive_path=archive.path,
            md5=archive.md5,
            file_name=archive.file_name,
        )
        self._last_submitted[assignment_id] = current_snapshot
        self._dirty_since.pop(assignment_id, None)
        LOGGER.info(
            "submission accepted: submission_id=%s assignment_id=%s status=%s",
            result.submission_id,
            result.assignment_id,
            result.status,
        )
