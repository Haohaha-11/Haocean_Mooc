from __future__ import annotations

from dataclasses import dataclass
import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests


class ModuleAApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class Assignment:
    assignment_id: str
    title: str
    description: str = ""
    deadline: str = ""
    created_by: str = ""
    created_at: str = ""
    status: str = "open"
    class_id: str | None = None
    class_name: str | None = None
    course_title: str | None = None
    assignment_weight: float = 1.0
    has_materials: bool = False
    materials_file_name: str | None = None
    materials_file_size: int | None = None
    materials_md5: str | None = None
    materials_uploaded_at: str | None = None
    materials_download_url: str | None = None


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
    joined_at: str | None = None
    student_id: str | None = None


@dataclass(frozen=True)
class SubmissionResult:
    submission_id: int
    student_id: str
    assignment_id: str
    file_name: str
    md5: str
    status: str
    archive_path: str


@dataclass(frozen=True)
class FeedbackItem:
    submission_id: int
    student_id: str
    assignment_id: str
    file_name: str
    submit_time: str
    status: str
    score: int | None
    comment: str | None
    feedback_path: str | None
    feedback_markdown: str


@dataclass(frozen=True)
class PeerReviewResult:
    assignment_id: str
    submission_id: int
    reviewer_student_id: str
    score: int


@dataclass(frozen=True)
class PeerReviewTask:
    assignment_id: str
    reviewer_student_id: str
    submission_id: int
    target_student_id: str
    assignment_title: str | None = None


class ModuleBClient:
    def __init__(
        self,
        server_url: str,
        auth_token: str = "",
        timeout: float = 10.0,
        retry_count: int = 3,
        retry_backoff_seconds: float = 1.0,
        session: requests.Session | None = None,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.auth_token = auth_token.strip()
        self.timeout = timeout
        self.retry_count = retry_count
        self.retry_backoff_seconds = retry_backoff_seconds
        self.session = session or requests.Session()

    def health(self) -> dict[str, Any]:
        response = self._request("GET", "/health")
        try:
            body = response.json()
        except ValueError as exc:
            raise ModuleAApiError(f"invalid json response: {response.text}") from exc
        if response.status_code >= 400:
            raise ModuleAApiError(response.text)
        return body

    def request_login_code(self, email: str, student_id: str) -> dict[str, Any]:
        response = self._request(
            "POST",
            "/v1/auth/request-code",
            json={
                "action": "REQUEST_LOGIN_CODE",
                "timestamp": int(time.time()),
                "payload": {
                    "email": email,
                    "role": "student",
                    "display_id": student_id,
                },
            },
        )
        return self._payload(response)

    def login_with_code(self, email: str, student_id: str, code: str) -> dict[str, Any]:
        response = self._request(
            "POST",
            "/v1/auth/login",
            json={
                "action": "LOGIN_WITH_CODE",
                "timestamp": int(time.time()),
                "payload": {
                    "email": email,
                    "role": "student",
                    "display_id": student_id,
                    "code": code,
                },
            },
        )
        payload = self._payload(response)
        token = str(payload.get("token", "")).strip()
        if token:
            self.auth_token = token
        return payload

    def list_open_assignments(self) -> list[Assignment]:
        response = self._request("GET", "/v1/assignments/open")
        payload = self._payload(response)
        return [Assignment(**item) for item in payload.get("assignments", [])]

    def get_assignment_materials(self, assignment_id: str) -> dict[str, Any]:
        response = self._request("GET", f"/v1/assignments/{quote(assignment_id)}/materials")
        return self._payload(response)

    def download_assignment_materials(self, assignment_id: str, target_dir: Path) -> Path:
        materials_payload = self.get_assignment_materials(assignment_id)
        materials = materials_payload.get("materials")
        if not isinstance(materials, dict):
            raise ModuleAApiError("assignment materials do not exist")
        file_name = str(materials.get("file_name") or f"{assignment_id}_materials")
        response = self._request("GET", f"/v1/assignments/{quote(assignment_id)}/materials/download")
        if response.status_code >= 400:
            self._payload(response)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / Path(file_name).name
        target_path.write_bytes(response.content)
        return target_path

    def join_class(self, student_id: str, join_code: str) -> ClassInfo:
        response = self._request(
            "POST",
            "/v1/classes/join",
            json={
                "action": "JOIN_CLASS",
                "timestamp": int(time.time()),
                "payload": {
                    "student_id": student_id,
                    "join_code": join_code,
                },
            },
        )
        return ClassInfo(**self._payload(response))

    def list_my_classes(self, student_id: str = "") -> list[ClassInfo]:
        kwargs: dict[str, Any] = {}
        if student_id:
            kwargs["params"] = {"student_id": student_id}
        response = self._request("GET", "/v1/classes/my", **kwargs)
        payload = self._payload(response)
        return [ClassInfo(**item) for item in payload.get("classes", [])]

    def submit_assignment(
        self,
        student_id: str,
        assignment_id: str,
        archive_path: Path,
        md5: str,
        file_name: str,
    ) -> SubmissionResult:
        metadata = {
            "action": "SUBMIT",
            "timestamp": int(time.time()),
            "payload": {
                "student_id": student_id,
                "assignment_id": assignment_id,
                "md5": md5,
                "file_name": file_name,
            },
        }
        response = self._request_upload(
            "/v1/submissions",
            archive_path=archive_path,
            file_name=file_name,
            metadata=metadata,
        )
        return SubmissionResult(**self._payload(response))

    def list_feedback(self, student_id: str) -> list[FeedbackItem]:
        response = self._request("GET", f"/v1/feedback/{student_id}")
        payload = self._payload(response)
        return [FeedbackItem(**item) for item in payload.get("feedback", [])]

    def submit_peer_review(
        self,
        reviewer_student_id: str,
        submission_id: int,
        score: int,
        comment: str = "",
    ) -> PeerReviewResult:
        response = self._request(
            "POST",
            "/v1/peer-reviews",
            json={
                "action": "SUBMIT_PEER_REVIEW",
                "timestamp": int(time.time()),
                "payload": {
                    "reviewer_student_id": reviewer_student_id,
                    "submission_id": submission_id,
                    "score": score,
                    "comment": comment,
                },
            },
        )
        return PeerReviewResult(**self._payload(response))

    def list_peer_review_tasks(
        self,
        student_id: str = "",
        assignment_id: str = "",
    ) -> list[PeerReviewTask]:
        params: dict[str, Any] = {}
        if student_id:
            params["student_id"] = student_id
        if assignment_id:
            params["assignment_id"] = assignment_id
        kwargs: dict[str, Any] = {"params": params} if params else {}
        response = self._request("GET", "/v1/peer-review/tasks/my", **kwargs)
        payload = self._payload(response)
        return [PeerReviewTask(**item) for item in payload.get("tasks", [])]

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        url = f"{self.server_url}{path}"
        last_error: Exception | None = None
        attempts = max(1, self.retry_count)
        kwargs = self._with_auth(kwargs)

        for attempt in range(1, attempts + 1):
            try:
                response = self.session.request(
                    method,
                    url,
                    timeout=self.timeout,
                    **kwargs,
                )
                if response.status_code >= 500 and attempt < attempts:
                    time.sleep(self.retry_backoff_seconds * attempt)
                    continue
                return response
            except requests.RequestException as exc:
                last_error = exc
                if attempt >= attempts:
                    break
                time.sleep(self.retry_backoff_seconds * attempt)

        raise ModuleAApiError(f"request failed: {method} {url}: {last_error}")

    def _request_upload(
        self,
        path: str,
        archive_path: Path,
        file_name: str,
        metadata: dict[str, Any],
    ) -> requests.Response:
        url = f"{self.server_url}{path}"
        last_error: Exception | None = None
        attempts = max(1, self.retry_count)
        request_kwargs = self._with_auth({})

        for attempt in range(1, attempts + 1):
            try:
                with archive_path.open("rb") as f:
                    response = self.session.request(
                        "POST",
                        url,
                        timeout=self.timeout,
                        data={"metadata": json.dumps(metadata, ensure_ascii=False)},
                        files={"file": (file_name, f, "application/gzip")},
                        **request_kwargs,
                    )
                if response.status_code >= 500 and attempt < attempts:
                    time.sleep(self.retry_backoff_seconds * attempt)
                    continue
                return response
            except requests.RequestException as exc:
                last_error = exc
                if attempt >= attempts:
                    break
                time.sleep(self.retry_backoff_seconds * attempt)

        raise ModuleAApiError(f"request failed: POST {url}: {last_error}")

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
            raise ModuleAApiError(f"invalid json response: {response.text}") from exc

        if response.status_code >= 400:
            detail = body.get("detail", body)
            message = detail.get("message", response.text) if isinstance(detail, dict) else response.text
            raise ModuleAApiError(message)

        if body.get("code") != 200:
            raise ModuleAApiError(body.get("message", "unexpected response code"))

        payload = body.get("payload")
        return payload if isinstance(payload, dict) else {}
