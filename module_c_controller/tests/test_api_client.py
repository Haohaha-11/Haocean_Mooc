from __future__ import annotations

import json

import pytest

from controller.api_client import ModuleBRepository, ModuleCApiError


class FakeResponse:
    def __init__(self, status_code: int, body: dict[str, object]) -> None:
        self.status_code = status_code
        self._body = body
        self.text = json.dumps(body, ensure_ascii=False)

    def json(self) -> dict[str, object]:
        return self._body


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def request(self, method: str, url: str, timeout: float, **kwargs: object) -> FakeResponse:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "timeout": timeout,
                "kwargs": kwargs,
            }
        )
        return self.responses.pop(0)


def test_list_pending_maps_module_b_fields_to_submission() -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "code": 200,
                    "message": "pending submissions returned",
                    "payload": {
                        "submissions": [
                            {
                                "submission_id": 7,
                                "student_id": "2024001",
                                "assignment_id": "home_001",
                                "file_name": "2024001_home_001.tar.gz",
                                "file_path": "/server/archive.tar.gz",
                                "md5": "abc",
                                "submit_time": "2026-05-27 10:10:00",
                                "status": "pending",
                            }
                        ]
                    },
                },
            )
        ]
    )
    repo = ModuleBRepository("http://server", "T001", session=session)  # type: ignore[arg-type]

    submissions = repo.list_submissions("pending")

    assert len(submissions) == 1
    assert submissions[0].id == 7
    assert submissions[0].student_id == "2024001"
    assert submissions[0].assignment_title == "home_001"
    assert submissions[0].status == "pending"
    assert "MD5: abc" in submissions[0].content
    assert session.calls[0]["url"] == "http://server/v1/submissions/pending"


def test_grade_submission_sends_grade_and_maps_graded_to_approved() -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "code": 200,
                    "message": "pending submissions returned",
                    "payload": {
                        "submissions": [
                            {
                                "submission_id": 7,
                                "student_id": "2024001",
                                "assignment_id": "home_001",
                                "file_name": "2024001_home_001.tar.gz",
                                "file_path": "/server/archive.tar.gz",
                                "md5": "abc",
                                "submit_time": "2026-05-27 10:10:00",
                                "status": "pending",
                            }
                        ]
                    },
                },
            ),
            FakeResponse(
                200,
                {
                    "code": 200,
                    "message": "submission graded",
                    "payload": {
                        "submission_id": 7,
                        "student_id": "2024001",
                        "assignment_id": "home_001",
                        "score": 95,
                        "status": "graded",
                        "feedback_path": "/server/feedback.md",
                    },
                },
            ),
        ]
    )
    repo = ModuleBRepository("http://server", "T001", session=session)  # type: ignore[arg-type]
    repo.list_submissions("pending")

    updated = repo.grade_submission(7, 95, "Good work.", status="graded")

    assert updated.status == "approved"
    assert updated.score == 95
    assert updated.feedback_path == "/server/feedback.md"

    grade_call = session.calls[1]
    assert grade_call["method"] == "POST"
    payload = grade_call["kwargs"]["json"]["payload"]  # type: ignore[index]
    assert grade_call["url"] == "http://server/v1/submissions/grade"
    assert grade_call["kwargs"]["json"]["action"] == "GRADE"  # type: ignore[index]
    assert payload["teacher_id"] == "T001"
    assert payload["status"] == "graded"


def test_grade_submission_rejects_fractional_score_for_module_b() -> None:
    repo = ModuleBRepository("http://server", "T001")

    with pytest.raises(ValueError, match="integer score"):
        repo.grade_submission(7, 87.5, "Half point.", status="graded")


def test_error_response_reads_fastapi_detail() -> None:
    repo = ModuleBRepository("http://server", "T001")
    response = FakeResponse(
        400,
        {"detail": {"code": 400, "message": "submission is not pending"}},
    )

    with pytest.raises(ModuleCApiError, match="submission is not pending"):
        repo._payload(response)  # type: ignore[arg-type]


def test_auth_token_is_sent_as_bearer_header() -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "code": 200,
                    "message": "pending submissions returned",
                    "payload": {"submissions": []},
                },
            )
        ]
    )
    repo = ModuleBRepository(
        "http://server",
        "T001",
        auth_token="token-abc",
        session=session,  # type: ignore[arg-type]
    )

    repo.list_submissions("pending")

    headers = session.calls[0]["kwargs"]["headers"]  # type: ignore[index]
    assert headers["Authorization"] == "Bearer token-abc"


def test_create_class_sends_teacher_payload() -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "code": 200,
                    "message": "class created",
                    "payload": {
                        "class_id": "cs101",
                        "class_name": "CS101 Spring",
                        "course_id": "course_cs",
                        "course_title": "Computer Science",
                        "join_code": "JOIN101",
                        "teacher_id": "T001",
                        "created_at": "2026-06-01 10:00:00",
                        "status": "active",
                    },
                },
            )
        ]
    )
    repo = ModuleBRepository("http://server", "T001", session=session)  # type: ignore[arg-type]

    created = repo.create_class(
        class_name="CS101 Spring",
        course_title="Computer Science",
        class_id="cs101",
        course_id="course_cs",
        join_code="JOIN101",
    )

    assert created.class_id == "cs101"
    call = session.calls[0]
    assert call["url"] == "http://server/v1/classes"
    assert call["kwargs"]["json"]["action"] == "CREATE_CLASS"  # type: ignore[index]
    payload = call["kwargs"]["json"]["payload"]  # type: ignore[index]
    assert payload["teacher_id"] == "T001"
    assert payload["join_code"] == "JOIN101"


def test_teacher_reports_call_expected_endpoints() -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "code": 200,
                    "message": "plagiarism reports returned",
                    "payload": {
                        "assignment_id": "home_001",
                        "reports": [
                            {
                                "submission_id": 7,
                                "student_id": "2024001",
                                "plagiarism_rate": 92.5,
                            }
                        ],
                    },
                },
            ),
            FakeResponse(
                200,
                {
                    "code": 200,
                    "message": "score statistics returned",
                    "payload": {
                        "assignment_id": "home_001",
                        "summary": {"count": 1},
                        "scores": [],
                    },
                },
            ),
        ]
    )
    repo = ModuleBRepository("http://server", "T001", session=session)  # type: ignore[arg-type]

    reports = repo.list_plagiarism("home_001")
    stats = repo.get_score_stats("home_001")

    assert reports[0]["plagiarism_rate"] == 92.5
    assert stats["summary"]["count"] == 1
    assert session.calls[0]["url"] == "http://server/v1/assignments/home_001/plagiarism"
    assert session.calls[1]["url"] == "http://server/v1/assignments/home_001/score-stats"
