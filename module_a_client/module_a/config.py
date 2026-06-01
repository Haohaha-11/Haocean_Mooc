from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(path: object, *_args: object, **_kwargs: object) -> bool:
        env_path = Path(path)
        if not env_path.exists():
            return False
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
        return True


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SERVER_URL = "https://student.haoceanlab.cn"


def default_config_dir() -> Path:
    return Path(os.getenv("HAOCEAN_HOME", "~/.haocean")).expanduser().resolve()


def _resolve_path(value: str | None, default: str, base_dir: Path) -> Path:
    raw_path = Path(value or default).expanduser()
    path = raw_path if raw_path.is_absolute() else base_dir / raw_path
    return path.resolve()


def _get_env(primary: str, legacy: str | None = None) -> str | None:
    return os.getenv(primary) or (os.getenv(legacy) if legacy else None)


def _read_user_config(config_dir: Path) -> dict[str, object]:
    config_path = config_dir / "config.json"
    if not config_path.exists():
        return {}
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid Haocean config file: {config_path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Haocean config file must contain a JSON object: {config_path}")
    return data


def _config_str(config: dict[str, object], key: str) -> str:
    value = config.get(key)
    return str(value).strip() if value is not None else ""


def _string_setting(
    config: dict[str, object],
    config_key: str,
    env_name: str,
    default: str = "",
    legacy_env: str | None = None,
) -> str:
    env_value = _get_env(env_name, legacy_env)
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
    legacy_env: str | None = None,
) -> Path:
    env_value = _get_env(env_name, legacy_env)
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
    server_url: str = DEFAULT_SERVER_URL
    student_id: str = ""
    email: str = ""
    auth_token: str = ""
    auth_token_file: Path = field(default_factory=lambda: default_config_dir() / "auth_token")
    assignment_filter: str = ""
    class_code: str = ""
    workspace_dir: Path = field(default_factory=lambda: default_config_dir() / "workspace")
    cache_dir: Path = field(default_factory=lambda: default_config_dir() / "cache" / "archives")
    feedback_dir: Path = field(default_factory=lambda: default_config_dir() / "feedback_inbox")
    log_path: Path = field(default_factory=lambda: default_config_dir() / "logs" / "haocean.log")
    debounce_seconds: float = 3.0
    poll_interval_seconds: float = 1.0
    request_timeout_seconds: float = 10.0
    retry_count: int = 3
    retry_backoff_seconds: float = 1.0


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value else default


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


def load_settings(project_root: Path = PROJECT_ROOT, config_dir: Path | None = None) -> Settings:
    load_dotenv(project_root / ".env")
    resolved_config_dir = (config_dir or default_config_dir()).expanduser().resolve()
    user_config = _read_user_config(resolved_config_dir)
    return Settings(
        project_root=project_root.resolve(),
        config_dir=resolved_config_dir,
        server_url=_string_setting(
            user_config,
            "server_url",
            "MODULE_A_SERVER_URL",
            DEFAULT_SERVER_URL,
        ),
        student_id=_string_setting(
            user_config,
            "student_id",
            "MODULE_A_STUDENT_ID",
            "",
            "STUDENT_ID",
        ),
        email=_string_setting(
            user_config,
            "email",
            "MODULE_A_EMAIL",
            "",
            "LOGIN_EMAIL",
        ),
        auth_token=_string_setting(
            user_config,
            "auth_token",
            "MODULE_A_AUTH_TOKEN",
            "",
            "AUTH_TOKEN",
        ),
        auth_token_file=_path_setting(
            user_config,
            "auth_token_file",
            "MODULE_A_AUTH_TOKEN_FILE",
            "auth_token",
            resolved_config_dir,
            project_root,
        ),
        assignment_filter=_string_setting(
            user_config,
            "assignment_id",
            "MODULE_A_ASSIGNMENT_ID",
            "",
            "ASSIGNMENT_ID",
        ),
        class_code=_string_setting(
            user_config,
            "class_code",
            "MODULE_A_CLASS_CODE",
        ),
        workspace_dir=_path_setting(
            user_config,
            "workspace_dir",
            "MODULE_A_WORKSPACE_DIR",
            "workspace",
            resolved_config_dir,
            project_root,
        ),
        cache_dir=_path_setting(
            user_config,
            "cache_dir",
            "MODULE_A_CACHE_DIR",
            "cache/archives",
            resolved_config_dir,
            project_root,
        ),
        feedback_dir=_path_setting(
            user_config,
            "feedback_dir",
            "MODULE_A_FEEDBACK_DIR",
            "feedback_inbox",
            resolved_config_dir,
            project_root,
        ),
        log_path=_path_setting(
            user_config,
            "log_path",
            "MODULE_A_LOG_FILE",
            "logs/haocean.log",
            resolved_config_dir,
            project_root,
        ),
        debounce_seconds=_float_env("MODULE_A_DEBOUNCE_SECONDS", 3.0),
        poll_interval_seconds=_float_env("MODULE_A_POLL_INTERVAL_SECONDS", 1.0),
        request_timeout_seconds=_float_env("MODULE_A_REQUEST_TIMEOUT_SECONDS", 10.0),
        retry_count=_int_env("MODULE_A_RETRY_COUNT", 3),
        retry_backoff_seconds=_float_env("MODULE_A_RETRY_BACKOFF_SECONDS", 1.0),
    )
