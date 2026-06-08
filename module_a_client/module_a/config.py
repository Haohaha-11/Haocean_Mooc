from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
import json
import os
from pathlib import Path
import re

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


def _clean_updates(updates: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in updates.items() if value not in (None, "")}


def _safe_profile_file_name(profile_name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", profile_name.strip())
    return safe or "default"


def _profile_name_from_config(config: dict[str, object]) -> str:
    return (
        _config_str(config, "profile_name")
        or _config_str(config, "student_id")
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
    if not any(_config_str(flat, key) for key in ("student_id", "name", "email", "server_url")):
        return {}
    profile_name = _profile_name_from_config(flat)
    return {profile_name: flat}


def _copy_legacy_token_to_profile(config_dir: Path, profile_name: str) -> None:
    if not profile_name:
        return
    legacy_token = config_dir / "auth_token"
    profile_token = config_dir / "auth_tokens" / _safe_profile_file_name(profile_name)
    if not legacy_token.exists() or profile_token.exists():
        return
    try:
        token = legacy_token.read_text(encoding="utf-8").strip()
    except OSError:
        return
    if not token:
        return
    try:
        profile_token.parent.mkdir(parents=True, exist_ok=True)
        profile_token.write_text(token + "\n", encoding="utf-8")
    except OSError:
        return


def list_student_profiles(config_dir: Path) -> list[dict[str, str]]:
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
                "student_id": _config_str(merged, "student_id"),
                "name": _config_str(merged, "name"),
                "email": _config_str(merged, "email"),
                "server_url": _config_str(merged, "server_url") or DEFAULT_SERVER_URL,
                "class_code": _config_str(merged, "class_code"),
                "active": "true" if profile_name == active_profile else "false",
            }
        )
    return result


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


def write_student_profile(
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
    migrated_profiles = _migrate_flat_config_to_profiles(current)
    profiles = dict(migrated_profiles)
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
    if not had_profiles:
        for migrated_name in migrated_profiles:
            _copy_legacy_token_to_profile(config_dir, migrated_name)
    return config_path


def set_active_profile(config_dir: Path, profile_name: str) -> Path:
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.json"
    current = _read_user_config(config_dir)
    had_profiles = bool(_profile_dict(current))
    profiles = _migrate_flat_config_to_profiles(current)
    if profile_name not in profiles:
        raise ValueError(f"student profile does not exist: {profile_name}")
    current = {
        **(_base_config(current) if had_profiles else {}),
        "active_profile": profile_name,
        "profiles": profiles,
    }
    config_path.write_text(
        json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not had_profiles:
        _copy_legacy_token_to_profile(config_dir, profile_name)
    return config_path


@dataclass(frozen=True)
class Settings:
    project_root: Path = PROJECT_ROOT
    config_dir: Path = field(default_factory=default_config_dir)
    profile_name: str = ""
    server_url: str = DEFAULT_SERVER_URL
    student_id: str = ""
    name: str = ""
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
        name=_string_setting(
            user_config,
            "name",
            "MODULE_A_NAME",
            "",
            "STUDENT_NAME",
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
            default_auth_token_file,
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
