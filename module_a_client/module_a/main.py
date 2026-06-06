from __future__ import annotations

import argparse
import logging

from .api_client import ModuleBClient
from .archive import preview_assignment_archive
from .auth import ensure_student_auth, read_cached_token, render_startup
from .config import DEFAULT_SERVER_URL, Settings, load_settings, write_user_config
from .feedback import save_feedback_items
from .logger import configure_logging
from .watcher import AssignmentWatcher


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Haocean Mooc student CLI")
    subparsers = parser.add_subparsers(dest="command")
    setup = subparsers.add_parser("setup", help="Write ~/.haocean/config.json")
    setup.add_argument("--server-url", default="", help=f"Backend URL, default {DEFAULT_SERVER_URL}")
    setup.add_argument("--student-id", default="", help="Student display ID")
    setup.add_argument("--email", default="", help="Login email")
    setup.add_argument("--class-code", default="", help="Class join code")
    setup.add_argument("--workspace-dir", default="", help="Local workspace directory")

    subparsers.add_parser("login", help="Login with email verification code")
    subparsers.add_parser("list", help="List open assignments")
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
    peer_review = subparsers.add_parser("peer-review", help="Submit a peer review score")
    peer_review.add_argument("submission_id", type=int, help="Submission ID to review")
    peer_review.add_argument("score", type=int, help="Peer review score, 0-100")
    peer_review.add_argument("--comment", default="", help="Peer review comment")
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


def _ensure_auth(client: ModuleBClient, settings: Settings) -> str:
    student_id = ensure_student_auth(client, settings)
    if student_id:
        object.__setattr__(settings, "student_id", student_id)
    return settings.student_id


def _has_cached_auth(settings: Settings) -> bool:
    return bool(settings.auth_token.strip() or read_cached_token(settings.auth_token_file))


def _render_login_startup_if_needed(settings: Settings) -> bool:
    if _has_cached_auth(settings):
        return False
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
    student_id = args.student_id.strip() or settings.student_id or input("Student ID : ").strip()
    email = args.email.strip() or settings.email or input("Email      : ").strip()
    server_url = args.server_url.strip() or settings.server_url or DEFAULT_SERVER_URL
    updates = {
        "server_url": server_url,
        "student_id": student_id,
        "email": email,
        "class_code": args.class_code.strip() or settings.class_code,
    }
    if args.workspace_dir.strip():
        updates["workspace_dir"] = args.workspace_dir.strip()
    config_path = write_user_config(settings.config_dir, updates)
    updated_settings = load_settings(settings.project_root, config_dir=settings.config_dir)
    updated_settings.workspace_dir.mkdir(parents=True, exist_ok=True)
    print(f"Config     : {config_path}")
    print(f"Workspace  : {updated_settings.workspace_dir}")
    print("Next       : haocean-student login")


def _ensure_student_profile(settings: Settings) -> Settings:
    config_path = settings.config_dir / "config.json"
    has_config = config_path.exists()
    student_id = settings.student_id.strip()
    email = settings.email.strip()
    class_code = settings.class_code.strip()

    if has_config and student_id and email:
        return settings

    if not student_id:
        student_id = input("Student ID : ").strip()
    if not email:
        email = input("Email      : ").strip()
    if not class_code:
        class_code = input("Class Code (optional): ").strip()
    if not student_id:
        raise SystemExit("student_id is required")
    if not email:
        raise SystemExit("email is required")

    updates = {
        "server_url": settings.server_url or DEFAULT_SERVER_URL,
        "student_id": student_id,
        "email": email,
        "class_code": class_code,
    }
    config_path = write_user_config(settings.config_dir, updates)
    updated_settings = load_settings(settings.project_root, config_dir=settings.config_dir)
    updated_settings.workspace_dir.mkdir(parents=True, exist_ok=True)
    print(f"Config     : {config_path}")
    return updated_settings


def _run_login_flow(
    client: ModuleBClient,
    settings: Settings,
    *,
    startup_rendered: bool = False,
) -> None:
    student_id = ensure_student_auth(client, settings, show_startup=not startup_rendered)
    if student_id:
        object.__setattr__(settings, "student_id", student_id)
    _join_configured_class(client, settings)
    print(f"Student    : {settings.student_id}")
    print(f"Workspace  : {settings.workspace_dir}")
    print("Next       : haocean-student list")


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
        print(
            f"{assignment.assignment_id}\t{assignment.title}\t"
            f"{class_label}\t{assignment.deadline}"
        )


def _print_classes(client: ModuleBClient, settings: Settings) -> None:
    classes = client.list_my_classes(settings.student_id)
    if not classes:
        print("No joined classes.")
        return
    for item in classes:
        print(f"{item.class_id}\t{item.course_title}\t{item.class_name}\t{item.joined_at or ''}")


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


def main() -> None:
    args = build_parser().parse_args()
    settings = load_settings()
    configure_logging(settings.log_path)

    if args.command == "setup":
        _handle_setup(args, settings)
        return

    if args.command in {None, "login"}:
        startup_rendered = _render_login_startup_if_needed(settings)
        settings = _ensure_student_profile(settings)
        client = _build_client(settings)
        _run_login_flow(client, settings, startup_rendered=startup_rendered)
        return

    if args.command in {"once", "submit", "preview"} and not settings.assignment_filter:
        assignment_id = args.assignment_id.strip() if args.command in {"submit", "preview"} else ""
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
