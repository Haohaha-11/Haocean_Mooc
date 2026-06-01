from __future__ import annotations

from pathlib import Path
import tempfile
import time
import unittest

from fastapi import HTTPException

from app import main
from app.main import (
    AuthLoginPayload,
    AuthLoginRequest,
    AuthVerificationRequest,
    AuthVerificationRequestPayload,
    get_auth_context,
    init_db,
    login_with_code,
    request_auth_code,
)


class AuthFlowTests(unittest.TestCase):
    def test_request_code_and_login_returns_token(self) -> None:
        original_db_path = main.DB_PATH
        original_auth_required = main.AUTH_REQUIRED
        original_dev_log = main.DEV_VERIFICATION_LOG
        original_send_email = main.send_email
        with tempfile.TemporaryDirectory() as tmp:
            main.DB_PATH = Path(tmp) / "engine.db"
            main.AUTH_REQUIRED = True
            main.DEV_VERIFICATION_LOG = True
            main.send_email = lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("disabled in test"))
            try:
                init_db()
                request = AuthVerificationRequest(
                    action="REQUEST_LOGIN_CODE",
                    timestamp=int(time.time()),
                    payload=AuthVerificationRequestPayload(
                        email="student@example.com",
                        role="student",
                        display_id="2024001",
                    ),
                )
                code_response = request_auth_code(request)
                code = code_response["payload"]["dev_code"]

                login_response = login_with_code(
                    AuthLoginRequest(
                        action="LOGIN_WITH_CODE",
                        timestamp=int(time.time()),
                        payload=AuthLoginPayload(
                            email="student@example.com",
                            role="student",
                            display_id="2024001",
                            code=code,
                        ),
                    )
                )

                token = login_response["payload"]["token"]
                auth = get_auth_context(f"Bearer {token}")
                self.assertEqual(auth.role, "student")
                self.assertEqual(auth.display_id, "2024001")
            finally:
                main.DB_PATH = original_db_path
                main.AUTH_REQUIRED = original_auth_required
                main.DEV_VERIFICATION_LOG = original_dev_log
                main.send_email = original_send_email

    def test_invalid_code_is_rejected(self) -> None:
        original_db_path = main.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            main.DB_PATH = Path(tmp) / "engine.db"
            try:
                init_db()
                with self.assertRaises(HTTPException) as caught:
                    login_with_code(
                        AuthLoginRequest(
                            action="LOGIN_WITH_CODE",
                            timestamp=int(time.time()),
                            payload=AuthLoginPayload(
                                email="teacher@example.com",
                                role="teacher",
                                display_id="T001",
                                code="000000",
                            ),
                        )
                    )
                self.assertEqual(caught.exception.status_code, 400)
            finally:
                main.DB_PATH = original_db_path


if __name__ == "__main__":
    unittest.main()
