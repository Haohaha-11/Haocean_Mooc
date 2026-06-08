from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
import json
from pathlib import Path
import re

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


def _clean_updates(updates: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in updates.items() if value not in (None, "")}


def _safe_profile_file_name(profile_name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", profile_name.strip())
    return safe or "default"


def _profile_name_from_config(config: dict[str, object]) -> str:
    return (
        _config_str(config, "profile_name")
        or _config_str(config, "teacher_id")
        or _config_str(config, "email")
        or "default"
    )


def _profile_dict(config: dict[str, object]) -> dict[str, dict[str, object]]:
    raw_profiles = config.get("profiles")
    if not isinstance(raw_profiles, dict):
        return {}
    profiles: dict[str, dict[str, object]] = {}
    for key, value in raw_profiles.items():
        if isinstance(value, dict):
            profile_name = str(key).strip()
            if profile_name:
                profiles[profile_name] = dict(value)
    return profiles


def _base_config(config: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in config.items()
        if key not in {"active_profile", "profiles"}
    }


def _select_profile_config(
    config: dict[str, object],
    profile_name: str = "",
) -> tuple[str, dict[str, object]]:
    profiles = _profile_dict(config)
    if not profiles:
        return "", dict(config)

    selected_name = profile_name.strip() or _config_str(config, "active_profile")
    if selected_name not in profiles:
        selected_name = next(iter(profiles))
    selected = {
        **_base_config(config),
        **profiles[selected_name],
        "profile_name": selected_name,
    }
    return selected_name, selected


def _migrate_flat_config_to_profiles(config: dict[str, object]) -> dict[str, dict[str, object]]:
    profiles = _profile_dict(config)
    if profiles:
        return profiles

    flat = _base_config(config)
    if not any(_config_str(flat, key) for key in ("teacher_id", "name", "email", "api_base_url")):
        return {}
    profile_name = _profile_name_from_config(flat)
    return {profile_name: flat}


def list_teacher_profiles(config_dir: Path) -> list[dict[str, str]]:
    config = _read_user_config(config_dir)
    profiles = _profile_dict(config)
    if not profiles:
        flat = _base_config(config)
        if not flat:
            return []
        profile_name = _profile_name_from_config(flat)
        profiles = {profile_name: flat}

    active_profile = _config_str(config, "active_profile")
    result: list[dict[str, str]] = []
    for profile_name, profile in profiles.items():
        merged = {**_base_config(config), **profile}
        result.append(
            {
                "profile_name": profile_name,
                "teacher_id": _config_str(merged, "teacher_id"),
                "name": _config_str(merged, "name"),
                "email": _config_str(merged, "email"),
                "api_base_url": _config_str(merged, "api_base_url") or DEFAULT_API_BASE_URL,
                "active": "true" if profile_name == active_profile else "false",
            }
        )
    return result


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
    profiles = _profile_dict(current)
    cleaned = _clean_updates(updates)
    if profiles:
        active_profile = _config_str(current, "active_profile") or next(iter(profiles))
        profile = dict(profiles.get(active_profile, {}))
        profile.update(cleaned)
        profiles[active_profile] = profile
        current["profiles"] = profiles
        current["active_profile"] = active_profile
    else:
        current.update(cleaned)
    config_path.write_text(
        json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return config_path


def write_teacher_profile(
    config_dir: Path,
    profile_name: str,
    updates: dict[str, object],
    *,
    make_active: bool = True,
) -> Path:
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.json"
    current = _read_user_config(config_dir)
    had_profiles = bool(_profile_dict(current))
    profiles = _migrate_flat_config_to_profiles(current)
    cleaned = _clean_updates(updates)
    selected_name = profile_name.strip() or _profile_name_from_config(cleaned)
    profile = dict(profiles.get(selected_name, {}))
    profile.update(cleaned)
    profiles[selected_name] = profile

    next_config = _base_config(current) if had_profiles else {}
    next_config["profiles"] = profiles
    if make_active:
        next_config["active_profile"] = selected_name
    elif "active_profile" not in next_config and profiles:
        next_config["active_profile"] = next(iter(profiles))

    config_path.write_text(
        json.dumps(next_config, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return config_path


def set_active_profile(config_dir: Path, profile_name: str) -> Path:
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.json"
    current = _read_user_config(config_dir)
    had_profiles = bool(_profile_dict(current))
    profiles = _migrate_flat_config_to_profiles(current)
    if profile_name not in profiles:
        raise ValueError(f"teacher profile does not exist: {profile_name}")
    current = {
        **(_base_config(current) if had_profiles else {}),
        "active_profile": profile_name,
        "profiles": profiles,
    }
    config_path.write_text(
        json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return config_path


@dataclass(frozen=True)
class Settings:
    project_root: Path = PROJECT_ROOT
    config_dir: Path = field(default_factory=default_config_dir)
    profile_name: str = ""
    db_path: Path = field(default_factory=lambda: default_config_dir() / "data" / "mock_submissions.db")
    feedback_dir: Path = field(default_factory=lambda: default_config_dir() / "feedback_outbox")
    log_path: Path = field(default_factory=lambda: default_config_dir() / "logs" / "haocean-teacher.log")
    download_dir: Path = field(default_factory=lambda: default_config_dir() / "downloads")
    source: str = "http"
    api_base_url: str = DEFAULT_API_BASE_URL
    teacher_id: str = "T001"
    name: str = ""
    email: str = ""
    current_class_id: str = ""
    auth_token: str = ""
    auth_token_file: Path = field(default_factory=lambda: default_config_dir() / "auth_token")
    request_timeout_seconds: float = 10.0


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value else default


def load_settings(
    project_root: Path = PROJECT_ROOT,
    config_dir: Path | None = None,
    profile_name: str = "",
) -> Settings:
    load_dotenv(project_root / ".env")
    resolved_config_dir = (config_dir or default_config_dir()).expanduser().resolve()
    user_config = _read_user_config(resolved_config_dir)
    selected_profile_name, user_config = _select_profile_config(user_config, profile_name)
    default_auth_token_file = (
        f"auth_tokens/{_safe_profile_file_name(selected_profile_name)}"
        if selected_profile_name
        else "auth_token"
    )
    return Settings(
        project_root=project_root.resolve(),
        config_dir=resolved_config_dir,
        profile_name=selected_profile_name,
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
        name=_string_setting(
            user_config,
            "name",
            "CONTROLLER_NAME",
            "",
            "MODULE_C_NAME",
        ),
        email=_string_setting(
            user_config,
            "email",
            "CONTROLLER_EMAIL",
            "",
            "LOGIN_EMAIL",
        ),
        current_class_id=_string_setting(
            user_config,
            "current_class_id",
            "CONTROLLER_CURRENT_CLASS_ID",
            "",
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
            default_auth_token_file,
            resolved_config_dir,
            project_root,
            "MODULE_C_AUTH_TOKEN_FILE",
        ),
        request_timeout_seconds=_float_env("CONTROLLER_REQUEST_TIMEOUT_SECONDS", 10.0),
    )
