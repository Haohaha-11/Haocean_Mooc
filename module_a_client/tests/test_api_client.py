from __future__ import annotations

import json
import tempfile
from pathlib import Path
import unittest

from module_a.api_client import ModuleAApiError, ModuleBClient


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


class ApiClientTests(unittest.TestCase):
    def test_list_open_assignments_maps_payload(self) -> None:
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
                                    "description": "Finish it",
                                    "deadline": "2026-06-01 23:59:59",
                                    "created_by": "T001",
                                    "created_at": "2026-05-27 10:00:00",
                                    "status": "open",
                                }
                            ]
                        },
                    },
                )
            ]
        )
        client = ModuleBClient("http://server", session=session)  # type: ignore[arg-type]

        assignments = client.list_open_assignments()

        self.assertEqual(assignments[0].assignment_id, "home_001")
        self.assertEqual(session.calls[0]["url"], "http://server/v1/assignments/open")

    def test_submit_assignment_sends_metadata_and_file(self) -> None:
        session = FakeSession(
            [
                FakeResponse(
                    200,
                    {
                        "code": 200,
                        "message": "submission accepted",
                        "payload": {
                            "submission_id": 1,
                            "student_id": "2024001",
                            "assignment_id": "home_001",
                            "file_name": "2024001_home_001.tar.gz",
                            "md5": "abc",
                            "status": "pending",
                            "archive_path": "/server/archive",
                        },
                    },
                )
            ]
        )
        client = ModuleBClient("http://server/", session=session)  # type: ignore[arg-type]

        with tempfile.TemporaryDirectory() as tmp:
            archive_path = Path(tmp) / "archive.tar.gz"
            archive_path.write_bytes(b"payload")
            result = client.submit_assignment(
                student_id="2024001",
                assignment_id="home_001",
                archive_path=archive_path,
                md5="abc",
                file_name="2024001_home_001.tar.gz",
            )

        self.assertEqual(result.status, "pending")
        call = session.calls[0]
        self.assertEqual(call["method"], "POST")
        kwargs = call["kwargs"]
        data = kwargs["data"]  # type: ignore[index]
        metadata = json.loads(data["metadata"])  # type: ignore[index]
        self.assertEqual(metadata["action"], "SUBMIT")
        self.assertEqual(metadata["payload"]["md5"], "abc")

    def test_error_response_uses_fastapi_detail_message(self) -> None:
        response = FakeResponse(
            400,
            {
                "detail": {
                    "code": 400,
                    "message": "md5 mismatch, rejected",
                }
            },
        )
        client = ModuleBClient("http://server")

        with self.assertRaisesRegex(ModuleAApiError, "md5 mismatch"):
            client._payload(response)  # type: ignore[arg-type]

    def test_upload_retries_after_server_error(self) -> None:
        session = FakeSession(
            [
                FakeResponse(500, {"code": 500, "message": "temporary error", "payload": {}}),
                FakeResponse(
                    200,
                    {
                        "code": 200,
                        "message": "submission accepted",
                        "payload": {
                            "submission_id": 2,
                            "student_id": "2024001",
                            "assignment_id": "home_001",
                            "file_name": "2024001_home_001.tar.gz",
                            "md5": "abc",
                            "status": "pending",
                            "archive_path": "/server/archive",
                        },
                    },
                ),
            ]
        )
        client = ModuleBClient(
            "http://server",
            retry_count=2,
            retry_backoff_seconds=0,
            session=session,  # type: ignore[arg-type]
        )

        with tempfile.TemporaryDirectory() as tmp:
            archive_path = Path(tmp) / "archive.tar.gz"
            archive_path.write_bytes(b"payload")
            result = client.submit_assignment(
                student_id="2024001",
                assignment_id="home_001",
                archive_path=archive_path,
                md5="abc",
                file_name="2024001_home_001.tar.gz",
            )

        self.assertEqual(result.submission_id, 2)
        self.assertEqual(len(session.calls), 2)

    def test_auth_token_is_sent_as_bearer_header(self) -> None:
        session = FakeSession(
            [
                FakeResponse(
                    200,
                    {
                        "code": 200,
                        "message": "open assignments returned",
                        "payload": {"assignments": []},
                    },
                )
            ]
        )
        client = ModuleBClient("http://server", auth_token="token-123", session=session)  # type: ignore[arg-type]

        client.list_open_assignments()

        headers = session.calls[0]["kwargs"]["headers"]  # type: ignore[index]
        self.assertEqual(headers["Authorization"], "Bearer token-123")

    def test_join_class_sends_join_code(self) -> None:
        session = FakeSession(
            [
                FakeResponse(
                    200,
                    {
                        "code": 200,
                        "message": "class joined",
                        "payload": {
                            "class_id": "cs101",
                            "class_name": "CS101 Spring",
                            "course_id": "course_cs",
                            "course_title": "Computer Science",
                            "join_code": "JOIN101",
                            "teacher_id": "T001",
                            "created_at": "2026-06-01 10:00:00",
                            "status": "active",
                            "student_id": "2024001",
                        },
                    },
                )
            ]
        )
        client = ModuleBClient("http://server", auth_token="token-123", session=session)  # type: ignore[arg-type]

        joined = client.join_class("2024001", "JOIN101")

        self.assertEqual(joined.class_id, "cs101")
        call = session.calls[0]
        self.assertEqual(call["url"], "http://server/v1/classes/join")
        self.assertEqual(call["kwargs"]["json"]["action"], "JOIN_CLASS")  # type: ignore[index]
        payload = call["kwargs"]["json"]["payload"]  # type: ignore[index]
        self.assertEqual(payload["join_code"], "JOIN101")

    def test_list_my_classes_maps_payload(self) -> None:
        session = FakeSession(
            [
                FakeResponse(
                    200,
                    {
                        "code": 200,
                        "message": "student classes returned",
                        "payload": {
                            "classes": [
                                {
                                    "class_id": "cs101",
                                    "class_name": "CS101 Spring",
                                    "course_id": "course_cs",
                                    "course_title": "Computer Science",
                                    "join_code": "JOIN101",
                                    "teacher_id": "T001",
                                    "created_at": "2026-06-01 10:00:00",
                                    "status": "active",
                                    "joined_at": "2026-06-01 10:05:00",
                                }
                            ]
                        },
                    },
                )
            ]
        )
        client = ModuleBClient("http://server", session=session)  # type: ignore[arg-type]

        classes = client.list_my_classes()

        self.assertEqual(classes[0].join_code, "JOIN101")
        self.assertEqual(session.calls[0]["url"], "http://server/v1/classes/my")


if __name__ == "__main__":
    unittest.main()
