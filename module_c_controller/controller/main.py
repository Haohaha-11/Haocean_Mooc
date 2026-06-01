from __future__ import annotations

import argparse
import tarfile
from pathlib import Path

from .auth import ensure_teacher_auth
from .api_client import ModuleBRepository
from .config import DEFAULT_API_BASE_URL, Settings, load_settings, write_user_config
from .tui import ApprovalApp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Haocean MOOC teacher CLI")
    subparsers = parser.add_subparsers(dest="command")

    setup = subparsers.add_parser("setup", help="Write ~/.haocean-teacher/config.json")
    setup.add_argument("--api-base-url", default="", help=f"Backend URL, default {DEFAULT_API_BASE_URL}")
    setup.add_argument("--teacher-id", default="", help="Teacher display ID")
    setup.add_argument("--email", default="", help="Login email")
    setup.add_argument("--download-dir", default="", help="Local download directory")

    subparsers.add_parser("login", help="Login with email verification code")
    subparsers.add_parser("tui", help="Open pending-review TUI")

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

    plagiarism = subparsers.add_parser("plagiarism", help="View plagiarism reports")
    plagiarism.add_argument("assignment_id")

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


def _require_http_repo(settings: Settings) -> ModuleBRepository:
    if settings.source != "http":
        raise SystemExit("This command requires CONTROLLER_SOURCE=http")
    repo = _build_repo(settings)
    ensure_teacher_auth(repo, settings)
    object.__setattr__(settings, "auth_token", repo.auth_token)
    return repo


def _handle_setup(args: argparse.Namespace, settings: Settings) -> None:
    teacher_id = args.teacher_id.strip() or settings.teacher_id or input("Teacher ID : ").strip()
    email = args.email.strip() or settings.email or input("Email      : ").strip()
    api_base_url = args.api_base_url.strip() or settings.api_base_url or DEFAULT_API_BASE_URL
    updates = {
        "source": "http",
        "api_base_url": api_base_url,
        "teacher_id": teacher_id,
        "email": email,
    }
    if args.download_dir.strip():
        updates["download_dir"] = args.download_dir.strip()
    config_path = write_user_config(settings.config_dir, updates)
    updated_settings = load_settings(settings.project_root, config_dir=settings.config_dir)
    updated_settings.download_dir.mkdir(parents=True, exist_ok=True)
    print(f"Config     : {config_path}")
    print(f"Downloads  : {updated_settings.download_dir}")
    print("Next       : haocean-teacher login")


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


def _print_stats(repo: ModuleBRepository, assignment_id: str) -> None:
    payload = repo.get_score_stats(assignment_id)
    summary = payload["summary"]
    print(
        f"Count={summary['count']} Avg={summary['average']} "
        f"Min={summary['min']} Max={summary['max']} Median={summary['median']}"
    )
    for item in payload.get("scores", []):
        print(
            f"{item['student_id']}\t{submission_score(item)}\t"
            f"teacher={item.get('teacher_score')}\tfinal={item.get('final_score')}"
        )


def submission_score(item: dict[str, object]) -> object:
    return item.get("effective_score")


def _print_history(repo: ModuleBRepository, student_id: str) -> None:
    payload = repo.get_student_history(student_id)
    summary = payload["summary"]
    print(f"Count={summary['count']} Avg={summary['average']} Best={summary['best']} Latest={summary['latest']}")
    for item in payload.get("scores", []):
        print(f"{item['assignment_id']}\t{item.get('assignment_title')}\t{item.get('effective_score')}")


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

    if args.command in {None, "tui"}:
        if settings.source == "http":
            repo = _build_repo(settings)
            ensure_teacher_auth(repo, settings)
            object.__setattr__(settings, "auth_token", repo.auth_token)
        ApprovalApp(settings).run()
        return

    repo = _require_http_repo(settings)

    if args.command == "login":
        print(f"Teacher    : {settings.teacher_id}")
        print(f"Downloads  : {settings.download_dir}")
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
        created = repo.create_assignment(
            assignment_id=args.assignment_id,
            title=args.title,
            description=args.description,
            deadline=args.deadline,
            class_id=args.class_id,
        )
        print(f"Assignment : {created['assignment_id']} {created['title']}")
        print(f"Class      : {created.get('class_id') or 'global'}")
        return

    if args.command == "plagiarism":
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
