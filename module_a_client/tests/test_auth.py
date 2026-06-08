from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from module_a.auth import ensure_student_auth
from module_a.config import Settings, load_settings, write_student_profile
from module_a.main import (
    _handle_setup,
    _render_login_startup_if_needed,
    _select_student_profile_for_login,
)


class FakeClient:
    def __init__(self) -> None:
        self.auth_token = ""

    def health(self) -> dict[str, object]:
        return {"auth_required": True}


def _clear_module_a_env(monkeypatch) -> None:
    for key in (
        "MODULE_A_SERVER_URL",
        "MODULE_A_STUDENT_ID",
        "MODULE_A_NAME",
        "MODULE_A_EMAIL",
        "MODULE_A_AUTH_TOKEN",
        "MODULE_A_AUTH_TOKEN_FILE",
        "MODULE_A_ASSIGNMENT_ID",
        "MODULE_A_WORKSPACE_DIR",
        "MODULE_A_CACHE_DIR",
        "MODULE_A_FEEDBACK_DIR",
        "MODULE_A_LOG_FILE",
        "STUDENT_ID",
        "STUDENT_NAME",
        "LOGIN_EMAIL",
        "AUTH_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)


def test_cached_student_token_skips_startup_art(monkeypatch, tmp_path: Path) -> None:
    token_file = tmp_path / "auth_token"
    token_file.write_text("cached-token\n", encoding="utf-8")
    settings = Settings(
        config_dir=tmp_path,
        student_id="2024001",
        auth_token_file=token_file,
    )
    client = FakeClient()
    rendered = False

    def fake_render_startup(role_label: str, server_url: str) -> None:
        nonlocal rendered
        rendered = True

    monkeypatch.setattr("module_a.auth.render_startup", fake_render_startup)

    student_id = ensure_student_auth(client, settings)  # type: ignore[arg-type]

    assert student_id == "2024001"
    assert client.auth_token == "cached-token"
    assert rendered is False


def test_student_login_flow_renders_startup_without_cached_token(
    monkeypatch,
    tmp_path: Path,
) -> None:
    settings = Settings(config_dir=tmp_path, auth_token_file=tmp_path / "auth_token")
    rendered: list[tuple[str, str]] = []

    def fake_render_startup(role_label: str, server_url: str) -> None:
        rendered.append((role_label, server_url))

    monkeypatch.setattr("module_a.main.render_startup", fake_render_startup)

    assert _render_login_startup_if_needed(settings) is True
    assert rendered == [("Student", settings.server_url)]


def test_student_login_selects_profile_before_code_flow(monkeypatch, tmp_path: Path) -> None:
    _clear_module_a_env(monkeypatch)
    write_student_profile(
        tmp_path,
        "2024001",
        {
            "student_id": "2024001",
            "name": "Student One",
            "email": "student1@example.com",
        },
    )
    write_student_profile(
        tmp_path,
        "2024002",
        {
            "student_id": "2024002",
            "name": "Student Two",
            "email": "student2@example.com",
        },
    )
    settings = load_settings(tmp_path, config_dir=tmp_path)
    inputs = iter(["1"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(inputs))

    selected = _select_student_profile_for_login(settings)
    active = load_settings(tmp_path, config_dir=tmp_path)

    assert selected.profile_name == "2024001"
    assert selected.student_id == "2024001"
    assert selected.auth_token_file == tmp_path / "auth_tokens" / "2024001"
    assert active.profile_name == "2024001"


def test_student_setup_new_profile_does_not_reuse_active_identity(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _clear_module_a_env(monkeypatch)
    write_student_profile(
        tmp_path,
        "active",
        {
            "student_id": "2024001",
            "name": "Old Student",
            "email": "old@example.com",
            "class_code": "JOIN101",
        },
    )
    settings = load_settings(tmp_path, config_dir=tmp_path, profile_name="active")
    monkeypatch.setattr("module_a.main._command_prefix", lambda: "haocean-student")

    _handle_setup(
        Namespace(
            server_url="",
            student_id="2024002",
            name="New Student",
            email="new@example.com",
            class_code="JOIN202",
            profile="new-profile",
            workspace_dir="",
        ),
        settings,
    )

    old_profile = load_settings(tmp_path, config_dir=tmp_path, profile_name="active")
    new_profile = load_settings(tmp_path, config_dir=tmp_path, profile_name="new-profile")

    assert old_profile.student_id == "2024001"
    assert old_profile.name == "Old Student"
    assert old_profile.email == "old@example.com"
    assert old_profile.class_code == "JOIN101"
    assert new_profile.student_id == "2024002"
    assert new_profile.name == "New Student"
    assert new_profile.email == "new@example.com"
    assert new_profile.class_code == "JOIN202"
