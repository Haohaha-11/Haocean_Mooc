from __future__ import annotations

from pathlib import Path

from controller.config import load_settings


def test_load_settings_reads_controller_env_names(
    monkeypatch,
    tmp_path: Path,
) -> None:
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
    monkeypatch.delenv("CONTROLLER_DB", raising=False)
    monkeypatch.delenv("FEEDBACK_DIR", raising=False)
    monkeypatch.delenv("LOG_FILE", raising=False)
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
    monkeypatch.setenv("CONTROLLER_SOURCE", "http")
    monkeypatch.setenv("CONTROLLER_API_BASE_URL", "http://127.0.0.1:9000")
    monkeypatch.setenv("CONTROLLER_TEACHER_ID", "T002")
    monkeypatch.setenv("CONTROLLER_EMAIL", "teacher@example.com")
    monkeypatch.setenv("CONTROLLER_AUTH_TOKEN", "token-abc")
    monkeypatch.setenv("CONTROLLER_AUTH_TOKEN_FILE", "data/teacher_token")
    monkeypatch.setenv("CONTROLLER_REQUEST_TIMEOUT_SECONDS", "3.5")

    settings = load_settings(tmp_path, config_dir=tmp_path / ".haocean-teacher")

    assert settings.source == "http"
    assert settings.api_base_url == "http://127.0.0.1:9000"
    assert settings.teacher_id == "T002"
    assert settings.email == "teacher@example.com"
    assert settings.auth_token == "token-abc"
    assert settings.auth_token_file == tmp_path / "data" / "teacher_token"
    assert settings.request_timeout_seconds == 3.5


def test_load_settings_reads_teacher_user_config(monkeypatch, tmp_path: Path) -> None:
    config_dir = tmp_path / ".haocean-teacher"
    config_dir.mkdir(parents=True)
    (config_dir / "config.json").write_text(
        """
        {
          "source": "http",
          "api_base_url": "https://teacher.example.com",
          "teacher_id": "T009",
          "email": "teacher9@example.com",
          "download_dir": "downloads-local"
        }
        """,
        encoding="utf-8",
    )

    monkeypatch.delenv("CONTROLLER_SOURCE", raising=False)
    monkeypatch.delenv("CONTROLLER_API_BASE_URL", raising=False)
    settings = load_settings(tmp_path, config_dir=config_dir)

    assert settings.source == "http"
    assert settings.api_base_url == "https://teacher.example.com"
    assert settings.teacher_id == "T009"
    assert settings.email == "teacher9@example.com"
    assert settings.auth_token_file == config_dir / "auth_token"
    assert settings.download_dir == config_dir / "downloads-local"
