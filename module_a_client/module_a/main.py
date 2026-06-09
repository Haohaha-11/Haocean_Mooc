from __future__ import annotations

import argparse
import logging
import sys
import zipfile
from pathlib import Path

from .ai_help import add_ai_help_arguments, run_ai_help
from .api_client import ModuleBClient
from .archive import preview_assignment_archive
from .auth import ensure_student_auth, render_startup
from .config import (
    DEFAULT_SERVER_URL,
    Settings,
    list_student_profiles,
    load_settings,
    set_active_profile,
    write_student_profile,
    write_user_config,
)
from .feedback import save_feedback_items
from .logger import configure_logging
from .watcher import AssignmentWatcher


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Haocean Mooc student CLI")
    subparsers = parser.add_subparsers(dest="command")
    setup = subparsers.add_parser("setup", help="Write ~/.haocean/config.json")
    setup.add_argument("--server-url", default="", help=f"Backend URL, default {DEFAULT_SERVER_URL}")
    setup.add_argument("--student-id", default="", help="Student display ID")
    setup.add_argument("--name", default="", help="Student name")
    setup.add_argument("--email", default="", help="Login email")
    setup.add_argument("--class-code", default="", help="Class join code")
    setup.add_argument("--profile", default="", help="Local profile name, default student ID")
    setup.add_argument("--workspace-dir", default="", help="Local workspace directory")

    subparsers.add_parser("login", help="Login with email verification code")
    subparsers.add_parser("profiles", help="List local student profiles")
    subparsers.add_parser("list", help="List open assignments")
    materials = subparsers.add_parser("materials", help="Download assignment materials")
    materials.add_argument("assignment_id", nargs="?", default="", help="Assignment ID")
    materials.add_argument("--no-extract", action="store_true", help="Do not extract zip materials")
    subparsers.add_parser("classes", help="List joined classes")
    join = subparsers.add_parser("join", help="Join a class by teacher-provided code")
    join.add_argument("class_code", nargs="?", default="", help="Class join code")
    subparsers.add_parser("feedback", help="Fetch and save feedback")
    subparsers.add_parser("once", help="Run one sync cycle")
    submit = subparsers.add_parser("submit", help="Submit one assignment from the local workspace")
    submit.add_argument("assignment_id", nargs="?", default="", help="Assignment ID")
    submit.add_argument("--dry-run", action="store_true", help="Preview files before submitting")
    submit.add_argument("--allow-zip", action="store_true", help="Allow nested archive files (*.zip, *.tar, *.gz, *.7z, *.rar)")
    preview = subparsers.add_parser("preview", help="Preview submission package without upload")
    preview.add_argument("assignment_id", nargs="?", default="", help="Assignment ID")
    preview.add_argument("--allow-zip", action="store_true", help="Allow nested archive files (*.zip, *.tar, *.gz, *.7z, *.rar)")
    peer_review = subparsers.add_parser("peer-review", help="List or submit peer review tasks")
    peer_review.add_argument("submission_id", type=int, nargs="?", help="Submission ID to review")
    peer_review.add_argument("score", type=int, nargs="?", help="Peer review score, 0-100")
    peer_review.add_argument("--assignment-id", default="", help="Filter peer review tasks by assignment")
    peer_review.add_argument("--comment", default="", help="Peer review comment")
    ai_help = subparsers.add_parser("ai-help", help="Ask the Haocean AI usage assistant")
    add_ai_help_arguments(ai_help)
    subparsers.add_parser("watch", help="Run background watcher")
    return parser


def _build_client(settings: Settings) -> ModuleBClient:
    return ModuleBClient(
        settings.server_url,
        auth_token=settings.auth_token,
        timeout=settings.request_timeout_seconds,
        retry_count=settings.retry_count,
        retry_backoff_seconds=settings.retry_backoff_seconds,
    )


def _command_prefix() -> str:
    command = Path(sys.argv[0]).name
    if command in {"haocean", "haocean-student"}:
        return "haocean-student"
    return f"{sys.executable} {sys.argv[0]}"


def _ensure_auth(client: ModuleBClient, settings: Settings) -> str:
    student_id = ensure_student_auth(client, settings)
    if student_id:
        object.__setattr__(settings, "student_id", student_id)
    return settings.student_id


def _render_login_startup_if_needed(settings: Settings) -> bool:
    render_startup("Student", settings.server_url)
    return True


def _join_class(client: ModuleBClient, settings: Settings, class_code: str) -> None:
    code = class_code.strip()
    if not code:
        code = input("Class Code : ").strip()
    if not code:
        raise SystemExit("class_code is required")
    if not settings.student_id:
        raise SystemExit("student_id is required before joining a class")

    info = client.join_class(settings.student_id, code)
    write_user_config(settings.config_dir, {"class_code": code})
    print(f"Joined     : {info.course_title} / {info.class_name} ({info.class_id})")


def _join_configured_class(client: ModuleBClient, settings: Settings) -> None:
    if not settings.class_code:
        return
    try:
        joined_codes = {item.join_code for item in client.list_my_classes(settings.student_id)}
    except Exception:
        joined_codes = set()
    if settings.class_code.upper() in joined_codes:
        return
    _join_class(client, settings, settings.class_code)


def _handle_setup(args: argparse.Namespace, settings: Settings) -> None:
    requested_profile = args.profile.strip()
    student_id = args.student_id.strip()
    if not student_id:
        default_student_id = (
            settings.student_id.strip()
            if not requested_profile or requested_profile == settings.profile_name
            else ""
        )
        if default_student_id:
            raw_student_id = input(f"Student ID [{default_student_id}] : ").strip()
            student_id = raw_student_id or default_student_id
        else:
            student_id = input("Student ID : ").strip()

    active_student_id = settings.student_id.strip()
    if requested_profile:
        profile_name = requested_profile
        updating_active_profile = requested_profile == settings.profile_name
    elif student_id == active_student_id:
        profile_name = settings.profile_name or student_id
        updating_active_profile = True
    else:
        profile_name = student_id
        updating_active_profile = False

    default_name = settings.name if updating_active_profile else ""
    default_email = settings.email if updating_active_profile else ""
    default_class_code = settings.class_code if updating_active_profile else ""
    name = args.name.strip() or default_name or input("Name       : ").strip()
    email = args.email.strip() or default_email or input("Email      : ").strip()
    class_code = args.class_code.strip() or default_class_code or input("Class Code (optional): ").strip()
    if not student_id:
        raise SystemExit("student_id is required")
    if not name:
        raise SystemExit("name is required")
    if not email:
        raise SystemExit("email is required")
    server_url = args.server_url.strip() or settings.server_url or DEFAULT_SERVER_URL
    updates = {
        "server_url": server_url,
        "student_id": student_id,
        "name": name,
        "email": email,
        "class_code": class_code,
    }
    if args.workspace_dir.strip():
        updates["workspace_dir"] = args.workspace_dir.strip()
    config_path = write_student_profile(settings.config_dir, profile_name, updates)
    updated_settings = load_settings(
        settings.project_root,
        config_dir=settings.config_dir,
        profile_name=profile_name,
    )
    updated_settings.workspace_dir.mkdir(parents=True, exist_ok=True)
    print(f"Profile    : {updated_settings.profile_name}")
    print(f"Config     : {config_path}")
    print(f"Workspace  : {updated_settings.workspace_dir}")
    print(f"Next       : {_command_prefix()} login")


def _ensure_student_profile(settings: Settings) -> Settings:
    config_path = settings.config_dir / "config.json"
    has_config = config_path.exists()
    student_id = settings.student_id.strip()
    name = settings.name.strip()
    email = settings.email.strip()
    class_code = settings.class_code.strip()

    if has_config and student_id and name and email:
        return settings

    if not student_id:
        student_id = input("Student ID : ").strip()
    if not name:
        name = input("Name       : ").strip()
    if not email:
        email = input("Email      : ").strip()
    if not class_code:
        class_code = input("Class Code (optional): ").strip()
    if not student_id:
        raise SystemExit("student_id is required")
    if not name:
        raise SystemExit("name is required")
    if not email:
        raise SystemExit("email is required")

    updates = {
        "server_url": settings.server_url or DEFAULT_SERVER_URL,
        "student_id": student_id,
        "name": name,
        "email": email,
        "class_code": class_code,
    }
    profile_name = settings.profile_name or student_id
    config_path = write_student_profile(settings.config_dir, profile_name, updates)
    updated_settings = load_settings(
        settings.project_root,
        config_dir=settings.config_dir,
        profile_name=profile_name,
    )
    updated_settings.workspace_dir.mkdir(parents=True, exist_ok=True)
    print(f"Profile    : {updated_settings.profile_name}")
    print(f"Config     : {config_path}")
    return updated_settings


def _profile_label(profile: dict[str, str]) -> str:
    identity = profile["student_id"] or profile["email"] or profile["profile_name"]
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
        if choice == profile["profile_name"] or choice == profile["student_id"] or choice == profile["email"]:
            return profile["profile_name"]
    raise SystemExit(f"unknown student profile: {choice}")


def _select_student_profile_for_login(settings: Settings) -> Settings:
    profiles = list_student_profiles(settings.config_dir)
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
    profiles = list_student_profiles(settings.config_dir)
    if not profiles:
        print("No student profiles. Run setup first.")
        return
    for profile in profiles:
        marker = "*" if profile["active"] == "true" or profile["profile_name"] == settings.profile_name else " "
        print(
            f"{marker} {profile['profile_name']}\t{profile['student_id']}\t"
            f"{profile['name']}\t{profile['email']}\t{profile['server_url']}"
        )


def _run_login_flow(
    client: ModuleBClient,
    settings: Settings,
    *,
    startup_rendered: bool = False,
) -> None:
    print(f"Account    : {settings.student_id} / {settings.name} / {settings.email}")
    student_id = ensure_student_auth(
        client,
        settings,
        show_startup=not startup_rendered,
        force_code=True,
    )
    if student_id:
        object.__setattr__(settings, "student_id", student_id)
    _join_configured_class(client, settings)
    print(f"Student    : {settings.student_id}")
    print(f"Name       : {settings.name}")
    print(f"Workspace  : {settings.workspace_dir}")
    print(f"Next       : {_command_prefix()} list")


def _print_assignments(client: ModuleBClient, settings: Settings) -> None:
    assignments = client.list_open_assignments()
    if settings.assignment_filter:
        assignments = [
            assignment
            for assignment in assignments
            if assignment.assignment_id == settings.assignment_filter
        ]
    if not assignments:
        print("No open assignments.")
        return
    for assignment in assignments:
        class_label = assignment.class_name or "global"
        materials_label = "materials=yes" if assignment.has_materials else "materials=no"
        print(
            f"{assignment.assignment_id}\t{assignment.title}\t"
            f"{class_label}\t{materials_label}\t{assignment.deadline}"
        )


def _print_classes(client: ModuleBClient, settings: Settings) -> None:
    classes = client.list_my_classes(settings.student_id)
    if not classes:
        print("No joined classes.")
        return
    for item in classes:
        print(f"{item.class_id}\t{item.course_title}\t{item.class_name}\t{item.joined_at or ''}")


def _print_peer_review_tasks(
    client: ModuleBClient,
    settings: Settings,
    assignment_id: str = "",
) -> None:
    tasks = client.list_peer_review_tasks(settings.student_id, assignment_id=assignment_id)
    if not tasks:
        print("No peer review tasks.")
        return
    for item in tasks:
        title = item.assignment_title or ""
        print(
            f"{item.assignment_id}\t{title}\t"
            f"submission={item.submission_id}\ttarget={item.target_student_id}"
        )
    print(f"Submit     : {_command_prefix()} peer-review <submission_id> <score> --comment \"...\"")


def _run_sync(settings: Settings, client: ModuleBClient, *, allow_zip: bool = False) -> None:
    watcher = AssignmentWatcher(
        client=client,
        student_id=settings.student_id,
        workspace_dir=settings.workspace_dir,
        cache_dir=settings.cache_dir,
        feedback_dir=settings.feedback_dir,
        debounce_seconds=settings.debounce_seconds,
        poll_interval_seconds=settings.poll_interval_seconds,
        assignment_filter=settings.assignment_filter,
        allow_zip=allow_zip,
    )
    watcher.sync_until_stable()


def _print_preview(settings: Settings, assignment_id: str, allow_zip: bool) -> None:
    assignment_dir = settings.workspace_dir / assignment_id
    preview = preview_assignment_archive(
        assignment_dir=assignment_dir,
        cache_dir=settings.cache_dir,
        student_id=settings.student_id,
        assignment_id=assignment_id,
        allow_zip=allow_zip,
    )
    print(f"assignment_id: {preview.assignment_id}")
    print(f"workspace: {preview.workspace_path}")
    print(f"temp_archive_path: {preview.archive_path}")
    print("included_files:")
    if preview.included_files:
        for item in preview.included_files:
            print(f"  - {item}")
    else:
        print("  - <none>")
    print("excluded_files:")
    if preview.excluded_files:
        for item in preview.excluded_files:
            print(f"  - {item.relative_path} ({item.reason})")
    else:
        print("  - <none>")
    print("archive_members:")
    if preview.archive_members:
        for item in preview.archive_members:
            print(f"  - {item}")
    else:
        print("  - <none>")


def _safe_extract_zip(zip_path: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    resolved_target = target_dir.resolve()
    with zipfile.ZipFile(zip_path, "r") as zf:
        safe_members = []
        for member in zf.infolist():
            member_path = (target_dir / member.filename).resolve()
            if member_path != resolved_target and resolved_target not in member_path.parents:
                raise SystemExit(f"Refusing to extract unsafe path: {member.filename}")
            safe_members.append(member)
        zf.extractall(target_dir, members=safe_members)


def _download_materials(
    client: ModuleBClient,
    settings: Settings,
    assignment_id: str,
    *,
    extract: bool = True,
) -> None:
    target_dir = settings.workspace_dir / assignment_id / "materials"
    downloaded_path = client.download_assignment_materials(assignment_id, target_dir)
    print(f"Saved      : {downloaded_path}")
    if extract and zipfile.is_zipfile(downloaded_path):
        _safe_extract_zip(downloaded_path, target_dir)
        print(f"Extracted  : {target_dir}")


def main() -> None:
    args = build_parser().parse_args()

    if args.command == "ai-help":
        run_ai_help(args.question, force_local=args.local)
        return

    settings = load_settings()
    configure_logging(settings.log_path)

    if args.command == "setup":
        _handle_setup(args, settings)
        return

    if args.command == "profiles":
        _print_profiles(settings)
        return

    if args.command in {None, "login"}:
        settings = _select_student_profile_for_login(settings)
        startup_rendered = _render_login_startup_if_needed(settings)
        settings = _ensure_student_profile(settings)
        client = _build_client(settings)
        _run_login_flow(client, settings, startup_rendered=startup_rendered)
        return

    if args.command in {"once", "submit", "preview", "materials"} and not settings.assignment_filter:
        assignment_id = args.assignment_id.strip() if args.command in {"submit", "preview", "materials"} else ""
        if not assignment_id:
            assignment_id = input("Assignment ID: ").strip()
        if not assignment_id:
            raise SystemExit("assignment_id is required")
        object.__setattr__(settings, "assignment_filter", assignment_id)

    if args.command in {"submit", "preview"} and (getattr(args, "dry_run", False) or args.command == "preview"):
        if not settings.student_id:
            raise SystemExit("student_id is required for preview (run haocean-student setup first)")
        _print_preview(settings, settings.assignment_filter, getattr(args, "allow_zip", False))
        return

    client = _build_client(settings)
    _ensure_auth(client, settings)

    if args.command == "join":
        _join_class(client, settings, args.class_code)
        return

    if args.command == "classes":
        _print_classes(client, settings)
        return

    if args.command == "list":
        _join_configured_class(client, settings)
        _print_assignments(client, settings)
        return

    if args.command == "materials":
        _join_configured_class(client, settings)
        _download_materials(
            client,
            settings,
            settings.assignment_filter,
            extract=not args.no_extract,
        )
        return

    if not settings.student_id:
        raise SystemExit("MODULE_A_STUDENT_ID or STUDENT_ID is required")

    if args.command == "feedback":
        saved_paths = save_feedback_items(
            client.list_feedback(settings.student_id),
            settings.feedback_dir,
        )
        for path in saved_paths:
            logging.info("feedback saved: path=%s", path)
            print(f"Saved      : {path}")
        return

    if args.command == "peer-review":
        if args.submission_id is None and args.score is None:
            _print_peer_review_tasks(client, settings, args.assignment_id)
            return
        if args.submission_id is None or args.score is None:
            raise SystemExit("peer-review requires both submission_id and score")
        result = client.submit_peer_review(
            reviewer_student_id=settings.student_id,
            submission_id=args.submission_id,
            score=args.score,
            comment=args.comment,
        )
        print(f"Assignment : {result.assignment_id}")
        print(f"Submission : {result.submission_id}")
        print(f"Reviewer   : {result.reviewer_student_id}")
        print(f"Score      : {result.score}")
        return

    if args.command in {"once", "submit"}:
        _join_configured_class(client, settings)
        _run_sync(settings, client, allow_zip=getattr(args, "allow_zip", False))
    elif args.command == "watch":
        _join_configured_class(client, settings)
        watcher = AssignmentWatcher(
            client=client,
            student_id=settings.student_id,
            workspace_dir=settings.workspace_dir,
            cache_dir=settings.cache_dir,
            feedback_dir=settings.feedback_dir,
            debounce_seconds=settings.debounce_seconds,
            poll_interval_seconds=settings.poll_interval_seconds,
            assignment_filter=settings.assignment_filter,
            allow_zip=False,
        )
        watcher.run_forever()


if __name__ == "__main__":
    main()
