from __future__ import annotations

from pathlib import Path

from controller.config import (
    list_teacher_profiles,
    load_settings,
    set_active_profile,
    write_teacher_profile,
    write_user_config,
)


CONFIG_ENV_NAMES = [
    "CONTROLLER_DB",
    "CONTROLLER_SOURCE",
    "CONTROLLER_API_BASE_URL",
    "CONTROLLER_TEACHER_ID",
    "CONTROLLER_NAME",
    "CONTROLLER_EMAIL",
    "CONTROLLER_CURRENT_CLASS_ID",
    "CONTROLLER_AUTH_TOKEN",
    "CONTROLLER_AUTH_TOKEN_FILE",
    "CONTROLLER_REQUEST_TIMEOUT_SECONDS",
    "FEEDBACK_DIR",
    "LOG_FILE",
    "MODULE_C_DB_PATH",
    "MODULE_C_FEEDBACK_DIR",
    "MODULE_C_LOG_PATH",
    "MODULE_C_SOURCE",
]


def clear_config_env(monkeypatch) -> None:
    for name in CONFIG_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_load_settings_reads_controller_env_names(
    monkeypatch,
    tmp_path: Path,
) -> None:
    clear_config_env(monkeypatch)
    monkeypatch.setenv("CONTROLLER_DB", "data/custom.db")
    monkeypatch.setenv("FEEDBACK_DIR", "feedback")
    monkeypatch.setenv("LOG_FILE", "logs/custom.log")
    monkeypatch.setenv("CONTROLLER_SOURCE", "sqlite")

    settings = load_settings(tmp_path, config_dir=tmp_path / ".haocean-teacher")

    assert settings.db_path == tmp_path / "data" / "custom.db"
    assert settings.feedback_dir == tmp_path / "feedback"
    assert settings.log_path == tmp_path / "logs" / "custom.log"
    assert settings.source == "sqlite"


def test_load_settings_keeps_legacy_env_fallback(
    monkeypatch,
    tmp_path: Path,
) -> None:
    clear_config_env(monkeypatch)
    monkeypatch.setenv("MODULE_C_DB_PATH", "data/legacy.db")
    monkeypatch.setenv("MODULE_C_FEEDBACK_DIR", "legacy_feedback")
    monkeypatch.setenv("MODULE_C_LOG_PATH", "logs/legacy.log")
    monkeypatch.setenv("MODULE_C_SOURCE", "sqlite")

    settings = load_settings(tmp_path, config_dir=tmp_path / ".haocean-teacher")

    assert settings.db_path == tmp_path / "data" / "legacy.db"
    assert settings.feedback_dir == tmp_path / "legacy_feedback"
    assert settings.log_path == tmp_path / "logs" / "legacy.log"
    assert settings.source == "sqlite"


def test_load_settings_reads_http_controller_env(monkeypatch, tmp_path: Path) -> None:
    clear_config_env(monkeypatch)
    monkeypatch.setenv("CONTROLLER_SOURCE", "http")
    monkeypatch.setenv("CONTROLLER_API_BASE_URL", "http://127.0.0.1:9000")
    monkeypatch.setenv("CONTROLLER_TEACHER_ID", "T002")
    monkeypatch.setenv("CONTROLLER_NAME", "Teacher Two")
    monkeypatch.setenv("CONTROLLER_EMAIL", "teacher@example.com")
    monkeypatch.setenv("CONTROLLER_CURRENT_CLASS_ID", "cs101")
    monkeypatch.setenv("CONTROLLER_AUTH_TOKEN", "token-abc")
    monkeypatch.setenv("CONTROLLER_AUTH_TOKEN_FILE", "data/teacher_token")
    monkeypatch.setenv("CONTROLLER_REQUEST_TIMEOUT_SECONDS", "3.5")

    settings = load_settings(tmp_path, config_dir=tmp_path / ".haocean-teacher")

    assert settings.source == "http"
    assert settings.api_base_url == "http://127.0.0.1:9000"
    assert settings.teacher_id == "T002"
    assert settings.name == "Teacher Two"
    assert settings.email == "teacher@example.com"
    assert settings.current_class_id == "cs101"
    assert settings.auth_token == "token-abc"
    assert settings.auth_token_file == tmp_path / "data" / "teacher_token"
    assert settings.request_timeout_seconds == 3.5


def test_load_settings_reads_teacher_user_config(monkeypatch, tmp_path: Path) -> None:
    clear_config_env(monkeypatch)
    config_dir = tmp_path / ".haocean-teacher"
    config_dir.mkdir(parents=True)
    (config_dir / "config.json").write_text(
        """
        {
          "source": "http",
          "api_base_url": "https://teacher.example.com",
          "teacher_id": "T009",
          "name": "Teacher Nine",
          "email": "teacher9@example.com",
          "current_class_id": "cs909",
          "download_dir": "downloads-local"
        }
        """,
        encoding="utf-8",
    )

    settings = load_settings(tmp_path, config_dir=config_dir)

    assert settings.source == "http"
    assert settings.api_base_url == "https://teacher.example.com"
    assert settings.teacher_id == "T009"
    assert settings.name == "Teacher Nine"
    assert settings.email == "teacher9@example.com"
    assert settings.current_class_id == "cs909"
    assert settings.auth_token_file == config_dir / "auth_token"
    assert settings.download_dir == config_dir / "downloads-local"


def test_teacher_profiles_can_store_multiple_identities(monkeypatch, tmp_path: Path) -> None:
    clear_config_env(monkeypatch)
    config_dir = tmp_path / ".haocean-teacher"

    write_teacher_profile(
        config_dir,
        "T001",
        {
            "source": "http",
            "api_base_url": "http://127.0.0.1:8000",
            "teacher_id": "T001",
            "name": "Teacher One",
            "email": "one@example.com",
        },
    )
    write_teacher_profile(
        config_dir,
        "T002",
        {
            "source": "http",
            "api_base_url": "http://127.0.0.1:9000",
            "teacher_id": "T002",
            "name": "Teacher Two",
            "email": "two@example.com",
        },
    )

    active = load_settings(tmp_path, config_dir=config_dir)
    first = load_settings(tmp_path, config_dir=config_dir, profile_name="T001")
    profiles = list_teacher_profiles(config_dir)

    assert active.profile_name == "T002"
    assert active.teacher_id == "T002"
    assert active.api_base_url == "http://127.0.0.1:9000"
    assert active.auth_token_file == config_dir / "auth_tokens" / "T002"
    assert first.profile_name == "T001"
    assert first.email == "one@example.com"
    assert [profile["profile_name"] for profile in profiles] == ["T001", "T002"]


def test_write_user_config_updates_active_teacher_profile(monkeypatch, tmp_path: Path) -> None:
    clear_config_env(monkeypatch)
    config_dir = tmp_path / ".haocean-teacher"
    write_teacher_profile(
        config_dir,
        "T001",
        {"teacher_id": "T001", "name": "Teacher One", "email": "one@example.com"},
    )
    write_teacher_profile(
        config_dir,
        "T002",
        {"teacher_id": "T002", "name": "Teacher Two", "email": "two@example.com"},
    )

    set_active_profile(config_dir, "T001")
    write_user_config(config_dir, {"current_class_id": "cs101"})

    first = load_settings(tmp_path, config_dir=config_dir, profile_name="T001")
    second = load_settings(tmp_path, config_dir=config_dir, profile_name="T002")

    assert first.current_class_id == "cs101"
    assert second.current_class_id == ""
