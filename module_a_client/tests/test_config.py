from __future__ import annotations

import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from module_a.config import (
    list_student_profiles,
    load_settings,
    set_active_profile,
    write_student_profile,
    write_user_config,
)


class ConfigTests(unittest.TestCase):
    def test_load_settings_reads_module_a_env(self) -> None:
        project_root = Path("/tmp/module_a_config_test")
        env = {
            "MODULE_A_SERVER_URL": "http://127.0.0.1:9000",
            "MODULE_A_STUDENT_ID": "2024001",
            "MODULE_A_NAME": "Alice Student",
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
        self.assertEqual(settings.name, "Alice Student")
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
              "name": "Student Eight",
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
        self.assertEqual(settings.name, "Student Eight")
        self.assertEqual(settings.email, "student8@example.com")
        self.assertEqual(settings.class_code, "JOIN101")
        self.assertEqual(settings.auth_token_file, config_dir / "auth_token")
        self.assertEqual(settings.workspace_dir, config_dir / "my-workspace")

    def test_student_profiles_can_store_multiple_identities(self) -> None:
        with tempfile.TemporaryDirectory() as raw_dir:
            project_root = Path(raw_dir)
            config_dir = project_root / ".haocean"

            with patch.dict("os.environ", {}, clear=True):
                write_student_profile(
                    config_dir,
                    "2024001",
                    {
                        "server_url": "https://student.example.com",
                        "student_id": "2024001",
                        "name": "Student One",
                        "email": "student1@example.com",
                        "class_code": "JOIN101",
                    },
                )
                write_student_profile(
                    config_dir,
                    "2024002",
                    {
                        "server_url": "https://student.example.com",
                        "student_id": "2024002",
                        "name": "Student Two",
                        "email": "student2@example.com",
                        "class_code": "JOIN202",
                    },
                )

                active = load_settings(project_root, config_dir=config_dir)
                first = load_settings(project_root, config_dir=config_dir, profile_name="2024001")
                profiles = list_student_profiles(config_dir)

            self.assertEqual(active.profile_name, "2024002")
            self.assertEqual(active.student_id, "2024002")
            self.assertEqual(active.auth_token_file, config_dir / "auth_tokens" / "2024002")
            self.assertEqual(first.profile_name, "2024001")
            self.assertEqual(first.student_id, "2024001")
            self.assertEqual(first.auth_token_file, config_dir / "auth_tokens" / "2024001")
            self.assertEqual([profile["profile_name"] for profile in profiles], ["2024001", "2024002"])
            self.assertEqual([profile["active"] for profile in profiles], ["false", "true"])

    def test_write_user_config_updates_active_student_profile(self) -> None:
        with tempfile.TemporaryDirectory() as raw_dir:
            project_root = Path(raw_dir)
            config_dir = project_root / ".haocean"

            with patch.dict("os.environ", {}, clear=True):
                write_student_profile(
                    config_dir,
                    "2024001",
                    {
                        "student_id": "2024001",
                        "name": "Student One",
                        "email": "student1@example.com",
                        "class_code": "JOIN101",
                    },
                )
                write_student_profile(
                    config_dir,
                    "2024002",
                    {
                        "student_id": "2024002",
                        "name": "Student Two",
                        "email": "student2@example.com",
                        "class_code": "JOIN202",
                    },
                )
                set_active_profile(config_dir, "2024001")
                write_user_config(config_dir, {"class_code": "JOIN303"})

                first = load_settings(project_root, config_dir=config_dir, profile_name="2024001")
                second = load_settings(project_root, config_dir=config_dir, profile_name="2024002")

            self.assertEqual(first.class_code, "JOIN303")
            self.assertEqual(second.class_code, "JOIN202")

    def test_flat_student_config_migrates_when_writing_profile(self) -> None:
        with tempfile.TemporaryDirectory() as raw_dir:
            project_root = Path(raw_dir)
            config_dir = project_root / ".haocean"
            config_dir.mkdir(parents=True)
            (config_dir / "config.json").write_text(
                """
                {
                  "server_url": "https://student.example.com",
                  "student_id": "2024001",
                  "name": "Student One",
                  "email": "student1@example.com",
                  "class_code": "JOIN101"
                }
                """,
                encoding="utf-8",
            )
            (config_dir / "auth_token").write_text("legacy-token\n", encoding="utf-8")

            with patch.dict("os.environ", {}, clear=True):
                write_student_profile(
                    config_dir,
                    "2024002",
                    {
                        "student_id": "2024002",
                        "name": "Student Two",
                        "email": "student2@example.com",
                        "class_code": "JOIN202",
                    },
                )
                first = load_settings(project_root, config_dir=config_dir, profile_name="2024001")
                second = load_settings(project_root, config_dir=config_dir, profile_name="2024002")
                profiles = list_student_profiles(config_dir)

            self.assertEqual(first.student_id, "2024001")
            self.assertEqual(first.class_code, "JOIN101")
            self.assertEqual(second.student_id, "2024002")
            self.assertEqual(second.class_code, "JOIN202")
            self.assertEqual([profile["profile_name"] for profile in profiles], ["2024001", "2024002"])
            self.assertEqual(
                (config_dir / "auth_tokens" / "2024001").read_text(encoding="utf-8"),
                "legacy-token\n",
            )
            self.assertFalse((config_dir / "auth_tokens" / "2024002").exists())


if __name__ == "__main__":
    unittest.main()
