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
                                "assignment_title": "Homework 1",
                                "class_id": "cs101",
                                "class_name": "CS101 Spring",
                                "download_url": "/v1/submissions/7/download",
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
    assert submissions[0].assignment_id == "home_001"
    assert submissions[0].assignment_title == "Homework 1"
    assert submissions[0].class_name == "CS101 Spring"
    assert submissions[0].download_url == "/v1/submissions/7/download"
    assert submissions[0].status == "pending"
    assert "Assignment ID: home_001" in submissions[0].content
    assert "MD5: abc" in submissions[0].content
    assert session.calls[0]["url"] == "http://server/v1/submissions"
    assert session.calls[0]["kwargs"]["params"] == {"status": "pending"}


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
                                "assignment_title": "Homework 1",
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
                        "comment": "Good work.",
                        "graded_at": "2026-05-27 10:20:00",
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
    assert updated.comment == "Good work."
    assert updated.reviewed_at == "2026-05-27 10:20:00"
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


def test_teacher_deepseek_key_is_sent_as_header(monkeypatch) -> None:
    monkeypatch.setenv("MODULE_C_DEEPSEEK_API_KEY", "teacher-key")
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
    repo = ModuleBRepository("http://server", "T001", session=session)  # type: ignore[arg-type]

    repo.list_submissions("pending")

    headers = session.calls[0]["kwargs"]["headers"]  # type: ignore[index]
    assert headers["X-DeepSeek-API-Key"] == "teacher-key"


def test_approved_submissions_are_loaded_from_module_b() -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "code": 200,
                    "message": "submissions returned",
                    "payload": {
                        "submissions": [
                            {
                                "submission_id": 8,
                                "student_id": "2024002",
                                "assignment_id": "home_002",
                                "assignment_title": "Homework 2",
                                "file_name": "home_002.tar.gz",
                                "download_url": "/v1/submissions/8/download",
                                "md5": "def",
                                "submit_time": "2026-05-28 10:10:00",
                                "status": "graded",
                                "score": 88,
                                "comment": "Solid.",
                                "feedback_path": "/server/feedback_8.md",
                            }
                        ]
                    },
                },
            )
        ]
    )
    repo = ModuleBRepository("http://server", "T001", session=session)  # type: ignore[arg-type]

    submissions = repo.list_submissions("approved")

    assert submissions[0].status == "approved"
    assert submissions[0].score == 88
    assert submissions[0].comment == "Solid."
    assert session.calls[0]["url"] == "http://server/v1/submissions"
    assert session.calls[0]["kwargs"]["params"] == {"status": "graded"}


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

def test_list_assignments_uses_open_assignments_endpoint() -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "code": 200,
                    "message": "open assignments returned",
                    "payload": {
                        "assignments": [
                            {
                                "assignment_id": "home_001",
                                "title": "Homework 1",
                                "class_name": "CS101 Spring",
                                "assignment_weight": 1.0,
                                "deadline": "2026-06-15 23:59:59",
                                "created_at": "2026-06-01 10:00:00",
                                "status": "open",
                            }
                        ]
                    },
                },
            )
        ]
    )
    repo = ModuleBRepository("http://server", "T001", session=session)  # type: ignore[arg-type]

    assignments = repo.list_assignments()

    assert assignments[0]["assignment_id"] == "home_001"
    assert session.calls[0]["method"] == "GET"
    assert session.calls[0]["url"] == "http://server/v1/assignments/open"


def test_create_assignment_sends_assignment_weight() -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "code": 200,
                    "message": "assignment created",
                    "payload": {
                        "assignment_id": "home_001",
                        "title": "Homework 1",
                        "class_id": "cs101",
                        "assignment_weight": 2.5,
                        "peer_review_enabled": True,
                        "peer_review_stage": "submission",
                        "status": "open",
                    },
                },
            )
        ]
    )
    repo = ModuleBRepository("http://server", "T001", session=session)  # type: ignore[arg-type]

    created = repo.create_assignment(
        "home_001",
        "Homework 1",
        class_id="cs101",
        assignment_weight=2.5,
        peer_review_enabled=True,
        teacher_weight=0.8,
        peer_weight=0.2,
    )

    assert created["assignment_weight"] == 2.5
    assert created["peer_review_enabled"] is True
    call = session.calls[0]
    assert call["url"] == "http://server/v1/assignments"
    payload = call["kwargs"]["json"]["payload"]  # type: ignore[index]
    assert payload["assignment_weight"] == 2.5
    assert payload["peer_review_enabled"] is True
    assert payload["teacher_weight"] == 0.8
    assert payload["peer_weight"] == 0.2


def test_peer_review_stage_and_auto_assign_call_expected_endpoints() -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "code": 200,
                    "message": "peer review stage updated",
                    "payload": {"assignment_id": "home_001", "stage": "peer_review"},
                },
            ),
            FakeResponse(
                200,
                {
                    "code": 200,
                    "message": "peer review tasks assigned",
                    "payload": {
                        "assignment_id": "home_001",
                        "student_count": 2,
                        "reviews_per_student": 1,
                        "tasks": [
                            {
                                "assignment_id": "home_001",
                                "reviewer_student_id": "2024001",
                                "submission_id": 8,
                            }
                        ],
                    },
                },
            ),
        ]
    )
    repo = ModuleBRepository(
        "http://server",
        "T001",
        auth_token="teacher-token",
        session=session,  # type: ignore[arg-type]
    )

    stage = repo.set_peer_review_stage("home_001", "peer_review")
    assigned = repo.auto_assign_peer_review_tasks("home_001")

    assert stage["stage"] == "peer_review"
    assert assigned["student_count"] == 2
    stage_call = session.calls[0]
    assert stage_call["method"] == "POST"
    assert stage_call["url"] == "http://server/v1/assignments/home_001/peer-review/stage"
    assert stage_call["kwargs"]["headers"]["Authorization"] == "Bearer teacher-token"  # type: ignore[index]
    assert stage_call["kwargs"]["json"]["action"] == "SET_PEER_REVIEW_STAGE"  # type: ignore[index]
    assert stage_call["kwargs"]["json"]["payload"] == {"stage": "peer_review"}  # type: ignore[index]

    assign_call = session.calls[1]
    assert assign_call["method"] == "POST"
    assert assign_call["url"] == "http://server/v1/assignments/home_001/peer-review/tasks/auto"
    assert assign_call["kwargs"]["headers"]["Authorization"] == "Bearer teacher-token"  # type: ignore[index]


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
            FakeResponse(
                200,
                {
                    "code": 200,
                    "message": "plagiarism report returned",
                    "payload": {
                        "submission_id": 7,
                        "student_id": "2024001",
                        "plagiarism_rate": 92.5,
                    },
                },
            ),
            FakeResponse(
                200,
                {
                    "code": 200,
                    "message": "ai grading report returned",
                    "payload": {
                        "submission_id": 7,
                        "source": "local",
                        "model": "local-summary",
                        "report": {"report_text": "Local report"},
                    },
                },
            ),
        ]
    )
    repo = ModuleBRepository("http://server", "T001", session=session)  # type: ignore[arg-type]

    reports = repo.list_plagiarism("home_001")
    stats = repo.get_score_stats("home_001")
    plagiarism = repo.get_submission_plagiarism(7)
    ai_report = repo.get_ai_grade_report(7)

    assert reports[0]["plagiarism_rate"] == 92.5
    assert stats["summary"]["count"] == 1
    assert plagiarism["submission_id"] == 7
    assert ai_report["report"]["report_text"] == "Local report"
    assert session.calls[0]["url"] == "http://server/v1/assignments/home_001/plagiarism"
    assert session.calls[1]["url"] == "http://server/v1/assignments/home_001/score-stats"
    assert session.calls[2]["url"] == "http://server/v1/submissions/7/plagiarism"
    assert session.calls[3]["url"] == "http://server/v1/submissions/7/ai-grade-report"


def test_check_plagiarism_sends_hybrid_payload() -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "code": 200,
                    "message": "plagiarism check finished",
                    "payload": {
                        "assignment_id": "home_001",
                        "method": "hybrid",
                        "suspected_pairs": [],
                    },
                },
            )
        ]
    )
    repo = ModuleBRepository("http://server", "T001", session=session)  # type: ignore[arg-type]

    payload = repo.check_plagiarism(
        "home_001",
        method="hybrid",
        threshold=0.8,
        ai_prefilter=0.45,
        ai_limit=6,
    )

    assert payload["method"] == "hybrid"
    call = session.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == "http://server/v1/plagiarism/check"
    assert call["kwargs"]["json"]["action"] == "CHECK_PLAGIARISM"  # type: ignore[index]
    request_payload = call["kwargs"]["json"]["payload"]  # type: ignore[index]
    assert request_payload == {
        "assignment_id": "home_001",
        "method": "hybrid",
        "threshold": 0.8,
        "ai_prefilter": 0.45,
        "ai_limit": 6,
    }


def test_list_assignment_submissions_filters_by_assignment() -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "code": 200,
                    "message": "submissions returned",
                    "payload": {
                        "summary": {"total": 2, "pending": 1, "graded": 1, "rejected": 0},
                        "submissions": [],
                    },
                },
            ),
            FakeResponse(
                200,
                {
                    "code": 200,
                    "message": "submissions returned",
                    "payload": {
                        "summary": {"total": 1, "pending": 1, "graded": 0, "rejected": 0},
                        "submissions": [],
                    },
                },
            )
        ]
    )
    repo = ModuleBRepository("http://server", "T001", session=session)  # type: ignore[arg-type]

    payload = repo.list_assignment_submissions("home_001")
    repo.list_submissions("pending", assignment_id="home_001")

    assert payload["summary"]["total"] == 2
    assert session.calls[0]["url"] == "http://server/v1/submissions"
    assert session.calls[0]["kwargs"]["params"] == {"status": "all", "assignment_id": "home_001"}
    assert session.calls[1]["kwargs"]["params"] == {"status": "pending", "assignment_id": "home_001"}


def test_upload_assignment_materials_posts_multipart_file(tmp_path) -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "code": 200,
                    "message": "assignment materials uploaded",
                    "payload": {
                        "assignment_id": "home_001",
                        "file_name": "spec.pdf",
                        "file_size": 7,
                    },
                },
            )
        ]
    )
    repo = ModuleBRepository("http://server", "T001", session=session)  # type: ignore[arg-type]
    source = tmp_path / "spec.pdf"
    source.write_bytes(b"payload")

    payload = repo.upload_assignment_materials("home_001", source)

    assert payload["file_name"] == "spec.pdf"
    call = session.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == "http://server/v1/assignments/home_001/materials"
    files = call["kwargs"]["files"]  # type: ignore[index]
    assert files["file"][0] == "spec.pdf"
