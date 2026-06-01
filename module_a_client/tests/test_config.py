from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from module_a.config import load_settings


class ConfigTests(unittest.TestCase):
    def test_load_settings_reads_module_a_env(self) -> None:
        project_root = Path("/tmp/module_a_config_test")
        env = {
            "MODULE_A_SERVER_URL": "http://127.0.0.1:9000",
            "MODULE_A_STUDENT_ID": "2024001",
            "MODULE_A_EMAIL": "student@example.com",
            "MODULE_A_AUTH_TOKEN": "token-123",
            "MODULE_A_AUTH_TOKEN_FILE": "data/custom_token",
            "MODULE_A_ASSIGNMENT_ID": "home_001",
            "MODULE_A_WORKSPACE_DIR": "workspace_custom",
            "MODULE_A_CACHE_DIR": "cache_custom",
            "MODULE_A_FEEDBACK_DIR": "feedback_custom",
            "MODULE_A_LOG_FILE": "logs/custom.log",
            "MODULE_A_DEBOUNCE_SECONDS": "1.5",
            "MODULE_A_POLL_INTERVAL_SECONDS": "0.5",
            "MODULE_A_REQUEST_TIMEOUT_SECONDS": "7",
            "MODULE_A_RETRY_COUNT": "5",
            "MODULE_A_RETRY_BACKOFF_SECONDS": "0.2",
        }

        with patch.dict("os.environ", env, clear=True):
            settings = load_settings(project_root, config_dir=project_root / ".haocean")

        self.assertEqual(settings.server_url, "http://127.0.0.1:9000")
        self.assertEqual(settings.student_id, "2024001")
        self.assertEqual(settings.email, "student@example.com")
        self.assertEqual(settings.auth_token, "token-123")
        self.assertEqual(settings.auth_token_file, project_root / "data" / "custom_token")
        self.assertEqual(settings.assignment_filter, "home_001")
        self.assertEqual(settings.workspace_dir, project_root / "workspace_custom")
        self.assertEqual(settings.cache_dir, project_root / "cache_custom")
        self.assertEqual(settings.feedback_dir, project_root / "feedback_custom")
        self.assertEqual(settings.log_path, project_root / "logs" / "custom.log")
        self.assertEqual(settings.debounce_seconds, 1.5)
        self.assertEqual(settings.poll_interval_seconds, 0.5)
        self.assertEqual(settings.request_timeout_seconds, 7)
        self.assertEqual(settings.retry_count, 5)
        self.assertEqual(settings.retry_backoff_seconds, 0.2)

    def test_student_id_keeps_legacy_fallback(self) -> None:
        with patch.dict("os.environ", {"STUDENT_ID": "legacy"}, clear=True):
            project_root = Path("/tmp/module_a_config_test")
            settings = load_settings(project_root, config_dir=project_root / ".haocean")

        self.assertEqual(settings.student_id, "legacy")

    def test_load_settings_reads_user_config_from_haocean_home(self) -> None:
        project_root = Path("/tmp/module_a_config_test")
        config_dir = project_root / ".haocean"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.json").write_text(
            """
            {
              "server_url": "https://student.example.com",
              "student_id": "2024008",
              "email": "student8@example.com",
              "class_code": "JOIN101",
              "workspace_dir": "my-workspace"
            }
            """,
            encoding="utf-8",
        )

        with patch.dict("os.environ", {}, clear=True):
            settings = load_settings(project_root, config_dir=config_dir)

        self.assertEqual(settings.server_url, "https://student.example.com")
        self.assertEqual(settings.student_id, "2024008")
        self.assertEqual(settings.email, "student8@example.com")
        self.assertEqual(settings.class_code, "JOIN101")
        self.assertEqual(settings.auth_token_file, config_dir / "auth_token")
        self.assertEqual(settings.workspace_dir, config_dir / "my-workspace")


if __name__ == "__main__":
    unittest.main()
