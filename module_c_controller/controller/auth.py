from __future__ import annotations

import getpass
from pathlib import Path
import shutil

from .api_client import ModuleBRepository
from .config import Settings


LOGO_COLOR = "\033[1;38;2;34;197;94m"
ACCENT_COLOR = "\033[1;38;2;52;211;153m"
TEXT_COLOR = "\033[38;2;86;171;117m"
BORDER_COLOR = "\033[38;2;22;101;52m"
RESET = "\033[0m"


HAOCEAN_ART = """\
██╗  ██╗ █████╗  ██████╗  ██████╗███████╗ █████╗ ███╗   ██╗
██║  ██║██╔══██╗██╔═══██╗██╔════╝██╔════╝██╔══██╗████╗  ██║
███████║███████║██║   ██║██║     █████╗  ███████║██╔██╗ ██║
██╔══██║██╔══██║██║   ██║██║     ██╔══╝  ██╔══██║██║╚██╗██║
██║  ██║██║  ██║╚██████╔╝╚██████╗███████╗██║  ██║██║ ╚████║
╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝  ╚═════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝
"""

MOOC_ART = """\
███╗   ███╗ ██████╗  ██████╗  ██████╗
████╗ ████║██╔═══██╗██╔═══██╗██╔════╝
██╔████╔██║██║   ██║██║   ██║██║
██║╚██╔╝██║██║   ██║██║   ██║██║
██║ ╚═╝ ██║╚██████╔╝╚██████╔╝╚██████╗
╚═╝     ╚═╝ ╚═════╝  ╚═════╝  ╚═════╝
"""

HAOCEAN_LINES = HAOCEAN_ART.splitlines()
MOOC_LINES = MOOC_ART.splitlines()


def _host_label(server_url: str) -> str:
    return server_url.removeprefix("https://").removeprefix("http://").rstrip("/")


def _render_logo_panel() -> list[tuple[str, str]]:
    return [
        *[(line, LOGO_COLOR) for line in HAOCEAN_LINES],
        ("", TEXT_COLOR),
        *[(line, LOGO_COLOR) for line in MOOC_LINES],
    ]


def _usage_lines(role_label: str) -> list[str]:
    if role_label == "Teacher":
        return [
            "Teacher quick commands:",
            "class    create class",
            "select   choose active class",
            "publish  publish assignment",
            "grade    review, download, plagiarism",
            "Enter keeps defaults; q changes them.",
        ]
    return [
        "Welcome Student !",
        "After login: once asks Assignment ID.",
        "Submits workspace/<assignment_id>/ archive.",
        "Run feedback to save feedback_inbox/.",
    ]


def _render_info_panel(
    role_label: str,
    server_url: str,
    target_height: int,
) -> list[tuple[str, str]]:
    upper = [
        (f"{role_label} Console", ACCENT_COLOR),
        (f"Host  {_host_label(server_url)}", TEXT_COLOR),
        ("Auth  email code", TEXT_COLOR),
        ("Mode  interactive CLI", TEXT_COLOR),
    ]
    lower = [
        ("Haocean Mooc CLI", ACCENT_COLOR),
        *[(line, TEXT_COLOR) for line in _usage_lines(role_label)],
    ]
    blank_count = max(target_height - len(upper) - len(lower), 1)
    return [*upper, *[("", TEXT_COLOR)] * blank_count, *lower]


def _paint(line: str, color: str) -> str:
    return f"{color}{line}{RESET}" if line else ""


def _terminal_width() -> int:
    return max(shutil.get_terminal_size((140, 24)).columns - 1, 78)


def _print_startup_panel(
    left_lines: list[tuple[str, str]],
    right_lines: list[tuple[str, str]],
    frame_width: int,
) -> None:
    inner_width = frame_width - 2
    content_width = inner_width - 2
    gutter = "  |  "
    left_width = min(
        max(len(line) for line, _ in left_lines),
        max(content_width - len(gutter) - 28, 24),
    )
    right_width = content_width - left_width - len(gutter)
    height = max(len(left_lines), len(right_lines))

    print(f"{BORDER_COLOR}+{'-' * inner_width}+{RESET}")
    for index in range(height):
        left_line, left_color = left_lines[index] if index < len(left_lines) else ("", TEXT_COLOR)
        right_line, right_color = right_lines[index] if index < len(right_lines) else ("", TEXT_COLOR)
        left_line = left_line[:left_width]
        right_line = right_line[:right_width]
        left_padding = " " * (left_width - len(left_line))
        right_padding = " " * (right_width - len(right_line))
        print(
            f"{BORDER_COLOR}|{RESET} "
            f"{_paint(left_line, left_color)}{left_padding}"
            f"{gutter}"
            f"{_paint(right_line, right_color)}{right_padding}"
            f" {BORDER_COLOR}|{RESET}"
        )
    print(f"{BORDER_COLOR}+{'-' * inner_width}+{RESET}")


def render_startup(role_label: str, server_url: str) -> None:
    print("\033[2J\033[H", end="")
    left_lines = _render_logo_panel()
    _print_startup_panel(
        left_lines,
        _render_info_panel(role_label, server_url, len(left_lines)),
        _terminal_width(),
    )


def read_cached_token(token_file: Path) -> str:
    try:
        return token_file.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def save_cached_token(token_file: Path, token: str) -> None:
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(token.strip() + "\n", encoding="utf-8")


def ensure_teacher_auth(
    repo: ModuleBRepository,
    settings: Settings,
    *,
    show_startup: bool = True,
    force_code: bool = False,
) -> None:
    health = repo.health()
    if not health.get("auth_required"):
        return

    token = settings.auth_token or read_cached_token(settings.auth_token_file)
    if token and not force_code:
        repo.auth_token = token
        print("Auth       : cached token")
        return

    if show_startup:
        render_startup("Teacher", settings.api_base_url)
    email = settings.email.strip() or input("Email      : ").strip()
    teacher_id = settings.teacher_id.strip() or input("Teacher ID : ").strip()
    if not email:
        raise SystemExit("CONTROLLER_EMAIL or interactive email is required")
    if not teacher_id:
        raise SystemExit("CONTROLLER_TEACHER_ID or TEACHER_ID is required")

    payload = repo.request_login_code(email=email, teacher_id=teacher_id)
    delivery = payload.get("delivery")
    if delivery == "server_log" and payload.get("dev_code"):
        print(f"Code       : {payload['dev_code']} (dev mode)")
    else:
        print("Code       : sent to your email")

    code = getpass.getpass("Verify    : ").strip()
    login_payload = repo.login_with_code(email=email, teacher_id=teacher_id, code=code)
    token = str(login_payload.get("token", "")).strip()
    if not token:
        raise SystemExit("login succeeded but token was missing")
    save_cached_token(settings.auth_token_file, token)
    print("Status     : signed in")
