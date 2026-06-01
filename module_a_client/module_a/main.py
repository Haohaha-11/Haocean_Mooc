from __future__ import annotations

import argparse
import logging

from .api_client import ModuleBClient
from .auth import ensure_student_auth
from .config import DEFAULT_SERVER_URL, Settings, load_settings, write_user_config
from .feedback import save_feedback_items
from .logger import configure_logging
from .watcher import AssignmentWatcher


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Haocean MOOC student CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
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
    print("Next       : haocean login")


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


def _run_sync(settings: Settings, client: ModuleBClient) -> None:
    watcher = AssignmentWatcher(
        client=client,
        student_id=settings.student_id,
        workspace_dir=settings.workspace_dir,
        cache_dir=settings.cache_dir,
        feedback_dir=settings.feedback_dir,
        debounce_seconds=settings.debounce_seconds,
        poll_interval_seconds=settings.poll_interval_seconds,
        assignment_filter=settings.assignment_filter,
    )
    watcher.sync_until_stable()


def main() -> None:
    args = build_parser().parse_args()
    settings = load_settings()
    configure_logging(settings.log_path)

    if args.command == "setup":
        _handle_setup(args, settings)
        return

    client = _build_client(settings)
    _ensure_auth(client, settings)

    if args.command == "login":
        _join_configured_class(client, settings)
        print(f"Student    : {settings.student_id}")
        print(f"Workspace  : {settings.workspace_dir}")
        return

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

    if args.command in {"once", "submit"} and not settings.assignment_filter:
        assignment_id = args.assignment_id.strip() if args.command == "submit" else ""
        if not assignment_id:
            assignment_id = input("Assignment ID: ").strip()
        if not assignment_id:
            raise SystemExit("assignment_id is required")
        object.__setattr__(settings, "assignment_filter", assignment_id)

    if args.command in {"once", "submit"}:
        _join_configured_class(client, settings)
        _run_sync(settings, client)
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
        )
        watcher.run_forever()


if __name__ == "__main__":
    main()
