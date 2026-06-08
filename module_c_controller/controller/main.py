from __future__ import annotations

import argparse
from datetime import datetime
import re
import sys
import tarfile
from pathlib import Path
from zoneinfo import ZoneInfo

from .auth import ensure_teacher_auth, render_startup
from .api_client import ClassInfo, ModuleBRepository, ModuleCApiError
from .config import (
    DEFAULT_API_BASE_URL,
    Settings,
    list_teacher_profiles,
    load_settings,
    set_active_profile,
    write_teacher_profile,
    write_user_config,
)
from .tui import ApprovalApp


BEIJING_TZ = ZoneInfo("Asia/Shanghai")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Haocean Mooc teacher CLI")
    subparsers = parser.add_subparsers(dest="command")

    setup = subparsers.add_parser("setup", help="Write ~/.haocean-teacher/config.json")
    setup.add_argument("--api-base-url", default="", help=f"Backend URL, default {DEFAULT_API_BASE_URL}")
    setup.add_argument("--teacher-id", default="", help="Teacher display ID")
    setup.add_argument("--name", default="", help="Teacher name")
    setup.add_argument("--email", default="", help="Login email")
    setup.add_argument("--profile", default="", help="Local profile name, default teacher ID")
    setup.add_argument("--download-dir", default="", help="Local download directory")

    subparsers.add_parser("login", help="Login with email verification code")
    subparsers.add_parser("profiles", help="List local teacher profiles")
    tui = subparsers.add_parser("tui", help="Open pending-review TUI")
    tui.add_argument("assignment_id", nargs="?", default="")
    subparsers.add_parser("class", help="Create a class interactively")
    subparsers.add_parser("select", help="Select the active class")

    publish = subparsers.add_parser("publish", help="Publish an assignment interactively")
    publish.add_argument("assignment_id", nargs="?", default="")
    publish.add_argument("title", nargs="?", default="")
    publish.add_argument("--class-id", default="")
    publish.add_argument("--description", default="")
    publish.add_argument("--deadline", default="")
    publish.add_argument("--weight", type=float, default=None, help="Relative weight in the course score")
    publish_peer = publish.add_mutually_exclusive_group()
    publish_peer.add_argument("--peer-review", dest="peer_review", action="store_true", default=None, help="Enable peer review")
    publish_peer.add_argument("--no-peer-review", dest="peer_review", action="store_false", help="Disable peer review")
    publish.add_argument("--teacher-weight", type=float, default=None, help="Teacher score weight when peer review is enabled")
    publish.add_argument("--peer-weight", type=float, default=None, help="Override peer score weight; defaults to 1 - teacher weight")

    peer_review = subparsers.add_parser("peer-review", help="Open peer review stage and assign tasks")
    peer_review.add_argument("assignment_id")
    peer_review.add_argument(
        "--stage",
        choices=["setup", "submission", "peer_review", "final_calculation", "closed"],
        default="peer_review",
        help="Peer review stage to set, default peer_review",
    )
    assign_mode = peer_review.add_mutually_exclusive_group()
    assign_mode.add_argument("--assign", dest="assign", action="store_true", default=None, help="Assign peer review tasks after setting the stage")
    assign_mode.add_argument("--no-assign", dest="assign", action="store_false", help="Only set the stage")

    grade = subparsers.add_parser("grade", help="Review assignments with reports and downloads")
    grade.add_argument("assignment_id", nargs="?", default="")

    classes = subparsers.add_parser("classes", help="Manage classes")
    class_sub = classes.add_subparsers(dest="classes_command", required=True)
    class_sub.add_parser("list", help="List classes")
    class_create = class_sub.add_parser("create", help="Create a class and join code")
    class_create.add_argument("class_name")
    class_create.add_argument("--course-title", default="")
    class_create.add_argument("--class-id", default="")
    class_create.add_argument("--course-id", default="")
    class_create.add_argument("--join-code", default="")

    assignment = subparsers.add_parser("assignment", help="Manage assignments")
    assignment_sub = assignment.add_subparsers(dest="assignment_command", required=True)
    assignment_create = assignment_sub.add_parser("create", help="Create an assignment")
    assignment_create.add_argument("assignment_id")
    assignment_create.add_argument("title")
    assignment_create.add_argument("--class-id", default="")
    assignment_create.add_argument("--description", default="")
    assignment_create.add_argument("--deadline", default="")
    assignment_create.add_argument("--weight", type=float, default=1.0, help="Relative weight in the course score")
    assignment_create.add_argument("--peer-review", action="store_true", help="Enable peer review")
    assignment_create.add_argument("--teacher-weight", type=float, default=None, help="Teacher score weight when peer review is enabled")
    assignment_create.add_argument("--peer-weight", type=float, default=None, help="Override peer score weight; defaults to 1 - teacher weight")
    assignment_view = assignment_sub.add_parser("view", help="View assignment workspace")
    assignment_view.add_argument("assignment_id")

    plagiarism = subparsers.add_parser("plagiarism", help="View plagiarism reports")
    plagiarism.add_argument("assignment_id")
    plagiarism.add_argument("--check", action="store_true", help="Run a plagiarism check before printing")
    plagiarism.add_argument("--method", choices=["token", "hybrid", "ai"], default="hybrid")
    plagiarism.add_argument("--threshold", type=float, default=0.75)
    plagiarism.add_argument("--ai-prefilter", type=float, default=None)
    plagiarism.add_argument("--ai-limit", type=int, default=None)

    stats = subparsers.add_parser("stats", help="View assignment score statistics")
    stats.add_argument("assignment_id")

    history = subparsers.add_parser("history", help="View one student's score history")
    history.add_argument("student_id")

    final_scores = subparsers.add_parser("final-scores", help="View or recalculate final scores")
    final_scores.add_argument("assignment_id")
    final_scores.add_argument("--calculate", action="store_true")

    archive = subparsers.add_parser("archive", help="Manage course archives")
    archive_sub = archive.add_subparsers(dest="archive_command", required=True)
    archive_create = archive_sub.add_parser("create", help="Create course archive")
    archive_create.add_argument("--name", default="")
    archive_create.add_argument("--note", default="")
    archive_sub.add_parser("list", help="List course archives")
    archive_download = archive_sub.add_parser("download", help="Download course archive")
    archive_download.add_argument("archive_name")

    download = subparsers.add_parser("download", help="Download a submission archive")
    download.add_argument("submission_id", type=int)
    download.add_argument("--file-name", default="")
    download.add_argument("--extract", action="store_true")

    return parser


def _build_repo(settings: Settings) -> ModuleBRepository:
    return ModuleBRepository(
        base_url=settings.api_base_url,
        teacher_id=settings.teacher_id,
        auth_token=settings.auth_token,
        timeout=settings.request_timeout_seconds,
    )


def _command_prefix() -> str:
    command = Path(sys.argv[0]).name
    if command == "haocean-teacher":
        return "haocean-teacher"
    return f"{sys.executable} {sys.argv[0]}"


def _require_http_repo(settings: Settings) -> ModuleBRepository:
    if settings.source != "http":
        raise SystemExit("This command requires CONTROLLER_SOURCE=http")
    repo = _build_repo(settings)
    try:
        ensure_teacher_auth(repo, settings)
    except ModuleCApiError as exc:
        raise SystemExit(f"Error      : {exc}") from exc
    object.__setattr__(settings, "auth_token", repo.auth_token)
    return repo


def _render_login_startup_if_needed(settings: Settings) -> bool:
    render_startup("Teacher", settings.api_base_url)
    return True


def _handle_setup(args: argparse.Namespace, settings: Settings) -> None:
    requested_profile = args.profile.strip()
    teacher_id = args.teacher_id.strip()
    if not teacher_id:
        default_teacher_id = settings.teacher_id.strip() if not requested_profile else "T001"
        default_teacher_id = default_teacher_id or "T001"
        raw_teacher_id = input(f"Teacher ID [{default_teacher_id}] : ").strip()
        teacher_id = raw_teacher_id or default_teacher_id

    active_teacher_id = settings.teacher_id.strip()
    if requested_profile:
        profile_name = requested_profile
        updating_active_profile = requested_profile == settings.profile_name
    elif teacher_id == active_teacher_id:
        profile_name = settings.profile_name or teacher_id
        updating_active_profile = True
    else:
        profile_name = teacher_id
        updating_active_profile = False

    default_name = settings.name if updating_active_profile else ""
    default_email = settings.email if updating_active_profile else ""
    name = args.name.strip() or default_name or input("Name       : ").strip()
    email = args.email.strip() or default_email or input("Email      : ").strip()
    if not teacher_id:
        raise SystemExit("teacher_id is required")
    if not name:
        raise SystemExit("name is required")
    if not email:
        raise SystemExit("email is required")
    api_base_url = args.api_base_url.strip() or settings.api_base_url or DEFAULT_API_BASE_URL
    updates = {
        "source": "http",
        "api_base_url": api_base_url,
        "teacher_id": teacher_id,
        "name": name,
        "email": email,
    }
    if args.download_dir.strip():
        updates["download_dir"] = args.download_dir.strip()
    config_path = write_teacher_profile(settings.config_dir, profile_name, updates)
    updated_settings = load_settings(
        settings.project_root,
        config_dir=settings.config_dir,
        profile_name=profile_name,
    )
    updated_settings.download_dir.mkdir(parents=True, exist_ok=True)
    print(f"Profile    : {updated_settings.profile_name}")
    print(f"Config     : {config_path}")
    print(f"Downloads  : {updated_settings.download_dir}")
    print(f"Next       : {_command_prefix()} login")


def _ensure_teacher_profile(settings: Settings) -> Settings:
    config_path = settings.config_dir / "config.json"
    has_config = config_path.exists()
    teacher_id = settings.teacher_id.strip()
    name = settings.name.strip()
    email = settings.email.strip()

    if has_config and teacher_id and name and email:
        return settings

    if not has_config or not teacher_id:
        default_teacher_id = teacher_id or "T001"
        raw_teacher_id = input(f"Teacher ID [{default_teacher_id}] : ").strip()
        teacher_id = raw_teacher_id or default_teacher_id
    if not name:
        name = input("Name       : ").strip()
    if not email:
        email = input("Email      : ").strip()
    if not name:
        raise SystemExit("name is required")
    if not email:
        raise SystemExit("email is required")

    updates = {
        "source": "http",
        "api_base_url": settings.api_base_url or DEFAULT_API_BASE_URL,
        "teacher_id": teacher_id,
        "name": name,
        "email": email,
    }
    profile_name = settings.profile_name or teacher_id
    config_path = write_teacher_profile(settings.config_dir, profile_name, updates)
    updated_settings = load_settings(
        settings.project_root,
        config_dir=settings.config_dir,
        profile_name=profile_name,
    )
    updated_settings.download_dir.mkdir(parents=True, exist_ok=True)
    print(f"Profile    : {updated_settings.profile_name}")
    print(f"Config     : {config_path}")
    return updated_settings


def _profile_label(profile: dict[str, str]) -> str:
    identity = profile["teacher_id"] or profile["email"] or profile["profile_name"]
    name = f" / {profile['name']}" if profile["name"] else ""
    email = f" / {profile['email']}" if profile["email"] else ""
    return f"{profile['profile_name']} ({identity}{name}{email})"


def _select_profile_name(profiles: list[dict[str, str]], raw_choice: str, default_name: str) -> str:
    choice = raw_choice.strip()
    if not choice:
        return default_name
    if choice.isdigit():
        index = int(choice)
        if 1 <= index <= len(profiles):
            return profiles[index - 1]["profile_name"]
    for profile in profiles:
        if choice == profile["profile_name"] or choice == profile["teacher_id"] or choice == profile["email"]:
            return profile["profile_name"]
    raise SystemExit(f"unknown teacher profile: {choice}")


def _select_teacher_profile_for_login(settings: Settings) -> Settings:
    profiles = list_teacher_profiles(settings.config_dir)
    if not profiles:
        return settings

    default_name = settings.profile_name or next(
        (profile["profile_name"] for profile in profiles if profile["active"] == "true"),
        profiles[0]["profile_name"],
    )
    print("Profiles   :")
    for index, profile in enumerate(profiles, start=1):
        marker = "*" if profile["profile_name"] == default_name else " "
        print(f"  {index}. {marker} {_profile_label(profile)}")
    raw_choice = input(f"Login Profile [{default_name}]: ").strip()
    selected_name = _select_profile_name(profiles, raw_choice, default_name)
    set_active_profile(settings.config_dir, selected_name)
    return load_settings(
        settings.project_root,
        config_dir=settings.config_dir,
        profile_name=selected_name,
    )


def _print_profiles(settings: Settings) -> None:
    profiles = list_teacher_profiles(settings.config_dir)
    if not profiles:
        print("No teacher profiles. Run setup first.")
        return
    for profile in profiles:
        marker = "*" if profile["active"] == "true" or profile["profile_name"] == settings.profile_name else " "
        print(
            f"{marker} {profile['profile_name']}\t{profile['teacher_id']}\t"
            f"{profile['name']}\t{profile['email']}\t{profile['api_base_url']}"
        )


def _next_teacher_command(repo: ModuleBRepository, settings: Settings) -> str:
    try:
        classes = repo.list_classes()
    except ModuleCApiError:
        return f"{_command_prefix()} class"
    if not classes:
        return f"{_command_prefix()} class"
    if not settings.current_class_id.strip():
        return f"{_command_prefix()} select"
    return f"{_command_prefix()} publish"


def _run_login_flow(settings: Settings) -> Settings:
    settings = _select_teacher_profile_for_login(settings)
    startup_rendered = _render_login_startup_if_needed(settings)
    settings = _ensure_teacher_profile(settings)
    repo = _build_repo(settings)
    print(f"Account    : {settings.teacher_id} / {settings.name} / {settings.email}")
    try:
        ensure_teacher_auth(repo, settings, show_startup=not startup_rendered, force_code=True)
    except ModuleCApiError as exc:
        raise SystemExit(f"Error      : {exc}") from exc
    object.__setattr__(settings, "auth_token", repo.auth_token)
    print(f"Teacher    : {settings.teacher_id}")
    print(f"Name       : {settings.name}")
    print(f"Downloads  : {settings.download_dir}")
    print(f"Next       : {_next_teacher_command(repo, settings)}")
    return settings


def _prompt_value(
    label: str,
    *,
    default: str = "",
    required: bool = False,
) -> str:
    while True:
        if default:
            raw = input(f"{label} [{default}] (Enter=confirm, q=change): ").strip()
            if raw.lower() == "q":
                raw = input(f"{label}: ").strip()
            value = raw or default
        else:
            value = input(f"{label}: ").strip()
        if value or not required:
            return value
        print(f"{label} is required.")


def _prompt_float_value(
    label: str,
    *,
    default: float = 1.0,
    minimum: float = 0.0,
    maximum: float | None = None,
) -> float:
    while True:
        raw = _prompt_value(label, default=f"{default:g}", required=True)
        try:
            value = float(raw)
        except ValueError:
            print(f"{label} must be a number.")
            continue
        if value < minimum:
            print(f"{label} must be at least {minimum:g}.")
            continue
        if maximum is not None and value > maximum:
            print(f"{label} must be at most {maximum:g}.")
            continue
        return value


def _normalize_deadline(raw_value: str, *, now: datetime | None = None) -> str:
    value = raw_value.strip()
    if not value:
        return ""
    normalized = re.sub(r"[./]", "-", value)
    patterns = [
        r"(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})"
        r"(?:\s+(?P<hour>\d{1,2}):(?P<minute>\d{1,2})(?::(?P<second>\d{1,2}))?)?",
        r"(?P<month>\d{1,2})-(?P<day>\d{1,2})"
        r"(?:\s+(?P<hour>\d{1,2}):(?P<minute>\d{1,2})(?::(?P<second>\d{1,2}))?)?",
    ]
    for pattern in patterns:
        match = re.fullmatch(pattern, normalized)
        if not match:
            continue
        parts = match.groupdict()
        current = now.astimezone(BEIJING_TZ) if now is not None else datetime.now(BEIJING_TZ)
        year = int(parts["year"]) if parts.get("year") else current.year
        if parts.get("hour"):
            hour = int(parts["hour"])
            minute = int(parts["minute"])
            second = int(parts["second"]) if parts.get("second") else 0
        else:
            hour = 23
            minute = 59
            second = 59
        try:
            deadline = datetime(
                year,
                int(parts["month"]),
                int(parts["day"]),
                hour,
                minute,
                second,
                tzinfo=BEIJING_TZ,
            )
        except ValueError as exc:
            raise ValueError(f"invalid deadline date: {raw_value}") from exc
        return deadline.strftime("%Y-%m-%d %H:%M:%S")
    raise ValueError("deadline must be YYYY-MM-DD, MM-DD, M.D, with optional HH:MM[:SS]")


def _prompt_deadline_value() -> str:
    while True:
        raw = _prompt_value("Deadline", required=False)
        if not raw:
            return ""
        try:
            return _normalize_deadline(raw)
        except ValueError as exc:
            print(str(exc))


def _prompt_bool_value(label: str, *, default: bool = False) -> bool:
    default_label = "Y/n" if default else "y/N"
    while True:
        raw = input(f"{label} [{default_label}]: ").strip().lower()
        if not raw:
            return default
        if raw in {"y", "yes", "true", "1", "on"}:
            return True
        if raw in {"n", "no", "false", "0", "off"}:
            return False
        print(f"{label} must be y or n.")


def _write_current_class(settings: Settings, class_id: str) -> Settings:
    write_user_config(settings.config_dir, {"current_class_id": class_id})
    return load_settings(settings.project_root, config_dir=settings.config_dir)


def _print_class_choices(classes: list[ClassInfo]) -> None:
    print("No.\tClass ID\tClass Name\tCourse\tJoin Code")
    for index, item in enumerate(classes, start=1):
        print(
            f"{index}\t{item.class_id}\t{item.class_name}\t"
            f"{item.course_title}\t{item.join_code}"
        )


def _format_class_info(item: ClassInfo) -> str:
    return (
        f"id={item.class_id} name={item.class_name} "
        f"course={item.course_title} code={item.join_code}"
    )


def _find_class_info(repo: ModuleBRepository, class_id: str) -> ClassInfo | None:
    for item in repo.list_classes():
        if item.class_id == class_id:
            return item
    return None


def _class_display(repo: ModuleBRepository, class_id: str) -> str:
    if not class_id:
        return "global"
    selected_class = _find_class_info(repo, class_id)
    if selected_class is None:
        return class_id
    return _format_class_info(selected_class)


def _bool_label(value: object) -> str:
    return "yes" if bool(value) else "no"


def _derive_peer_review_weights(
    peer_review_enabled: bool,
    teacher_weight: float | None,
    peer_weight: float | None,
) -> tuple[float, float]:
    effective_teacher_weight = 0.7 if teacher_weight is None else teacher_weight
    if peer_weight is not None:
        return effective_teacher_weight, peer_weight
    if peer_review_enabled:
        return effective_teacher_weight, round(1.0 - effective_teacher_weight, 10)
    return effective_teacher_weight, 0.3


def _resolve_class_number(classes: list[ClassInfo], raw_choice: str) -> str:
    if not raw_choice.isdigit():
        print("Choose the left number only.")
        return ""
    index = int(raw_choice)
    if 1 <= index <= len(classes):
        return classes[index - 1].class_id
    print(f"Choose a number between 1 and {len(classes)}.")
    return ""


def _choose_class_id(repo: ModuleBRepository, settings: Settings) -> str:
    current = settings.current_class_id.strip()
    classes: list[ClassInfo] | None = None

    def load_classes() -> list[ClassInfo]:
        nonlocal classes
        if classes is None:
            classes = repo.list_classes()
        return classes

    if current:
        current_class = next((item for item in load_classes() if item.class_id == current), None)
        current_label = current_class.class_name if current_class is not None else current
        raw = input(f"Class Name [{current_label}] (Enter=confirm, q=choose): ").strip()
        if raw == "":
            return current
        if raw.lower() != "q":
            print("Press Enter to confirm the current class name, or q to choose from the list.")

    classes = load_classes()
    if not classes:
        print("No classes. Run `haocean-teacher class` first.")
        return ""

    while True:
        _print_class_choices(classes)
        raw_choice = input("Choose class number: ").strip()
        if not raw_choice:
            return ""
        selected = _resolve_class_number(classes, raw_choice)
        if selected:
            return selected


def _create_class_interactive(repo: ModuleBRepository, settings: Settings) -> Settings:
    class_name = _prompt_value("Class Name", required=True)
    course_title = _prompt_value("Course Title", default=class_name)
    class_id = _prompt_value("Class ID", required=False)
    created = repo.create_class(
        class_name=class_name,
        course_title=course_title,
        class_id=class_id,
    )
    settings = _write_current_class(settings, created.class_id)
    print(f"Class      : {created.class_id} {created.class_name}")
    print(f"Join Code  : {created.join_code}")
    print(f"Selected   : {_format_class_info(created)}")
    return settings


def _select_class_interactive(repo: ModuleBRepository, settings: Settings) -> Settings:
    class_id = _choose_class_id(repo, settings)
    if not class_id:
        raise SystemExit("class_id is required")
    settings = _write_current_class(settings, class_id)
    selected_class = _find_class_info(repo, class_id)
    if selected_class is not None:
        print(f"Selected   : {_format_class_info(selected_class)}")
    else:
        print(f"Selected   : id={settings.current_class_id}")
    return settings


def _publish_assignment_interactive(
    repo: ModuleBRepository,
    settings: Settings,
    args: argparse.Namespace,
) -> None:
    assignment_id = args.assignment_id.strip() or _prompt_value("Assignment ID", required=True)
    title = args.title.strip() or _prompt_value("Title", default=assignment_id, required=True)
    class_id = args.class_id.strip() or _choose_class_id(repo, settings)
    description = args.description.strip() or _prompt_value("Description", required=False)
    try:
        deadline = _normalize_deadline(args.deadline) if args.deadline.strip() else _prompt_deadline_value()
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    assignment_weight = (
        args.weight
        if args.weight is not None
        else _prompt_float_value("Course Weight", default=1.0, minimum=0.0)
    )
    peer_review_enabled = (
        args.peer_review
        if args.peer_review is not None
        else _prompt_bool_value("Peer Review", default=False)
    )
    teacher_weight = args.teacher_weight
    if peer_review_enabled and args.peer_review is None:
        teacher_weight = _prompt_float_value(
            "Teacher Score Weight",
            default=0.7 if teacher_weight is None else teacher_weight,
            minimum=0.0,
            maximum=1.0,
        )
    teacher_weight, peer_weight = _derive_peer_review_weights(
        peer_review_enabled,
        teacher_weight,
        args.peer_weight,
    )
    created = repo.create_assignment(
        assignment_id=assignment_id,
        title=title,
        description=description,
        deadline=deadline,
        class_id=class_id,
        assignment_weight=assignment_weight,
        peer_review_enabled=peer_review_enabled,
        teacher_weight=teacher_weight,
        peer_weight=peer_weight,
    )
    if class_id:
        _write_current_class(settings, class_id)
    created_peer_review = created.get("peer_review_enabled")
    print(f"Assignment : {created['assignment_id']} {created['title']}")
    print(f"Class      : {_class_display(repo, str(created.get('class_id') or class_id))}")
    print(f"Deadline   : {created.get('deadline') or deadline or '-'}")
    print(f"Weight     : {created.get('assignment_weight')}")
    print(f"Peer Review: {_bool_label(peer_review_enabled if created_peer_review is None else created_peer_review)}")
    if created_peer_review is None and peer_review_enabled:
        print("Warning    : peer review fields were not returned; restart Module B if this should be enabled.")
    if created.get("peer_review_enabled"):
        print(f"Peer Stage : {created.get('peer_review_stage')}")
        print(f"Weights    : teacher={created.get('teacher_weight')} peer={created.get('peer_weight')}")


def _handle_peer_review_stage(
    repo: ModuleBRepository,
    args: argparse.Namespace,
    *,
    exit_on_error: bool = True,
) -> None:
    assignment_id = args.assignment_id.strip()
    if not assignment_id:
        raise SystemExit("assignment_id is required")

    stage = args.stage.strip()
    should_assign = args.assign if args.assign is not None else stage == "peer_review"
    try:
        updated = repo.set_peer_review_stage(assignment_id, stage)
        print(f"Assignment : {updated.get('assignment_id', assignment_id)}")
        print(f"Peer Stage : {updated.get('stage', stage)}")
        if not should_assign:
            print("Tasks      : not assigned")
            return
        assigned = repo.auto_assign_peer_review_tasks(assignment_id)
    except ModuleCApiError as exc:
        if exit_on_error:
            raise SystemExit(f"Error      : {exc}") from exc
        print(f"Error      : {exc}")
        return

    tasks = assigned.get("tasks", [])
    task_count = len(tasks) if isinstance(tasks, list) else 0
    print(f"Students   : {assigned.get('student_count', 0)}")
    print(f"Reviews/Stu: {assigned.get('reviews_per_student', 0)}")
    print(f"Tasks      : {task_count}")
    print(f"Next       : haocean-student peer-review --assignment-id {assignment_id}")


def _grade_assignment_interactive(
    settings: Settings,
    repo: ModuleBRepository,
    assignment_id: str = "",
) -> None:
    selected_assignment_id = assignment_id.strip() or _prompt_value("Assignment ID for report", required=True)
    while True:
        items = _print_grade_overview(repo, selected_assignment_id)
        raw = input("Open item [1] (Enter=confirm, q=quit): ").strip().lower()
        if raw in {"q", "quit", "exit"}:
            return
        choice = raw or "1"
        if choice in {"t", "tui"}:
            action = "tui"
        elif choice in {"pr", "peer", "peer-review"}:
            action = "peer_review"
        elif choice.isdigit() and 1 <= int(choice) <= len(items):
            action = items[int(choice) - 1]["action"]
        else:
            print("Unknown item.")
            continue

        if action == "pending":
            _print_submission_status_detail(repo, selected_assignment_id, "pending")
        elif action == "graded":
            _print_submission_status_detail(repo, selected_assignment_id, "approved")
        elif action == "all":
            _print_submission_status_detail(repo, selected_assignment_id, None)
        elif action == "plagiarism":
            if selected_assignment_id:
                _print_plagiarism(repo, selected_assignment_id)
            else:
                print("Assignment ID is required for plagiarism reports.")
        elif action == "stats":
            if selected_assignment_id:
                _print_stats(repo, selected_assignment_id)
            else:
                print("Assignment ID is required for score stats.")
        elif action == "final":
            if selected_assignment_id:
                _print_final_scores(repo, selected_assignment_id)
            else:
                print("Assignment ID is required for final scores.")
        elif action == "peer_review":
            if selected_assignment_id:
                _handle_peer_review_stage(
                    repo,
                    argparse.Namespace(
                        assignment_id=selected_assignment_id,
                        stage="peer_review",
                        assign=None,
                    ),
                    exit_on_error=False,
                )
            else:
                print("Assignment ID is required for peer review.")
        elif action == "tui":
            print("TUI        : Enter grade, d download, s stats, p pending, a graded, l all, q quit")
            ApprovalApp(settings, selected_assignment_id).run()
        input("Press Enter to return to overview.")


def _print_classes(repo: ModuleBRepository) -> None:
    classes = repo.list_classes()
    if not classes:
        print("No classes.")
        return
    for item in classes:
        print(f"{item.class_id}\t{item.course_title}\t{item.class_name}\tcode={item.join_code}")


def _print_plagiarism(repo: ModuleBRepository, assignment_id: str) -> None:
    reports = repo.list_plagiarism(assignment_id)
    if not reports:
        print("No plagiarism reports.")
        return
    for item in reports:
        print(
            f"{item['submission_id']}\t{item['student_id']}\t"
            f"{item['plagiarism_rate']}%\tmatch={item.get('matched_submission_id')}\t"
            f"scope={item.get('scope')}"
        )


def _print_plagiarism_check(payload: dict[str, object]) -> None:
    print(f"Assignment : {payload.get('assignment_id')}")
    print(f"Method     : {payload.get('method')}")
    print(f"Threshold  : {payload.get('threshold')}")
    print(f"Submissions: {payload.get('submission_count')}")
    print(f"Pairs      : {payload.get('candidate_pair_count')}")
    if payload.get("ai_enabled"):
        print(f"AI Model   : {payload.get('ai_model')}")
        print(f"AI Reviewed: {payload.get('ai_reviewed_count')} / limit={payload.get('ai_limit')}")
        if payload.get("ai_error_count"):
            print(f"AI Errors  : {payload.get('ai_error_count')}")
    pairs = payload.get("suspected_pairs") or []
    if not isinstance(pairs, list) or not pairs:
        print("Suspected  : none")
        return
    print("Suspected  :")
    for item in pairs:
        if not isinstance(item, dict):
            continue
        print(
            f"{item.get('submission_a')}:{item.get('student_a')} <-> "
            f"{item.get('submission_b')}:{item.get('student_b')} "
            f"score={item.get('similarity')} local={item.get('local_similarity')} "
            f"reason={item.get('reason')}"
        )


def _print_stats(repo: ModuleBRepository, assignment_id: str) -> None:
    payload = repo.get_score_stats(assignment_id)
    summary = payload["summary"]
    print(f"Assignment : {assignment_id}")
    print(
        f"Count={summary['count']} Avg={summary['average']} "
        f"Min={summary['min']} Max={summary['max']} Median={summary['median']}"
    )
    print("Student\tEffective\tTeacher\tPeer Avg\tBonus\tFinal\tWeight\tWeighted")
    for item in payload.get("scores", []):
        print(
            f"{item['student_id']}\t{submission_score(item)}\t"
            f"{item.get('teacher_score')}\t{item.get('peer_avg_score')}\t"
            f"{item.get('peer_bonus')}\t{item.get('final_score')}\t"
            f"{item.get('assignment_weight')}\t{item.get('weighted_score')}"
        )


def submission_score(item: dict[str, object]) -> object:
    return item.get("effective_score")


def _print_final_scores(repo: ModuleBRepository, assignment_id: str) -> None:
    rows = repo.get_score_stats(assignment_id).get("scores", [])
    if not rows:
        print("No final scores.")
        return
    print("Student\tTeacher\tPeer Avg\tBonus\tFinal\tWeight\tWeighted")
    for item in rows:
        print(
            f"{item['student_id']}\t{item.get('teacher_score')}\t"
            f"{item.get('peer_avg_score')}\t{item.get('peer_bonus')}\t"
            f"{item.get('final_score')}\t{item.get('assignment_weight')}\t"
            f"{item.get('weighted_score')}"
        )


def _print_submission_status_detail(
    repo: ModuleBRepository,
    assignment_id: str,
    status: str | None,
) -> None:
    submissions = repo.list_submissions(status, assignment_id or None)
    if not submissions:
        print("No submissions.")
        return
    print("ID\tStudent\tAssignment\tStatus\tTeacher\tPeer Avg\tBonus\tFinal\tSubmitted")
    for item in submissions:
        print(
            f"{item.id}\t{item.student_id}\t{item.assignment_id}\t{item.status}\t"
            f"{item.score}\t{item.peer_avg_score}\t{item.peer_bonus}\t"
            f"{item.final_score}\t{item.created_at}"
        )


def _print_grade_overview(repo: ModuleBRepository, assignment_id: str) -> list[dict[str, object]]:
    submissions = repo.list_assignment_submissions(assignment_id) if assignment_id else {
        "summary": {
            "total": len(repo.list_submissions(None)),
            "pending": len(repo.list_submissions("pending")),
            "graded": len(repo.list_submissions("approved")),
            "rejected": len(repo.list_submissions("rejected")),
        }
    }
    summary = submissions.get("summary", {})
    stats_payload = repo.get_score_stats(assignment_id) if assignment_id else {"summary": {}, "scores": []}
    stats = stats_payload.get("summary", {})
    scores = stats_payload.get("scores", [])
    reports = repo.list_plagiarism(assignment_id) if assignment_id else []
    weight = next((item.get("assignment_weight") for item in scores if isinstance(item, dict)), None)
    calculated = len([item for item in scores if isinstance(item, dict) and item.get("final_score") is not None])
    top_plagiarism = reports[0] if reports else None

    print("")
    print(f"Grade Overview: {assignment_id or 'all assignments'}")
    if weight is not None:
        print(f"Course Weight : {weight}")
    print(
        "Submissions   : total={total} pending={pending} graded={graded} rejected={rejected}".format(
            total=summary.get("total", 0),
            pending=summary.get("pending", 0),
            graded=summary.get("graded", 0),
            rejected=summary.get("rejected", 0),
        )
    )
    print(
        "Score Stats   : count={count} avg={average} min={min} max={max} median={median}".format(
            count=stats.get("count"),
            average=stats.get("average"),
            min=stats.get("min"),
            max=stats.get("max"),
            median=stats.get("median"),
        )
    )
    if top_plagiarism:
        print(
            f"Plagiarism    : top={top_plagiarism.get('plagiarism_rate')}% "
            f"submission={top_plagiarism.get('submission_id')}"
        )
    else:
        print("Plagiarism    : no reports")
    print(f"Final Scores  : calculated={calculated}")

    items = [
        {"label": f"Pending submissions ({summary.get('pending', 0)})", "action": "pending"},
        {"label": f"Graded submissions ({summary.get('graded', 0)})", "action": "graded"},
        {"label": f"All submissions ({summary.get('total', 0)})", "action": "all"},
        {"label": f"Plagiarism detail ({len(reports)})", "action": "plagiarism"},
        {"label": f"Score statistics ({stats.get('count', 0)})", "action": "stats"},
    ]
    if assignment_id:
        items.append({"label": "Open peer review stage + assign tasks (pr)", "action": "peer_review"})
    items.extend(
        [
            {"label": f"Final score detail ({calculated})", "action": "final"},
            {"label": "Enter TUI", "action": "tui"},
        ]
    )
    for index, item in enumerate(items, start=1):
        print(f"{index}. {item['label']}")
    return items


def _print_history(repo: ModuleBRepository, student_id: str) -> None:
    payload = repo.get_student_history(student_id)
    summary = payload["summary"]
    print(f"Count={summary['count']} Avg={summary['average']} Best={summary['best']} Latest={summary['latest']}")
    for item in payload.get("scores", []):
        print(
            f"{item['assignment_id']}\t{item.get('assignment_title')}\t"
            f"teacher={item.get('teacher_score')}\tpeer={item.get('peer_avg_score')}\t"
            f"bonus={item.get('peer_bonus')}\tfinal={item.get('final_score')}\t"
            f"weight={item.get('assignment_weight')}\tweighted={item.get('weighted_score')}"
        )


def _print_assignment_workspace(repo: ModuleBRepository, assignment_id: str) -> None:
    submissions = repo.list_assignment_submissions(assignment_id)
    summary = submissions.get("summary", {})
    stats_payload = repo.get_score_stats(assignment_id)
    stats = stats_payload.get("summary", {})
    reports = repo.list_plagiarism(assignment_id)
    scores = stats_payload.get("scores", [])
    weight = next((item.get("assignment_weight") for item in scores if isinstance(item, dict)), None)
    print(f"Assignment : {assignment_id}")
    if weight is not None:
        print(f"Weight     : {weight}")
    print(
        "Submissions: total={total} pending={pending} graded={graded} rejected={rejected}".format(
            total=summary.get("total", 0),
            pending=summary.get("pending", 0),
            graded=summary.get("graded", 0),
            rejected=summary.get("rejected", 0),
        )
    )
    print(
        "Scores     : count={count} avg={average} min={min} max={max} median={median}".format(
            count=stats.get("count"),
            average=stats.get("average"),
            min=stats.get("min"),
            max=stats.get("max"),
            median=stats.get("median"),
        )
    )
    if reports:
        top = reports[0]
        print(
            f"Plagiarism : top={top.get('plagiarism_rate')}% "
            f"submission={top.get('submission_id')} match={top.get('matched_submission_id')}"
        )
    else:
        print("Plagiarism : no reports")
    peer_ready = [item for item in scores if item.get("final_score") is not None]
    print(f"Final      : calculated={len(peer_ready)}")
    print("Next       : grade overview | tui | plagiarism | stats | final-scores --calculate | archive create")


def _extract_archive(archive_path: Path) -> Path:
    target_dir = archive_path.with_suffix("").with_suffix("")
    target_dir.mkdir(parents=True, exist_ok=True)
    resolved_target = target_dir.resolve()
    with tarfile.open(archive_path, "r:*") as tar:
        safe_members = []
        for member in tar.getmembers():
            member_path = (target_dir / member.name).resolve()
            if member_path != resolved_target and resolved_target not in member_path.parents:
                raise SystemExit(f"Refusing to extract unsafe path: {member.name}")
            safe_members.append(member)
        tar.extractall(target_dir, members=safe_members)
    return target_dir


def main() -> None:
    args = build_parser().parse_args()
    settings = load_settings()

    if args.command == "setup":
        _handle_setup(args, settings)
        return

    if args.command in {None, "login"}:
        _run_login_flow(settings)
        return

    if args.command == "profiles":
        _print_profiles(settings)
        return

    if args.command == "tui":
        settings = _ensure_teacher_profile(settings)
        if settings.source == "http":
            repo = _build_repo(settings)
            try:
                ensure_teacher_auth(repo, settings)
            except ModuleCApiError as exc:
                raise SystemExit(f"Error      : {exc}") from exc
            object.__setattr__(settings, "auth_token", repo.auth_token)
        ApprovalApp(settings, args.assignment_id).run()
        return

    repo = _require_http_repo(settings)

    if args.command == "class":
        _create_class_interactive(repo, settings)
        return

    if args.command == "select":
        _select_class_interactive(repo, settings)
        return

    if args.command == "publish":
        _publish_assignment_interactive(repo, settings, args)
        return

    if args.command == "peer-review":
        _handle_peer_review_stage(repo, args)
        return

    if args.command == "grade":
        _grade_assignment_interactive(settings, repo, args.assignment_id)
        return

    if args.command == "classes":
        if args.classes_command == "list":
            _print_classes(repo)
            return
        created = repo.create_class(
            class_name=args.class_name,
            course_title=args.course_title,
            class_id=args.class_id,
            course_id=args.course_id,
            join_code=args.join_code,
        )
        print(f"Class      : {created.class_id} {created.class_name}")
        print(f"Join Code  : {created.join_code}")
        return

    if args.command == "assignment":
        if args.assignment_command == "view":
            _print_assignment_workspace(repo, args.assignment_id)
            return
        teacher_weight, peer_weight = _derive_peer_review_weights(
            args.peer_review,
            args.teacher_weight,
            args.peer_weight,
        )
        try:
            deadline = _normalize_deadline(args.deadline)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        created = repo.create_assignment(
            assignment_id=args.assignment_id,
            title=args.title,
            description=args.description,
            deadline=deadline,
            class_id=args.class_id,
            assignment_weight=args.weight,
            peer_review_enabled=args.peer_review,
            teacher_weight=teacher_weight,
            peer_weight=peer_weight,
        )
        print(f"Assignment : {created['assignment_id']} {created['title']}")
        print(f"Class      : {_class_display(repo, str(created.get('class_id') or args.class_id))}")
        print(f"Deadline   : {created.get('deadline') or deadline or '-'}")
        print(f"Weight     : {created.get('assignment_weight')}")
        created_peer_review = created.get("peer_review_enabled")
        print(f"Peer Review: {_bool_label(args.peer_review if created_peer_review is None else created_peer_review)}")
        if created_peer_review is None and args.peer_review:
            print("Warning    : peer review fields were not returned; restart Module B if this should be enabled.")
        return

    if args.command == "plagiarism":
        if args.check:
            payload = repo.check_plagiarism(
                args.assignment_id,
                method=args.method,
                threshold=args.threshold,
                ai_prefilter=args.ai_prefilter,
                ai_limit=args.ai_limit,
            )
            _print_plagiarism_check(payload)
            return
        _print_plagiarism(repo, args.assignment_id)
        return

    if args.command == "stats":
        _print_stats(repo, args.assignment_id)
        return

    if args.command == "history":
        _print_history(repo, args.student_id)
        return

    if args.command == "final-scores":
        results = (
            repo.calculate_final_scores(args.assignment_id)
            if args.calculate
            else repo.get_score_stats(args.assignment_id).get("scores", [])
        )
        for item in results:
            print(
                f"{item['student_id']}\tteacher={item.get('teacher_score')}\t"
                f"peer={item.get('peer_avg_score')}\tbonus={item.get('peer_bonus')}\t"
                f"final={item.get('final_score')}"
            )
        return

    if args.command == "archive":
        if args.archive_command == "create":
            created = repo.create_archive(archive_name=args.name, note=args.note)
            print(f"Archive    : {created['archive_name']}")
            print(f"Download   : {created['download_url']}")
            return
        if args.archive_command == "list":
            archives = repo.list_archives()
            if not archives:
                print("No archives.")
                return
            for item in archives:
                print(f"{item['archive_name']}\t{item['created_at']}\t{item.get('note') or ''}")
            return
        path = repo.download_archive(args.archive_name, settings.download_dir)
        print(f"Saved      : {path}")
        return

    if args.command == "download":
        path = repo.download_submission(args.submission_id, settings.download_dir, args.file_name)
        print(f"Saved      : {path}")
        if args.extract:
            print(f"Extracted  : {_extract_archive(path)}")
        return


if __name__ == "__main__":
    main()
