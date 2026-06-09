from __future__ import annotations

from argparse import Namespace
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from controller.auth import ensure_teacher_auth
from controller.api_client import ClassInfo, ModuleCApiError
from controller.config import Settings, load_settings, write_teacher_profile
from controller.main import (
    build_parser,
    _handle_setup,
    _choose_class_id,
    _derive_peer_review_weights,
    _grade_assignment_interactive,
    _normalize_deadline,
    _next_teacher_command,
    _select_class_interactive,
    _render_login_startup_if_needed,
    _select_teacher_profile_for_login,
)


class FakeRepository:
    def __init__(self) -> None:
        self.auth_token = ""

    def health(self) -> dict[str, object]:
        return {"auth_required": True}


class FakeClassRepository:
    def __init__(self, classes: list[object], *, fail: bool = False) -> None:
        self.classes = classes
        self.fail = fail

    def list_classes(self) -> list[object]:
        if self.fail:
            raise ModuleCApiError("failed")
        return self.classes


class FakeGradePeerReviewRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def list_assignment_submissions(self, assignment_id: str) -> dict[str, object]:
        return {
            "summary": {
                "total": 2,
                "pending": 2,
                "graded": 0,
                "rejected": 0,
            }
        }

    def get_score_stats(self, assignment_id: str) -> dict[str, object]:
        return {
            "summary": {
                "count": 2,
                "average": 0,
                "min": 0,
                "max": 0,
                "median": 0,
            },
            "scores": [],
        }

    def list_plagiarism(self, assignment_id: str) -> list[dict[str, object]]:
        return []

    def set_peer_review_stage(self, assignment_id: str, stage: str) -> dict[str, object]:
        self.calls.append(("stage", assignment_id, stage))
        return {"assignment_id": assignment_id, "stage": stage}

    def auto_assign_peer_review_tasks(self, assignment_id: str) -> dict[str, object]:
        self.calls.append(("assign", assignment_id, ""))
        return {
            "assignment_id": assignment_id,
            "student_count": 2,
            "reviews_per_student": 1,
            "tasks": [
                {"reviewer_student_id": "2024001", "submission_id": 2},
                {"reviewer_student_id": "2024002", "submission_id": 1},
            ],
        }


def make_class_info(class_id: str, class_name: str) -> ClassInfo:
    return ClassInfo(
        class_id=class_id,
        class_name=class_name,
        course_id=f"course_{class_id}",
        course_title=class_name,
        join_code="JOIN101",
        teacher_id="T001",
        created_at="2026-06-08 00:00:00",
        status="active",
    )


def test_teacher_parser_accepts_guide_before_auth() -> None:
    args = build_parser().parse_args(["guide"])

    assert args.command == "guide"


def test_cached_teacher_token_skips_startup_art(monkeypatch, tmp_path: Path) -> None:
    token_file = tmp_path / "auth_token"
    token_file.write_text("cached-token\n", encoding="utf-8")
    settings = Settings(
        config_dir=tmp_path,
        teacher_id="T001",
        auth_token_file=token_file,
    )
    repo = FakeRepository()
    rendered = False

    def fake_render_startup(role_label: str, server_url: str) -> None:
        nonlocal rendered
        rendered = True

    monkeypatch.setattr("controller.auth.render_startup", fake_render_startup)

    ensure_teacher_auth(repo, settings)  # type: ignore[arg-type]

    assert repo.auth_token == "cached-token"
    assert rendered is False


def test_teacher_login_flow_renders_startup_without_cached_token(
    monkeypatch,
    tmp_path: Path,
) -> None:
    settings = Settings(config_dir=tmp_path, auth_token_file=tmp_path / "auth_token")
    rendered: list[tuple[str, str]] = []

    def fake_render_startup(role_label: str, server_url: str) -> None:
        rendered.append((role_label, server_url))

    monkeypatch.setattr("controller.main.render_startup", fake_render_startup)

    assert _render_login_startup_if_needed(settings) is True
    assert rendered == [("Teacher", settings.api_base_url)]


def test_teacher_login_selects_profile_before_code_flow(monkeypatch, tmp_path: Path) -> None:
    write_teacher_profile(
        tmp_path,
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
        tmp_path,
        "T002",
        {
            "source": "http",
            "api_base_url": "http://127.0.0.1:9000",
            "teacher_id": "T002",
            "name": "Teacher Two",
            "email": "two@example.com",
        },
    )
    settings = load_settings(tmp_path, config_dir=tmp_path)
    monkeypatch.setattr("builtins.input", lambda _prompt: "1")

    selected = _select_teacher_profile_for_login(settings)

    assert selected.profile_name == "T001"
    assert selected.teacher_id == "T001"
    assert selected.email == "one@example.com"
    assert selected.api_base_url == "http://127.0.0.1:8000"


def test_teacher_setup_new_profile_does_not_reuse_active_identity(
    monkeypatch,
    tmp_path: Path,
) -> None:
    write_teacher_profile(
        tmp_path,
        "active",
        {
            "source": "http",
            "api_base_url": "http://127.0.0.1:8000",
            "teacher_id": "T001",
            "name": "Old Teacher",
            "email": "old@example.com",
        },
    )
    settings = load_settings(tmp_path, config_dir=tmp_path)
    answers = iter(["New Teacher", "new@example.com"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))

    _handle_setup(
        Namespace(
            api_base_url="",
            teacher_id="T002",
            name="",
            email="",
            profile="new-profile",
            download_dir="",
        ),
        settings,
    )

    old_profile = load_settings(tmp_path, config_dir=tmp_path, profile_name="active")
    new_profile = load_settings(tmp_path, config_dir=tmp_path, profile_name="new-profile")

    assert old_profile.name == "Old Teacher"
    assert old_profile.email == "old@example.com"
    assert new_profile.teacher_id == "T002"
    assert new_profile.name == "New Teacher"
    assert new_profile.email == "new@example.com"


def test_teacher_setup_changed_teacher_id_without_profile_prompts_for_new_identity(
    monkeypatch,
    tmp_path: Path,
) -> None:
    write_teacher_profile(
        tmp_path,
        "Test_Local",
        {
            "source": "http",
            "api_base_url": "http://127.0.0.1:8000",
            "teacher_id": "Test_Local",
            "name": "Old Local",
            "email": "old-local@example.com",
        },
    )
    settings = load_settings(tmp_path, config_dir=tmp_path)
    answers = iter(["Hao_test_2", "Hao Teacher", "hao@example.com"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))

    _handle_setup(
        Namespace(
            api_base_url="",
            teacher_id="",
            name="",
            email="",
            profile="",
            download_dir="",
        ),
        settings,
    )

    old_profile = load_settings(tmp_path, config_dir=tmp_path, profile_name="Test_Local")
    new_profile = load_settings(tmp_path, config_dir=tmp_path, profile_name="Hao_test_2")

    assert old_profile.name == "Old Local"
    assert old_profile.email == "old-local@example.com"
    assert new_profile.teacher_id == "Hao_test_2"
    assert new_profile.name == "Hao Teacher"
    assert new_profile.email == "hao@example.com"


def test_teacher_login_next_command_matches_setup_progress() -> None:
    assert _next_teacher_command(  # type: ignore[arg-type]
        FakeClassRepository([]),
        Settings(),
    ).endswith(" class")
    assert _next_teacher_command(  # type: ignore[arg-type]
        FakeClassRepository([object()]),
        Settings(current_class_id=""),
    ).endswith(" select")
    assert _next_teacher_command(  # type: ignore[arg-type]
        FakeClassRepository([object()]),
        Settings(current_class_id="cs101"),
    ).endswith(" publish")
    assert _next_teacher_command(  # type: ignore[arg-type]
        FakeClassRepository([], fail=True),
        Settings(),
    ).endswith(" class")


def test_choose_class_requires_left_number(monkeypatch, capsys) -> None:
    repo = FakeClassRepository([make_class_info("2", "test_2")])
    answers = iter(["q", "test_2", "1"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))

    selected = _choose_class_id(repo, Settings(current_class_id="2"))  # type: ignore[arg-type]

    assert selected == "2"
    assert "Choose the left number only." in capsys.readouterr().out


def test_select_class_prints_full_selected_class(monkeypatch, tmp_path: Path, capsys) -> None:
    repo = FakeClassRepository([make_class_info("2", "test_2")])
    answers = iter(["1"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))

    _select_class_interactive(  # type: ignore[arg-type]
        repo,
        Settings(config_dir=tmp_path, current_class_id=""),
    )

    assert "Selected   : id=2 name=test_2 course=test_2 code=JOIN101" in capsys.readouterr().out


def test_peer_review_peer_weight_defaults_to_one_minus_teacher_weight() -> None:
    assert _derive_peer_review_weights(True, 0.6, None) == (0.6, 0.4)
    assert _derive_peer_review_weights(True, None, None) == (0.7, 0.3)
    assert _derive_peer_review_weights(True, 0.6, 0.2) == (0.6, 0.2)


def test_grade_overview_can_open_peer_review_stage(monkeypatch, capsys) -> None:
    repo = FakeGradePeerReviewRepository()
    answers = iter(["pr", "", "q"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))

    _grade_assignment_interactive(  # type: ignore[arg-type]
        Settings(),
        repo,
        "005",
    )

    assert repo.calls == [("stage", "005", "peer_review"), ("assign", "005", "")]
    output = capsys.readouterr().out
    assert "Open peer review stage + assign tasks (pr)" in output
    assert "Peer Stage : peer_review" in output
    assert "Students   : 2" in output
    assert "Tasks      : 2" in output


def test_deadline_short_date_uses_beijing_year_and_end_of_day() -> None:
    now = datetime(2026, 6, 8, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))

    assert _normalize_deadline("6.10", now=now) == "2026-06-10 23:59:59"
    assert _normalize_deadline("6.10 18:30", now=now) == "2026-06-10 18:30:00"
    assert _normalize_deadline("2026-06-10", now=now) == "2026-06-10 23:59:59"
