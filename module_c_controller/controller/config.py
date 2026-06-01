from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
import json
from pathlib import Path

from dotenv import load_dotenv
import os


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_API_BASE_URL = "https://teacher.haoceanlab.cn"


def default_config_dir() -> Path:
    return Path(os.getenv("HAOCEAN_TEACHER_HOME", "~/.haocean-teacher")).expanduser().resolve()


def _resolve_path(value: str | None, default: str, base_dir: Path) -> Path:
    raw_path = Path(value or default).expanduser()
    path = raw_path if raw_path.is_absolute() else base_dir / raw_path
    return path.resolve()


def _get_env(primary: str, legacy: str) -> str | None:
    return os.getenv(primary) or os.getenv(legacy)


def _read_user_config(config_dir: Path) -> dict[str, object]:
    config_path = config_dir / "config.json"
    if not config_path.exists():
        return {}
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid Haocean teacher config file: {config_path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Haocean teacher config must contain a JSON object: {config_path}")
    return data


def _config_str(config: dict[str, object], key: str) -> str:
    value = config.get(key)
    return str(value).strip() if value is not None else ""


def _string_setting(
    config: dict[str, object],
    config_key: str,
    env_name: str,
    default: str = "",
    legacy_env: str = "",
) -> str:
    env_value = _get_env(env_name, legacy_env) if legacy_env else os.getenv(env_name)
    if env_value is not None:
        return env_value
    return _config_str(config, config_key) or default


def _path_setting(
    config: dict[str, object],
    config_key: str,
    env_name: str,
    default: str,
    config_dir: Path,
    project_root: Path,
    legacy_env: str = "",
) -> Path:
    env_value = _get_env(env_name, legacy_env) if legacy_env else os.getenv(env_name)
    if env_value is not None:
        return _resolve_path(env_value, default, project_root)
    config_value = _config_str(config, config_key)
    return _resolve_path(config_value or default, default, config_dir)


def write_user_config(config_dir: Path, updates: dict[str, object]) -> Path:
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.json"
    current = _read_user_config(config_dir)
    current.update({key: value for key, value in updates.items() if value not in (None, "")})
    config_path.write_text(
        json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return config_path


@dataclass(frozen=True)
class Settings:
    project_root: Path = PROJECT_ROOT
    config_dir: Path = field(default_factory=default_config_dir)
    db_path: Path = field(default_factory=lambda: default_config_dir() / "data" / "mock_submissions.db")
    feedback_dir: Path = field(default_factory=lambda: default_config_dir() / "feedback_outbox")
    log_path: Path = field(default_factory=lambda: default_config_dir() / "logs" / "haocean-teacher.log")
    download_dir: Path = field(default_factory=lambda: default_config_dir() / "downloads")
    source: str = "http"
    api_base_url: str = DEFAULT_API_BASE_URL
    teacher_id: str = "T001"
    email: str = ""
    auth_token: str = ""
    auth_token_file: Path = field(default_factory=lambda: default_config_dir() / "auth_token")
    request_timeout_seconds: float = 10.0


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value else default


def load_settings(project_root: Path = PROJECT_ROOT, config_dir: Path | None = None) -> Settings:
    load_dotenv(project_root / ".env")
    resolved_config_dir = (config_dir or default_config_dir()).expanduser().resolve()
    user_config = _read_user_config(resolved_config_dir)
    return Settings(
        project_root=project_root.resolve(),
        config_dir=resolved_config_dir,
        db_path=_path_setting(
            user_config,
            "db_path",
            "CONTROLLER_DB",
            "data/mock_submissions.db",
            resolved_config_dir,
            project_root,
            "MODULE_C_DB_PATH",
        ),
        feedback_dir=_path_setting(
            user_config,
            "feedback_dir",
            "FEEDBACK_DIR",
            "feedback_outbox",
            resolved_config_dir,
            project_root,
            "MODULE_C_FEEDBACK_DIR",
        ),
        log_path=_path_setting(
            user_config,
            "log_path",
            "LOG_FILE",
            "logs/haocean-teacher.log",
            resolved_config_dir,
            project_root,
            "MODULE_C_LOG_PATH",
        ),
        download_dir=_path_setting(
            user_config,
            "download_dir",
            "CONTROLLER_DOWNLOAD_DIR",
            "downloads",
            resolved_config_dir,
            project_root,
            "MODULE_C_DOWNLOAD_DIR",
        ),
        source=_string_setting(
            user_config,
            "source",
            "CONTROLLER_SOURCE",
            "http",
            "MODULE_C_SOURCE",
        ).lower(),
        api_base_url=_string_setting(
            user_config,
            "api_base_url",
            "CONTROLLER_API_BASE_URL",
            DEFAULT_API_BASE_URL,
            "MODULE_C_API_BASE_URL",
        ),
        teacher_id=_string_setting(
            user_config,
            "teacher_id",
            "CONTROLLER_TEACHER_ID",
            "T001",
            "TEACHER_ID",
        ),
        email=_string_setting(
            user_config,
            "email",
            "CONTROLLER_EMAIL",
            "",
            "LOGIN_EMAIL",
        ),
        auth_token=_string_setting(
            user_config,
            "auth_token",
            "CONTROLLER_AUTH_TOKEN",
            "",
            "AUTH_TOKEN",
        ),
        auth_token_file=_path_setting(
            user_config,
            "auth_token_file",
            "CONTROLLER_AUTH_TOKEN_FILE",
            "auth_token",
            resolved_config_dir,
            project_root,
            "MODULE_C_AUTH_TOKEN_FILE",
        ),
        request_timeout_seconds=_float_env("CONTROLLER_REQUEST_TIMEOUT_SECONDS", 10.0),
    )
