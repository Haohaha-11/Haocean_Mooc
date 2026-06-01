from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Any
from urllib.parse import quote

import requests

from .models import Submission
from .status import local_to_service_status, service_to_local_status


class ModuleCApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class GradeResult:
    submission_id: int
    student_id: str
    assignment_id: str
    score: int
    status: str
    feedback_path: str


@dataclass(frozen=True)
class ClassInfo:
    class_id: str
    class_name: str
    course_id: str
    course_title: str
    join_code: str
    teacher_id: str
    created_at: str
    status: str


class ModuleBRepository:
    def __init__(
        self,
        base_url: str,
        teacher_id: str,
        auth_token: str = "",
        timeout: float = 10.0,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.teacher_id = teacher_id
        self.auth_token = auth_token.strip()
        self.timeout = timeout
        self.session = session or requests.Session()
        self._pending_cache: dict[int, Submission] = {}
        self._reviewed_cache: dict[int, Submission] = {}

    def health(self) -> dict[str, Any]:
        response = self._request("GET", "/health")
        try:
            body = response.json()
        except ValueError as exc:
            raise ModuleCApiError(f"invalid json response: {response.text}") from exc
        if response.status_code >= 400:
            raise ModuleCApiError(response.text)
        return body

    def request_login_code(self, email: str, teacher_id: str) -> dict[str, Any]:
        response = self._request(
            "POST",
            "/v1/auth/request-code",
            json={
                "action": "REQUEST_LOGIN_CODE",
                "timestamp": int(time.time()),
                "payload": {
                    "email": email,
                    "role": "teacher",
                    "display_id": teacher_id,
                },
            },
        )
        return self._payload(response)

    def login_with_code(self, email: str, teacher_id: str, code: str) -> dict[str, Any]:
        response = self._request(
            "POST",
            "/v1/auth/login",
            json={
                "action": "LOGIN_WITH_CODE",
                "timestamp": int(time.time()),
                "payload": {
                    "email": email,
                    "role": "teacher",
                    "display_id": teacher_id,
                    "code": code,
                },
            },
        )
        payload = self._payload(response)
        token = str(payload.get("token", "")).strip()
        if token:
            self.auth_token = token
        return payload

    def list_submissions(self, status: str | None = None) -> list[Submission]:
        if status == "pending":
            return self._list_pending()
        if status == "approved":
            return [
                submission
                for submission in self._reviewed_cache.values()
                if submission.status == "approved"
            ]
        if status == "rejected":
            return [
                submission
                for submission in self._reviewed_cache.values()
                if submission.status == "rejected"
            ]

        pending = self._list_pending()
        reviewed = sorted(self._reviewed_cache.values(), key=lambda item: (item.created_at, item.id))
        return [*pending, *reviewed]

    def get_submission(self, submission_id: int) -> Submission | None:
        if submission_id in self._pending_cache:
            return self._pending_cache[submission_id]
        if submission_id in self._reviewed_cache:
            return self._reviewed_cache[submission_id]

        for submission in self._list_pending():
            if submission.id == submission_id:
                return submission
        return None

    def grade_submission(
        self,
        submission_id: int,
        score: float,
        comment: str,
        status: str = "graded",
    ) -> Submission:
        if not float(score).is_integer():
            raise ValueError("Module B requires an integer score")

        service_status = local_to_service_status(status)
        if service_status not in {"graded", "rejected"}:
            raise ValueError("status must be graded or rejected")

        response = self._request(
            "POST",
            "/v1/submissions/grade",
            json={
                "action": "GRADE",
                "timestamp": int(time.time()),
                "payload": {
                    "submission_id": submission_id,
                    "teacher_id": self.teacher_id,
                    "score": int(score),
                    "comment": comment,
                    "status": service_status,
                },
            },
        )
        result = GradeResult(**self._payload(response))
        cached = self._pending_cache.pop(submission_id, None)
        submission = self._grade_result_to_submission(result, cached, comment)
        self._reviewed_cache[submission.id] = submission
        return submission

    def create_class(
        self,
        class_name: str,
        course_title: str = "",
        class_id: str = "",
        course_id: str = "",
        join_code: str = "",
    ) -> ClassInfo:
        response = self._request(
            "POST",
            "/v1/classes",
            json={
                "action": "CREATE_CLASS",
                "timestamp": int(time.time()),
                "payload": {
                    "teacher_id": self.teacher_id,
                    "class_name": class_name,
                    "course_title": course_title,
                    "class_id": class_id,
                    "course_id": course_id,
                    "join_code": join_code,
                },
            },
        )
        return ClassInfo(**self._payload(response))

    def list_classes(self) -> list[ClassInfo]:
        response = self._request("GET", "/v1/classes")
        payload = self._payload(response)
        return [ClassInfo(**item) for item in payload.get("classes", [])]

    def create_assignment(
        self,
        assignment_id: str,
        title: str,
        description: str = "",
        deadline: str = "",
        class_id: str = "",
    ) -> dict[str, Any]:
        response = self._request(
            "POST",
            "/v1/assignments",
            json={
                "action": "CREATE_ASSIGNMENT",
                "timestamp": int(time.time()),
                "payload": {
                    "teacher_id": self.teacher_id,
                    "assignment_id": assignment_id,
                    "title": title,
                    "description": description,
                    "deadline": deadline,
                    "class_id": class_id or None,
                },
            },
        )
        return self._payload(response)

    def list_plagiarism(self, assignment_id: str) -> list[dict[str, Any]]:
        response = self._request("GET", f"/v1/assignments/{quote(assignment_id)}/plagiarism")
        payload = self._payload(response)
        return list(payload.get("reports", []))

    def get_score_stats(self, assignment_id: str) -> dict[str, Any]:
        response = self._request("GET", f"/v1/assignments/{quote(assignment_id)}/score-stats")
        return self._payload(response)

    def get_student_history(self, student_id: str) -> dict[str, Any]:
        response = self._request("GET", f"/v1/students/{quote(student_id)}/score-history")
        return self._payload(response)

    def calculate_final_scores(self, assignment_id: str) -> list[dict[str, Any]]:
        response = self._request(
            "POST",
            f"/v1/assignments/{quote(assignment_id)}/calculate-final-scores",
        )
        payload = self._payload(response)
        return list(payload.get("results", []))

    def create_archive(
        self,
        archive_name: str = "",
        note: str = "",
        include_db: bool = True,
        include_submissions: bool = True,
        include_feedback: bool = True,
        include_docs: bool = True,
    ) -> dict[str, Any]:
        response = self._request(
            "POST",
            "/v1/archives/course",
            json={
                "action": "CREATE_COURSE_ARCHIVE",
                "timestamp": int(time.time()),
                "payload": {
                    "archive_name": archive_name or None,
                    "note": note,
                    "include_db": include_db,
                    "include_submissions": include_submissions,
                    "include_feedback": include_feedback,
                    "include_docs": include_docs,
                },
            },
        )
        return self._payload(response)

    def list_archives(self) -> list[dict[str, Any]]:
        response = self._request("GET", "/v1/archives")
        payload = self._payload(response)
        return list(payload.get("archives", []))

    def download_archive(self, archive_name: str, target_dir: Path) -> Path:
        return self._download_file(
            f"/v1/archives/download/{quote(archive_name)}",
            target_dir,
            archive_name,
        )

    def download_submission(
        self,
        submission_id: int,
        target_dir: Path,
        file_name: str = "",
    ) -> Path:
        return self._download_file(
            f"/v1/submissions/{submission_id}/download",
            target_dir,
            file_name or f"submission_{submission_id}.tar.gz",
        )

    def _list_pending(self) -> list[Submission]:
        response = self._request("GET", "/v1/submissions/pending")
        payload = self._payload(response)
        submissions = [
            self._pending_item_to_submission(item)
            for item in payload.get("submissions", [])
        ]
        self._pending_cache = {submission.id: submission for submission in submissions}
        return submissions

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        kwargs = self._with_auth(kwargs)
        try:
            return self.session.request(
                method,
                f"{self.base_url}{path}",
                timeout=self.timeout,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise ModuleCApiError(f"request failed: {method} {path}: {exc}") from exc

    def _download_file(self, path: str, target_dir: Path, file_name: str) -> Path:
        response = self._request("GET", path)
        if response.status_code >= 400:
            self._payload(response)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / Path(file_name).name
        target_path.write_bytes(response.content)
        return target_path

    def _with_auth(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        if not self.auth_token:
            return kwargs
        headers = dict(kwargs.get("headers") or {})
        headers.setdefault("Authorization", f"Bearer {self.auth_token}")
        return {**kwargs, "headers": headers}

    def _payload(self, response: requests.Response) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError as exc:
            raise ModuleCApiError(f"invalid json response: {response.text}") from exc

        if response.status_code >= 400:
            detail = body.get("detail", body)
            message = detail.get("message", response.text) if isinstance(detail, dict) else response.text
            raise ModuleCApiError(message)

        if body.get("code") != 200:
            raise ModuleCApiError(body.get("message", "unexpected response code"))

        payload = body.get("payload")
        return payload if isinstance(payload, dict) else {}

    def _pending_item_to_submission(self, item: dict[str, Any]) -> Submission:
        submission_id = int(item["submission_id"])
        student_id = str(item["student_id"])
        assignment_id = str(item["assignment_id"])
        content = (
            f"File Name: {item.get('file_name', '')}\n"
            f"Archive Path: {item.get('file_path', '')}\n"
            f"MD5: {item.get('md5', '')}"
        )
        return Submission(
            id=submission_id,
            student_id=student_id,
            student_name=student_id,
            assignment_title=assignment_id,
            content=content,
            status=service_to_local_status(str(item.get("status", "pending"))),
            created_at=str(item.get("submit_time", "")),
        )

    def _grade_result_to_submission(
        self,
        result: GradeResult,
        cached: Submission | None,
        comment: str,
    ) -> Submission:
        return Submission(
            id=result.submission_id,
            student_id=result.student_id,
            student_name=cached.student_name if cached else result.student_id,
            assignment_title=cached.assignment_title if cached else result.assignment_id,
            content=cached.content if cached else f"Feedback Path: {result.feedback_path}",
            status=service_to_local_status(result.status),
            created_at=cached.created_at if cached else "",
            score=result.score,
            comment=comment,
            reviewed_at="",
            feedback_path=result.feedback_path,
        )
