from pathlib import Path, PurePosixPath
import base64
import csv
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
import difflib
import hashlib
import io
import json
import math
import os
import random
import re
import shutil
import sqlite3
import smtplib
import ssl
import secrets
from statistics import median
import tarfile
import time
from typing import Optional
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Depends, Header, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*_args: object, **_kwargs: object) -> bool:
        return False


ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")
NEW_API_ENV_FILE = os.getenv("MODULE_B_NEW_API_ENV_FILE", "")
if NEW_API_ENV_FILE:
    load_dotenv(NEW_API_ENV_FILE, override=False)
DATA_DIR = ROOT_DIR / "data"
DB_DIR = DATA_DIR / "db"
TMP_DIR = DATA_DIR / "tmp"
SUBMISSIONS_DIR = DATA_DIR / "submissions"
FEEDBACK_DIR = DATA_DIR / "feedback"
DB_PATH = DB_DIR / "engine.db"

SYSTEM_NAME = os.getenv("MODULE_B_SYSTEM_NAME", "Haocean Mooc")
AUTH_REQUIRED = os.getenv("MODULE_B_AUTH_REQUIRED", "false").lower() in {"1", "true", "yes", "on"}
VERIFICATION_VALID_SECONDS = int(os.getenv("MODULE_B_VERIFICATION_VALID_SECONDS", "600"))
SESSION_VALID_SECONDS = int(os.getenv("MODULE_B_SESSION_VALID_SECONDS", str(7 * 24 * 3600)))
DEV_VERIFICATION_LOG = os.getenv("MODULE_B_DEV_VERIFICATION_LOG", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

SMTP_SERVER = os.getenv("SMTPServer", os.getenv("SMTP_SERVER", ""))
SMTP_PORT = int(os.getenv("SMTPPort", os.getenv("SMTP_PORT", "587")))
SMTP_SSL_ENABLED = os.getenv("SMTPSSLEnabled", os.getenv("SMTP_SSL_ENABLED", "false")).lower() in {
    "1",
    "true",
    "yes",
    "on",
}
SMTP_FORCE_AUTH_LOGIN = os.getenv(
    "SMTPForceAuthLogin",
    os.getenv("SMTP_FORCE_AUTH_LOGIN", "false"),
).lower() in {"1", "true", "yes", "on"}
SMTP_ACCOUNT = os.getenv("SMTPAccount", os.getenv("SMTP_ACCOUNT", ""))
SMTP_FROM = os.getenv("SMTPFrom", os.getenv("SMTP_FROM", SMTP_ACCOUNT))
SMTP_TOKEN = os.getenv("SMTPToken", os.getenv("SMTP_TOKEN", ""))
SMTP_LOGIN_AUTH_SERVERS = {"smtp.sendcloud.net", "smtp.azurecomm.net"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", os.getenv("MODULE_B_DEEPSEEK_API_KEY", ""))
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
DEEPSEEK_TIMEOUT_SECONDS = _env_float("DEEPSEEK_TIMEOUT_SECONDS", 30.0)
DEEPSEEK_MAX_CHARS_PER_SUBMISSION = _env_int("DEEPSEEK_MAX_CHARS_PER_SUBMISSION", 8000)
DEEPSEEK_MAX_CANDIDATE_PAIRS = _env_int("DEEPSEEK_MAX_CANDIDATE_PAIRS", 12)
DEEPSEEK_PREFILTER_SIMILARITY = _env_float("DEEPSEEK_PREFILTER_SIMILARITY", 0.45)

ROLE_STUDENT = "student"
ROLE_TEACHER = "teacher"

for d in [DB_DIR, TMP_DIR, SUBMISSIONS_DIR, FEEDBACK_DIR]:
    d.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Module B - Assignment Engine")


BEIJING_TZ = ZoneInfo("Asia/Shanghai")


def now_str() -> str:
    return datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")


def safe_name(name: str) -> str:
    """
    只保留文件名本身，防止 ../ 这类路径穿越。
    例如 ../../evil.tar.gz 会变成 evil.tar.gz。
    """
    return Path(name).name


def calc_md5(file_path: Path) -> str:
    """
    分块计算 MD5。
    不一次性读入整个文件，避免大文件占用太多内存。
    """
    md5 = hashlib.md5()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            md5.update(chunk)
    return md5.hexdigest()


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db():
    conn = get_conn()

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS assignments (
            assignment_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            deadline TEXT,
            created_by TEXT,
            class_id TEXT,
            assignment_weight REAL NOT NULL DEFAULT 1.0,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open'
        );
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS courses (
            course_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            teacher_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active'
        );
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS classes (
            class_id TEXT PRIMARY KEY,
            course_id TEXT NOT NULL,
            class_name TEXT NOT NULL,
            join_code TEXT NOT NULL UNIQUE,
            teacher_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active'
        );
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS class_enrollments (
            class_id TEXT NOT NULL,
            student_id TEXT NOT NULL,
            email TEXT,
            joined_at TEXT NOT NULL,
            PRIMARY KEY (class_id, student_id)
        );
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS submissions (
            submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            assignment_id TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            md5 TEXT NOT NULL,
            submit_time TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            score INTEGER,
            comment TEXT,
            feedback_path TEXT
        );
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            role TEXT NOT NULL,
            display_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_login_at TEXT
        );
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS email_verification_codes (
            email TEXT NOT NULL,
            role TEXT NOT NULL,
            code TEXT NOT NULL,
            expires_at INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (email, role)
        );
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_sessions (
            token TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            role TEXT NOT NULL,
            display_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at INTEGER NOT NULL
        );
        """
    )

    conn.commit()
    conn.close()


class AssignmentPayload(BaseModel):
    teacher_id: str
    assignment_id: str
    title: str
    description: str = ""
    deadline: str = ""
    class_id: Optional[str] = None
    assignment_weight: float = 1.0
    peer_review_enabled: bool = False
    teacher_weight: float = 0.7
    peer_weight: float = 0.3
    bonus_threshold_1: int = 5


class AssignmentRequest(BaseModel):
    action: str
    timestamp: int
    payload: AssignmentPayload


class SubmissionPayload(BaseModel):
    student_id: str
    assignment_id: str
    md5: str
    file_name: Optional[str] = None


class SubmissionMetadata(BaseModel):
    action: str
    timestamp: int
    payload: SubmissionPayload


class AuthVerificationRequestPayload(BaseModel):
    email: str
    role: str
    display_id: str = ""


class AuthVerificationRequest(BaseModel):
    action: str
    timestamp: int
    payload: AuthVerificationRequestPayload


class AuthLoginPayload(BaseModel):
    email: str
    role: str
    code: str
    display_id: str = ""


class AuthLoginRequest(BaseModel):
    action: str
    timestamp: int
    payload: AuthLoginPayload


class CreateClassPayload(BaseModel):
    teacher_id: str = ""
    class_id: str = ""
    class_name: str
    course_id: str = ""
    course_title: str = ""
    join_code: str = ""


class CreateClassRequest(BaseModel):
    action: str
    timestamp: int
    payload: CreateClassPayload


class JoinClassPayload(BaseModel):
    student_id: str = ""
    join_code: str


class JoinClassRequest(BaseModel):
    action: str
    timestamp: int
    payload: JoinClassPayload


@dataclass(frozen=True)
class AuthContext:
    email: str
    role: str
    display_id: str


def normalize_role(role: str) -> str:
    normalized = role.strip().lower()
    if normalized not in {ROLE_STUDENT, ROLE_TEACHER}:
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "role must be student or teacher",
            },
        )
    return normalized


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "invalid email",
            },
        )
    return normalized


def default_display_id(email: str, role: str) -> str:
    local_part = email.split("@", 1)[0].strip()
    if local_part:
        return local_part
    return "student" if role == ROLE_STUDENT else "teacher"


def normalize_identifier(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip()).strip("_")


def generated_class_id(class_name: str) -> str:
    prefix = normalize_identifier(class_name).lower() or "class"
    return f"{prefix}_{secrets.token_hex(3)}"


def generated_join_code() -> str:
    return secrets.token_hex(3).upper()


def class_row_to_payload(row: sqlite3.Row) -> dict:
    return {
        "class_id": row["class_id"],
        "class_name": row["class_name"],
        "course_id": row["course_id"],
        "course_title": row["course_title"],
        "join_code": row["join_code"],
        "teacher_id": row["teacher_id"],
        "created_at": row["created_at"],
        "status": row["status"],
    }


def generate_verification_code() -> str:
    return f"{random.SystemRandom().randint(0, 999999):06d}"


def smtp_configured() -> bool:
    return bool(SMTP_SERVER and SMTP_ACCOUNT and SMTP_TOKEN and SMTP_FROM)


def deepseek_configured() -> bool:
    return bool(DEEPSEEK_API_KEY)


def should_use_smtp_login_auth() -> bool:
    server = SMTP_SERVER.lower()
    account = SMTP_ACCOUNT.lower()
    return (
        SMTP_FORCE_AUTH_LOGIN
        or "outlook" in server
        or "onmicrosoft" in server
        or "outlook" in account
        or "onmicrosoft" in account
        or server in SMTP_LOGIN_AUTH_SERVERS
    )


def login_smtp_client(client: smtplib.SMTP) -> None:
    if not should_use_smtp_login_auth():
        client.login(SMTP_ACCOUNT, SMTP_TOKEN)
        return

    code, response = client.docmd("AUTH", "LOGIN")
    if code != 334:
        raise smtplib.SMTPAuthenticationError(code, response)

    username = base64.b64encode(SMTP_ACCOUNT.encode("utf-8")).decode("ascii")
    code, response = client.docmd(username)
    if code != 334:
        raise smtplib.SMTPAuthenticationError(code, response)

    password = base64.b64encode(SMTP_TOKEN.encode("utf-8")).decode("ascii")
    code, response = client.docmd(password)
    if code != 235:
        raise smtplib.SMTPAuthenticationError(code, response)


def send_email(subject: str, receiver: str, html_content: str) -> None:
    if not smtp_configured():
        raise RuntimeError("SMTP server is not configured")

    message = EmailMessage()
    message["To"] = receiver
    message["From"] = f"{SYSTEM_NAME} <{SMTP_FROM}>"
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain=SMTP_FROM.split("@")[-1])
    message.set_content(html_content, subtype="html")

    if SMTP_PORT == 465 or SMTP_SSL_ENABLED:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context, timeout=10) as client:
            login_smtp_client(client)
            client.send_message(message)
        return

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as client:
        client.starttls(context=ssl.create_default_context())
        login_smtp_client(client)
        client.send_message(message)


def create_auth_error(message: str, status_code: int = 401) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "code": status_code,
            "message": message,
        },
    )


def get_auth_context(authorization: str | None = Header(default=None)) -> AuthContext | None:
    if not AUTH_REQUIRED:
        return None

    if not authorization or not authorization.startswith("Bearer "):
        raise create_auth_error("authorization token required")

    token = authorization.removeprefix("Bearer ").strip()
    conn = get_conn()
    row = conn.execute(
        """
        SELECT email, role, display_id, expires_at
        FROM auth_sessions
        WHERE token = ?;
        """,
        (token,),
    ).fetchone()
    conn.close()

    if row is None or int(row["expires_at"]) < int(time.time()):
        raise create_auth_error("authorization token is invalid or expired")

    return AuthContext(
        email=row["email"],
        role=row["role"],
        display_id=row["display_id"],
    )


def require_student(auth: AuthContext | None = Depends(get_auth_context)) -> AuthContext | None:
    if AUTH_REQUIRED and (auth is None or auth.role != ROLE_STUDENT):
        raise create_auth_error("student authorization required", 403)
    return auth


def require_teacher(auth: AuthContext | None = Depends(get_auth_context)) -> AuthContext | None:
    if AUTH_REQUIRED and (auth is None or auth.role != ROLE_TEACHER):
        raise create_auth_error("teacher authorization required", 403)
    return auth


def resolved_auth(auth: object) -> AuthContext | None:
    return auth if isinstance(auth, AuthContext) else None


@app.post("/v1/auth/request-code")
def request_auth_code(req: AuthVerificationRequest):
    if req.action != "REQUEST_LOGIN_CODE":
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "action must be REQUEST_LOGIN_CODE",
            },
        )

    role = normalize_role(req.payload.role)
    email = normalize_email(req.payload.email)
    display_id = req.payload.display_id.strip() or default_display_id(email, role)
    code = generate_verification_code()
    expires_at = int(time.time()) + VERIFICATION_VALID_SECONDS

    conn = get_conn()
    conn.execute(
        """
        INSERT INTO email_verification_codes (
            email, role, code, expires_at, created_at
        )
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(email, role) DO UPDATE SET
            code = excluded.code,
            expires_at = excluded.expires_at,
            created_at = excluded.created_at;
        """,
        (email, role, code, expires_at, now_str()),
    )
    conn.commit()
    conn.close()

    subject = f"{SYSTEM_NAME} 登录验证码"
    content = (
        f"<p>您好，你正在登录 {SYSTEM_NAME}。</p>"
        f"<p>身份：<strong>{role}</strong></p>"
        f"<p>验证码：<strong>{code}</strong></p>"
        f"<p>验证码 {VERIFICATION_VALID_SECONDS // 60} 分钟内有效。</p>"
    )

    delivery = "email"
    try:
        send_email(subject, email, content)
    except Exception as exc:
        if AUTH_REQUIRED and not DEV_VERIFICATION_LOG:
            raise HTTPException(
                status_code=500,
                detail={
                    "code": 500,
                    "message": f"failed to send verification email: {exc}",
                },
            )
        delivery = "server_log"
        print(
            f"[Module_B] login verification code: email={email} role={role} "
            f"display_id={display_id} code={code}"
        )

    return {
        "code": 200,
        "message": "verification code sent",
        "payload": {
            "email": email,
            "role": role,
            "display_id": display_id,
            "expires_at": expires_at,
            "delivery": delivery,
            "dev_code": code if delivery == "server_log" and DEV_VERIFICATION_LOG else None,
        },
    }


@app.post("/v1/auth/login")
def login_with_code(req: AuthLoginRequest):
    if req.action != "LOGIN_WITH_CODE":
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "action must be LOGIN_WITH_CODE",
            },
        )

    role = normalize_role(req.payload.role)
    email = normalize_email(req.payload.email)
    display_id = req.payload.display_id.strip() or default_display_id(email, role)
    now_ts = int(time.time())

    conn = get_conn()
    row = conn.execute(
        """
        SELECT code, expires_at
        FROM email_verification_codes
        WHERE email = ?
          AND role = ?;
        """,
        (email, role),
    ).fetchone()

    if row is None or row["code"] != req.payload.code.strip() or int(row["expires_at"]) < now_ts:
        conn.close()
        raise create_auth_error("verification code is invalid or expired", 400)

    token = secrets.token_urlsafe(32)
    expires_at = now_ts + SESSION_VALID_SECONDS
    conn.execute(
        """
        INSERT INTO users (
            email, role, display_id, created_at, last_login_at
        )
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(email) DO UPDATE SET
            role = excluded.role,
            display_id = excluded.display_id,
            last_login_at = excluded.last_login_at;
        """,
        (email, role, display_id, now_str(), now_str()),
    )
    conn.execute(
        """
        INSERT INTO auth_sessions (
            token, email, role, display_id, created_at, expires_at
        )
        VALUES (?, ?, ?, ?, ?, ?);
        """,
        (token, email, role, display_id, now_str(), expires_at),
    )
    conn.execute(
        """
        DELETE FROM email_verification_codes
        WHERE email = ?
          AND role = ?;
        """,
        (email, role),
    )
    conn.commit()
    conn.close()

    return {
        "code": 200,
        "message": "login succeeded",
        "payload": {
            "token": token,
            "email": email,
            "role": role,
            "display_id": display_id,
            "expires_at": expires_at,
        },
    }


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
def health():
    return {
        "code": 200,
        "message": "module_b_server is running",
        "db_path": str(DB_PATH),
        "auth_required": AUTH_REQUIRED,
        "smtp_configured": smtp_configured(),
        "deepseek_configured": deepseek_configured(),
        "time": now_str(),
    }


@app.post("/v1/classes")
def create_class(
    req: CreateClassRequest,
    auth: AuthContext | None = Depends(require_teacher),
):
    if req.action != "CREATE_CLASS":
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "action must be CREATE_CLASS",
            },
        )

    p = req.payload
    class_name = p.class_name.strip()
    if not class_name:
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "class_name is required",
            },
        )

    auth = resolved_auth(auth)
    teacher_id = auth.display_id if auth is not None else p.teacher_id.strip()
    if not teacher_id:
        teacher_id = "T001"

    class_id = normalize_identifier(p.class_id) if p.class_id else generated_class_id(class_name)
    course_id = normalize_identifier(p.course_id) if p.course_id else f"course_{class_id}"
    course_title = p.course_title.strip() or class_name
    join_code = normalize_identifier(p.join_code).upper() if p.join_code else generated_join_code()

    conn = get_conn()
    existing_class_name = conn.execute(
        """
        SELECT class_id
        FROM classes
        WHERE teacher_id = ?
          AND lower(class_name) = lower(?)
          AND status = 'active'
        LIMIT 1;
        """,
        (teacher_id, class_name),
    ).fetchone()
    if existing_class_name is not None:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": f"class_name already exists for this teacher: {class_name}",
            },
        )

    try:
        conn.execute(
            """
            INSERT INTO courses (
                course_id, title, teacher_id, created_at, status
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(course_id) DO UPDATE SET
                title = excluded.title,
                teacher_id = excluded.teacher_id,
                status = excluded.status;
            """,
            (course_id, course_title, teacher_id, now_str(), "active"),
        )
        conn.execute(
            """
            INSERT INTO classes (
                class_id, course_id, class_name, join_code,
                teacher_id, created_at, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (class_id, course_id, class_name, join_code, teacher_id, now_str(), "active"),
        )
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": f"class_id or join_code already exists: {exc}",
            },
        )

    row = conn.execute(
        """
        SELECT
            c.class_id,
            c.class_name,
            c.course_id,
            co.title AS course_title,
            c.join_code,
            c.teacher_id,
            c.created_at,
            c.status
        FROM classes c
        JOIN courses co ON co.course_id = c.course_id
        WHERE c.class_id = ?;
        """,
        (class_id,),
    ).fetchone()
    conn.close()

    return {
        "code": 200,
        "message": "class created",
        "payload": class_row_to_payload(row),
    }


@app.get("/v1/classes")
def list_classes(
    auth: AuthContext | None = Depends(require_teacher),
):
    auth = resolved_auth(auth)
    teacher_id = auth.display_id if auth is not None else ""

    conn = get_conn()
    if teacher_id:
        rows = conn.execute(
            """
            SELECT
                c.class_id,
                c.class_name,
                c.course_id,
                co.title AS course_title,
                c.join_code,
                c.teacher_id,
                c.created_at,
                c.status
            FROM classes c
            JOIN courses co ON co.course_id = c.course_id
            WHERE c.teacher_id = ?
            ORDER BY c.created_at DESC;
            """,
            (teacher_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT
                c.class_id,
                c.class_name,
                c.course_id,
                co.title AS course_title,
                c.join_code,
                c.teacher_id,
                c.created_at,
                c.status
            FROM classes c
            JOIN courses co ON co.course_id = c.course_id
            ORDER BY c.created_at DESC;
            """
        ).fetchall()
    conn.close()

    return {
        "code": 200,
        "message": "classes returned",
        "payload": {
            "classes": [class_row_to_payload(row) for row in rows],
        },
    }


@app.post("/v1/classes/join")
def join_class(
    req: JoinClassRequest,
    auth: AuthContext | None = Depends(require_student),
):
    if req.action != "JOIN_CLASS":
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "action must be JOIN_CLASS",
            },
        )

    auth = resolved_auth(auth)
    student_id = auth.display_id if auth is not None else req.payload.student_id.strip()
    student_email = auth.email if auth is not None else ""
    if not student_id:
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "student_id is required",
            },
        )

    join_code = normalize_identifier(req.payload.join_code).upper()
    conn = get_conn()
    row = conn.execute(
        """
        SELECT
            c.class_id,
            c.class_name,
            c.course_id,
            co.title AS course_title,
            c.join_code,
            c.teacher_id,
            c.created_at,
            c.status
        FROM classes c
        JOIN courses co ON co.course_id = c.course_id
        WHERE c.join_code = ?
          AND c.status = 'active';
        """,
        (join_code,),
    ).fetchone()

    if row is None:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "class join_code is invalid",
            },
        )

    conn.execute(
        """
        INSERT INTO class_enrollments (
            class_id, student_id, email, joined_at
        )
        VALUES (?, ?, ?, ?)
        ON CONFLICT(class_id, student_id) DO UPDATE SET
            email = excluded.email,
            joined_at = excluded.joined_at;
        """,
        (row["class_id"], student_id, student_email, now_str()),
    )
    conn.commit()
    conn.close()

    payload = class_row_to_payload(row)
    payload["student_id"] = student_id
    return {
        "code": 200,
        "message": "class joined",
        "payload": payload,
    }


@app.get("/v1/classes/my")
def list_my_classes(
    student_id: str = "",
    auth: AuthContext | None = Depends(require_student),
):
    auth = resolved_auth(auth)
    effective_student_id = auth.display_id if auth is not None else student_id.strip()
    if not effective_student_id:
        raise create_auth_error("student authorization required", 403)

    conn = get_conn()
    rows = conn.execute(
        """
        SELECT
            c.class_id,
            c.class_name,
            c.course_id,
            co.title AS course_title,
            c.join_code,
            c.teacher_id,
            c.created_at,
            c.status,
            e.joined_at
        FROM class_enrollments e
        JOIN classes c ON c.class_id = e.class_id
        JOIN courses co ON co.course_id = c.course_id
        WHERE e.student_id = ?
        ORDER BY e.joined_at DESC;
        """,
        (effective_student_id,),
    ).fetchall()
    conn.close()

    classes = []
    for row in rows:
        item = class_row_to_payload(row)
        item["joined_at"] = row["joined_at"]
        classes.append(item)

    return {
        "code": 200,
        "message": "student classes returned",
        "payload": {
            "student_id": effective_student_id,
            "classes": classes,
        },
    }


@app.post("/v1/assignments")
def create_assignment(
    req: AssignmentRequest,
    auth: AuthContext | None = Depends(require_teacher),
):
    if req.action != "CREATE_ASSIGNMENT":
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "action must be CREATE_ASSIGNMENT",
            },
        )

    p = req.payload
    auth = resolved_auth(auth)
    teacher_id = auth.display_id if auth is not None else p.teacher_id
    class_id = p.class_id.strip() if p.class_id else None
    if class_id == "":
        class_id = None
    if not math.isfinite(p.assignment_weight) or p.assignment_weight < 0:
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "assignment_weight must be a non-negative number",
            },
        )
    if p.teacher_weight < 0 or p.peer_weight < 0:
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "peer review weights must be non-negative",
            },
        )
    if p.teacher_weight + p.peer_weight <= 0:
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "teacher_weight + peer_weight must be greater than 0",
            },
        )

    conn = get_conn()
    if class_id:
        class_row = conn.execute(
            """
            SELECT class_id, teacher_id
            FROM classes
            WHERE class_id = ?;
            """,
            (class_id,),
        ).fetchone()
        if class_row is None:
            conn.close()
            raise HTTPException(
                status_code=400,
                detail={
                    "code": 400,
                    "message": "class_id does not exist",
                },
            )
        if auth is not None and class_row["teacher_id"] != teacher_id:
            conn.close()
            raise create_auth_error("teacher can only create assignments for own classes", 403)

    try:
        conn.execute(
            """
            INSERT INTO assignments (
                assignment_id, title, description, deadline,
                created_by, class_id, assignment_weight, created_at, status,
                peer_review_enabled, peer_review_stage, teacher_weight, peer_weight,
                bonus_threshold_1, bonus_value_1, bonus_threshold_2, bonus_value_2,
                bonus_threshold_3, bonus_value_3
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                p.assignment_id,
                p.title,
                p.description,
                p.deadline,
                teacher_id,
                class_id,
                p.assignment_weight,
                now_str(),
                "open",
                1 if p.peer_review_enabled else 0,
                "submission" if p.peer_review_enabled else "setup",
                p.teacher_weight,
                p.peer_weight,
                p.bonus_threshold_1,
                1,
                10,
                0,
                15,
                0,
            ),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "assignment_id already exists",
            },
        )
    finally:
        conn.close()

    return {
        "code": 200,
        "message": "assignment created",
        "payload": {
            "assignment_id": p.assignment_id,
            "title": p.title,
            "class_id": class_id,
            "deadline": p.deadline,
            "assignment_weight": p.assignment_weight,
            "peer_review_enabled": p.peer_review_enabled,
            "peer_review_stage": "submission" if p.peer_review_enabled else "setup",
            "teacher_weight": p.teacher_weight,
            "peer_weight": p.peer_weight,
            "peer_bonus_rule": f"+1 when peer score is within {p.bonus_threshold_1} points of teacher score",
            "status": "open",
        },
    }


@app.get("/v1/assignments/open")
def list_open_assignments(
    auth: AuthContext | None = Depends(get_auth_context),
):
    auth = resolved_auth(auth)
    conn = get_conn()
    if auth is not None and auth.role == ROLE_STUDENT:
        rows = conn.execute(
            """
            SELECT
                a.assignment_id,
                a.title,
                a.description,
                a.deadline,
                a.created_by,
                a.class_id,
                a.assignment_weight,
                c.class_name,
                co.title AS course_title,
                a.created_at,
                a.status
            FROM assignments a
            LEFT JOIN classes c ON c.class_id = a.class_id
            LEFT JOIN courses co ON co.course_id = c.course_id
            WHERE a.status = 'open'
              AND (
                    a.class_id IS NULL
                    OR a.class_id IN (
                        SELECT class_id
                        FROM class_enrollments
                        WHERE student_id = ?
                    )
              )
            ORDER BY a.created_at DESC;
            """,
            (auth.display_id,),
        ).fetchall()
    elif auth is not None and auth.role == ROLE_TEACHER:
        rows = conn.execute(
            """
            SELECT
                a.assignment_id,
                a.title,
                a.description,
                a.deadline,
                a.created_by,
                a.class_id,
                a.assignment_weight,
                c.class_name,
                co.title AS course_title,
                a.created_at,
                a.status
            FROM assignments a
            LEFT JOIN classes c ON c.class_id = a.class_id
            LEFT JOIN courses co ON co.course_id = c.course_id
            WHERE a.status = 'open'
              AND (
                    a.created_by = ?
                    OR c.teacher_id = ?
              )
            ORDER BY a.created_at DESC;
            """,
            (auth.display_id, auth.display_id),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT
                a.assignment_id,
                a.title,
                a.description,
                a.deadline,
                a.created_by,
                a.class_id,
                a.assignment_weight,
                c.class_name,
                co.title AS course_title,
                a.created_at,
                a.status
            FROM assignments a
            LEFT JOIN classes c ON c.class_id = a.class_id
            LEFT JOIN courses co ON co.course_id = c.course_id
            WHERE a.status = 'open'
            ORDER BY a.created_at DESC;
            """
        ).fetchall()
    conn.close()

    return {
        "code": 200,
        "message": "open assignments returned",
        "payload": {
            "assignments": [dict(row) for row in rows]
        },
    }


@app.post("/v1/submissions")
async def create_submission(
    metadata: str = Form(...),
    file: UploadFile = File(...),
    auth: AuthContext | None = Depends(require_student),
):
    """
    A -> B 提交作业接口。

    请求格式：
    - metadata: JSON 字符串，包含 student_id、assignment_id、md5
    - file: 作业压缩包，例如 2024001_home_1.tar.gz

    处理流程：
    1. 解析 metadata
    2. 先把上传文件保存到 data/tmp
    3. B 重新计算 MD5
    4. 和 metadata 中的 MD5 比较
    5. 一致则移动到 data/submissions 并写入 submissions 表
    6. 不一致则删除临时文件并返回 400
    """
    try:
        meta_dict = json.loads(metadata)
        meta = SubmissionMetadata(**meta_dict)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "invalid metadata json",
                "error": str(e),
            },
        )

    if meta.action != "SUBMIT":
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "action must be SUBMIT",
            },
        )

    p = meta.payload
    auth = resolved_auth(auth)
    student_id = auth.display_id if auth is not None else p.student_id
    upload_file_name = safe_name(file.filename or p.file_name or "submission.tar.gz")

    conn = get_conn()
    assignment = conn.execute(
        """
        SELECT assignment_id, status, class_id
        FROM assignments
        WHERE assignment_id = ?;
        """,
        (p.assignment_id,),
    ).fetchone()

    if assignment is None:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "assignment_id does not exist",
            },
        )

    if assignment["status"] != "open":
        conn.close()
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "assignment is not open",
            },
        )

    if auth is not None and assignment["class_id"]:
        enrollment = conn.execute(
            """
            SELECT class_id
            FROM class_enrollments
            WHERE class_id = ?
              AND student_id = ?;
            """,
            (assignment["class_id"], student_id),
        ).fetchone()
        if enrollment is None:
            conn.close()
            raise create_auth_error("student is not enrolled in assignment class", 403)

    timestamp = int(time.time())
    tmp_file = TMP_DIR / f"{timestamp}_{student_id}_{p.assignment_id}_{upload_file_name}"

    with tmp_file.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    actual_md5 = calc_md5(tmp_file)

    if actual_md5 != p.md5:
        tmp_file.unlink(missing_ok=True)
        conn.close()
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "md5 mismatch, rejected",
                "expected_md5": p.md5,
                "actual_md5": actual_md5,
            },
        )

    student_dir = SUBMISSIONS_DIR / student_id / p.assignment_id
    student_dir.mkdir(parents=True, exist_ok=True)

    final_file = student_dir / f"{timestamp}_{upload_file_name}"
    shutil.move(str(tmp_file), str(final_file))

    cur = conn.execute(
        """
        INSERT INTO submissions (
            student_id, assignment_id, file_name, file_path,
            md5, submit_time, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        (
            student_id,
            p.assignment_id,
            upload_file_name,
            str(final_file),
            actual_md5,
            now_str(),
            "pending",
        ),
    )
    submission_id = cur.lastrowid
    calculate_plagiarism_for_submission(conn, int(submission_id))
    conn.commit()
    conn.close()

    return {
        "code": 200,
        "message": "submission accepted",
        "payload": {
            "submission_id": submission_id,
            "student_id": student_id,
            "assignment_id": p.assignment_id,
            "file_name": upload_file_name,
            "md5": actual_md5,
            "status": "pending",
            "archive_path": str(final_file),
        },
    }


def normalize_submission_status_filter(status: str) -> str:
    normalized = status.strip().lower() or "pending"
    if normalized == "approved":
        normalized = "graded"
    allowed = {"pending", "graded", "rejected", "all"}
    if normalized not in allowed:
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "status must be pending, graded, rejected, approved, or all",
            },
        )
    return normalized


def build_submissions_response(
    status: str,
    assignment_id: str | None,
    auth: AuthContext | None,
) -> dict:
    status_filter = normalize_submission_status_filter(status)
    assignment_filter = assignment_id.strip() if assignment_id else ""
    auth = resolved_auth(auth)
    conn = get_conn()
    where = []
    params: list[object] = []
    if status_filter != "all":
        where.append("s.status = ?")
        params.append(status_filter)
    if assignment_filter:
        where.append("s.assignment_id = ?")
        params.append(assignment_filter)
    if auth is not None:
        where.append("(a.created_by = ? OR c.teacher_id = ?)")
        params.extend([auth.display_id, auth.display_id])

    where_sql = "WHERE " + " AND ".join(where) if where else ""
    rows = conn.execute(
        f"""
        SELECT
            s.submission_id,
            s.student_id,
            s.assignment_id,
            s.file_name,
            s.file_path,
            s.md5,
            s.submit_time,
            s.status,
            s.score,
            s.comment,
            s.feedback_path,
            s.peer_avg_score,
            s.peer_bonus,
            s.final_score,
            a.class_id,
            a.title AS assignment_title,
            a.assignment_weight,
            c.class_name
        FROM submissions s
        LEFT JOIN assignments a ON a.assignment_id = s.assignment_id
        LEFT JOIN classes c ON c.class_id = a.class_id
        {where_sql}
        ORDER BY s.submit_time DESC, s.submission_id DESC;
        """,
        params,
    ).fetchall()
    conn.close()

    submissions = []
    summary = {"total": 0, "pending": 0, "graded": 0, "rejected": 0}
    for row in rows:
        item = dict(row)
        item["download_url"] = f"/v1/submissions/{item['submission_id']}/download"
        submissions.append(item)
        summary["total"] += 1
        if item["status"] in summary:
            summary[item["status"]] += 1

    return {
        "code": 200,
        "message": "submissions returned",
        "payload": {
            "status": status_filter,
            "assignment_id": assignment_filter or None,
            "summary": summary,
            "submissions": submissions,
        },
    }


@app.get("/v1/submissions")
def list_submissions(
    status: str = "pending",
    assignment_id: str | None = None,
    auth: AuthContext | None = Depends(require_teacher),
):
    """
    B -> C 提交列表接口。
    status 支持 pending / graded / rejected / approved / all。
    """
    return build_submissions_response(status, assignment_id, auth)


@app.get("/v1/submissions/pending")
def list_pending_submissions(
    assignment_id: str | None = None,
    auth: AuthContext | None = Depends(require_teacher),
):
    """
    B -> C 待批改列表接口。保留旧路径兼容现有 C 端。
    """
    return build_submissions_response("pending", assignment_id, auth)


@app.get("/v1/submissions/{submission_id}/download")
def download_submission(
    submission_id: int,
    auth: AuthContext | None = Depends(require_teacher),
):
    auth = resolved_auth(auth)
    conn = get_conn()
    row = conn.execute(
        """
        SELECT
            s.submission_id,
            s.file_name,
            s.file_path,
            a.created_by,
            c.teacher_id AS class_teacher_id
        FROM submissions s
        JOIN assignments a ON a.assignment_id = s.assignment_id
        LEFT JOIN classes c ON c.class_id = a.class_id
        WHERE s.submission_id = ?;
        """,
        (submission_id,),
    ).fetchone()
    conn.close()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": 404,
                "message": "submission_id does not exist",
            },
        )

    if auth is not None and row["created_by"] != auth.display_id and row["class_teacher_id"] != auth.display_id:
        raise create_auth_error("teacher can only download own class submissions", 403)

    file_path = Path(row["file_path"])
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail={
                "code": 404,
                "message": "submission archive does not exist",
            },
        )

    return FileResponse(
        path=str(file_path),
        filename=row["file_name"],
        media_type="application/gzip",
    )


class GradePayload(BaseModel):
    submission_id: int
    teacher_id: str
    score: int
    comment: str = ""
    status: str = "graded"


class GradeRequest(BaseModel):
    action: str
    timestamp: int
    payload: GradePayload


def render_feedback_markdown(
    submission_id: int,
    student_id: str,
    assignment_id: str,
    teacher_id: str,
    score: int,
    comment: str,
    status: str,
    graded_at: str,
) -> str:
    """
    把老师的评分和评语渲染成 Markdown 文档。
    这个文件后面给 A 端拉取。
    """
    return f"""# 作业反馈

## 基本信息

- 提交编号：{submission_id}
- 学生学号：{student_id}
- 作业编号：{assignment_id}
- 批改教师：{teacher_id}
- 批改时间：{graded_at}
- 当前状态：{status}

## 批改结果

- 分数：{score}

## 教师评语

{comment}
"""


@app.post("/v1/submissions/grade")
def grade_submission(
    req: GradeRequest,
    auth: AuthContext | None = Depends(require_teacher),
):
    """
    C -> B 批改接口。

    C 端提交 submission_id、score、comment。
    B 端负责：
    1. 检查 submission_id 是否存在
    2. 更新 submissions 表中的状态、分数、评语
    3. 生成 Markdown 反馈文件
    4. 把 feedback_path 写回数据库
    """
    if req.action != "GRADE":
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "action must be GRADE",
            },
        )

    p = req.payload
    auth = resolved_auth(auth)
    teacher_id = auth.display_id if auth is not None else p.teacher_id

    if p.status not in ["graded", "rejected"]:
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "status must be graded or rejected",
            },
        )

    if p.score < 0 or p.score > 100:
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "score must be between 0 and 100",
            },
        )

    conn = get_conn()

    row = conn.execute(
        """
        SELECT
            s.submission_id,
            s.student_id,
            s.assignment_id,
            s.file_name,
            s.status,
            a.created_by,
            c.teacher_id AS class_teacher_id
        FROM submissions s
        LEFT JOIN assignments a ON a.assignment_id = s.assignment_id
        LEFT JOIN classes c ON c.class_id = a.class_id
        WHERE s.submission_id = ?;
        """,
        (p.submission_id,),
    ).fetchone()

    if row is None:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "submission_id does not exist",
            },
        )

    if auth is not None and row["created_by"] != teacher_id and row["class_teacher_id"] != teacher_id:
        conn.close()
        raise create_auth_error("teacher can only grade own class submissions", 403)

    if row["status"] not in {"pending", "graded", "rejected"}:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "submission cannot be graded in current status",
            },
        )

    student_id = row["student_id"]
    assignment_id = row["assignment_id"]
    graded_at = now_str()

    feedback_dir = FEEDBACK_DIR / student_id / assignment_id
    feedback_dir.mkdir(parents=True, exist_ok=True)

    feedback_file = feedback_dir / f"submission_{p.submission_id}_feedback.md"

    markdown = render_feedback_markdown(
        submission_id=p.submission_id,
        student_id=student_id,
        assignment_id=assignment_id,
        teacher_id=teacher_id,
        score=p.score,
        comment=p.comment,
        status=p.status,
        graded_at=graded_at,
    )

    feedback_file.write_text(markdown, encoding="utf-8")

    conn.execute(
        """
        UPDATE submissions
        SET status = ?,
            score = ?,
            comment = ?,
            feedback_path = ?
        WHERE submission_id = ?;
        """,
        (
            p.status,
            p.score,
            p.comment,
            str(feedback_file),
            p.submission_id,
        ),
    )
    if table_exists(conn, "ai_grading_reports"):
        conn.execute(
            "DELETE FROM ai_grading_reports WHERE submission_id = ?;",
            (p.submission_id,),
        )

    conn.commit()
    conn.close()

    return {
        "code": 200,
        "message": "submission graded",
        "payload": {
            "submission_id": p.submission_id,
            "student_id": student_id,
            "assignment_id": assignment_id,
            "score": p.score,
            "comment": p.comment,
            "status": p.status,
            "feedback_path": str(feedback_file),
            "graded_at": graded_at,
        },
    }


@app.get("/v1/feedback/{student_id}")
def list_feedback(
    student_id: str,
    auth: AuthContext | None = Depends(require_student),
):
    """
    A -> B 查询反馈接口。

    A 端根据 student_id 查询自己所有已经批改或打回的作业反馈。
    B 返回分数、评语、状态，以及 Markdown 文件内容。
    """
    auth = resolved_auth(auth)
    effective_student_id = auth.display_id if auth is not None else student_id
    conn = get_conn()

    rows = conn.execute(
        """
        SELECT
            submission_id,
            student_id,
            assignment_id,
            file_name,
            submit_time,
            status,
            score,
            comment,
            feedback_path
        FROM submissions
        WHERE student_id = ?
          AND status IN ('graded', 'rejected')
        ORDER BY submit_time DESC;
        """,
        (effective_student_id,),
    ).fetchall()

    conn.close()

    feedback_items = []

    for row in rows:
        item = dict(row)
        feedback_path = item.get("feedback_path")

        if feedback_path and Path(feedback_path).exists():
            item["feedback_markdown"] = Path(feedback_path).read_text(encoding="utf-8")
        else:
            item["feedback_markdown"] = ""

        feedback_items.append(item)

    return {
        "code": 200,
        "message": "feedback returned",
        "payload": {
            "student_id": effective_student_id,
            "feedback": feedback_items,
        },
    }
# =========================
# Phase 5: Peer Review & Course Archive
# =========================

import zipfile


PROJECT_DIR = ROOT_DIR.parent
ARCHIVE_DIR = DATA_DIR / "archives"
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)


def column_exists(conn, table_name: str, column_name: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table_name});").fetchall()
    return any(row["name"] == column_name for row in rows)


def table_exists(conn, table_name: str) -> bool:
    row = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = ?;
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def add_column_if_missing(conn, table_name: str, column_name: str, column_sql: str):
    if not column_exists(conn, table_name, column_name):
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql};")


def init_extra_db():
    """
    第五阶段数据库扩展：
    1. assignments 表增加互评配置字段；
    2. submissions 表增加互评平均分、最终分、互评奖励；
    3. 新建 peer_reviews 表保存学生互评；
    4. 新建 archives 表保存归档文件记录。
    """
    conn = get_conn()

    add_column_if_missing(
        conn,
        "assignments",
        "class_id",
        "class_id TEXT",
    )
    add_column_if_missing(
        conn,
        "assignments",
        "assignment_weight",
        "assignment_weight REAL NOT NULL DEFAULT 1.0",
    )
    add_column_if_missing(
        conn,
        "assignments",
        "peer_review_enabled",
        "peer_review_enabled INTEGER NOT NULL DEFAULT 0",
    )
    add_column_if_missing(
        conn,
        "assignments",
        "peer_review_stage",
        "peer_review_stage TEXT NOT NULL DEFAULT 'setup'",
    )
    add_column_if_missing(
        conn,
        "assignments",
        "teacher_weight",
        "teacher_weight REAL NOT NULL DEFAULT 0.7",
    )
    add_column_if_missing(
        conn,
        "assignments",
        "peer_weight",
        "peer_weight REAL NOT NULL DEFAULT 0.3",
    )
    add_column_if_missing(
        conn,
        "assignments",
        "bonus_threshold_1",
        "bonus_threshold_1 INTEGER NOT NULL DEFAULT 5",
    )
    add_column_if_missing(
        conn,
        "assignments",
        "bonus_value_1",
        "bonus_value_1 REAL NOT NULL DEFAULT 1",
    )
    add_column_if_missing(
        conn,
        "assignments",
        "bonus_threshold_2",
        "bonus_threshold_2 INTEGER NOT NULL DEFAULT 10",
    )
    add_column_if_missing(
        conn,
        "assignments",
        "bonus_value_2",
        "bonus_value_2 REAL NOT NULL DEFAULT 0",
    )
    add_column_if_missing(
        conn,
        "assignments",
        "bonus_threshold_3",
        "bonus_threshold_3 INTEGER NOT NULL DEFAULT 15",
    )
    add_column_if_missing(
        conn,
        "assignments",
        "bonus_value_3",
        "bonus_value_3 REAL NOT NULL DEFAULT 0",
    )

    add_column_if_missing(
        conn,
        "submissions",
        "peer_avg_score",
        "peer_avg_score REAL",
    )
    add_column_if_missing(
        conn,
        "submissions",
        "final_score",
        "final_score REAL",
    )
    add_column_if_missing(
        conn,
        "submissions",
        "peer_bonus",
        "peer_bonus REAL NOT NULL DEFAULT 0",
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS peer_reviews (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id TEXT NOT NULL,
            submission_id INTEGER NOT NULL,
            reviewer_student_id TEXT NOT NULL,
            score INTEGER NOT NULL,
            comment TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(submission_id, reviewer_student_id)
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS peer_review_tasks (
            task_id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id TEXT NOT NULL,
            reviewer_student_id TEXT NOT NULL,
            submission_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(assignment_id, reviewer_student_id, submission_id)
        );
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS archives (
            archive_id INTEGER PRIMARY KEY AUTOINCREMENT,
            archive_name TEXT NOT NULL UNIQUE,
            archive_path TEXT NOT NULL,
            created_at TEXT NOT NULL,
            note TEXT
        );
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS plagiarism_reports (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL UNIQUE,
            assignment_id TEXT NOT NULL,
            student_id TEXT NOT NULL,
            plagiarism_rate REAL NOT NULL DEFAULT 0,
            matched_submission_id INTEGER,
            matched_student_id TEXT,
            matched_assignment_id TEXT,
            scope TEXT NOT NULL,
            checked_at TEXT NOT NULL
        );
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_grading_reports (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL UNIQUE,
            assignment_id TEXT NOT NULL,
            student_id TEXT NOT NULL,
            model TEXT NOT NULL,
            source TEXT NOT NULL,
            generated_at TEXT NOT NULL,
            report_json TEXT NOT NULL
        );
        """
    )

    conn.commit()
    conn.close()


TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".py",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".js",
    ".ts",
    ".html",
    ".css",
    ".json",
    ".yaml",
    ".yml",
    ".csv",
    ".sql",
}
MAX_PLAGIARISM_TEXT_BYTES = 400_000
THREE_YEARS_SECONDS = 3 * 365 * 24 * 60 * 60


def _read_text_bytes(raw: bytes) -> str:
    return raw.decode("utf-8", errors="ignore")


def extract_archive_text(file_path: Path) -> str:
    """
    Extract text-like content from a submitted archive for a pragmatic similarity check.
    Binary-heavy files are ignored by extension where possible and decoded defensively.
    """
    if not file_path.exists():
        return ""

    collected: list[str] = []
    remaining = MAX_PLAGIARISM_TEXT_BYTES

    try:
        with tarfile.open(file_path, "r:*") as tar:
            for member in tar.getmembers():
                if remaining <= 0:
                    break
                if not member.isfile():
                    continue
                suffix = Path(member.name).suffix.lower()
                if suffix and suffix not in TEXT_EXTENSIONS:
                    continue
                extracted = tar.extractfile(member)
                if extracted is None:
                    continue
                chunk = extracted.read(min(member.size, remaining))
                remaining -= len(chunk)
                text = _read_text_bytes(chunk)
                if text.strip():
                    collected.append(text)
    except tarfile.TarError:
        raw = file_path.read_bytes()[:MAX_PLAGIARISM_TEXT_BYTES]
        collected.append(_read_text_bytes(raw))

    return "\n".join(collected)


def tokenize_for_similarity(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]", text.lower()))


def calculate_similarity_rate(text_a: str, text_b: str) -> float:
    if not text_a.strip() or not text_b.strip():
        return 0.0

    tokens_a = tokenize_for_similarity(text_a)
    tokens_b = tokenize_for_similarity(text_b)
    token_score = 0.0
    if tokens_a and tokens_b:
        token_score = len(tokens_a & tokens_b) / len(tokens_a | tokens_b)

    sample_a = text_a[:20_000]
    sample_b = text_b[:20_000]
    sequence_score = difflib.SequenceMatcher(None, sample_a, sample_b, autojunk=True).ratio()
    return round(max(token_score, sequence_score) * 100, 2)


def plagiarism_cutoff_time() -> str:
    return datetime.fromtimestamp(time.time() - THREE_YEARS_SECONDS).strftime("%Y-%m-%d %H:%M:%S")


def calculate_plagiarism_for_submission(conn, submission_id: int) -> dict:
    submission = conn.execute(
        """
        SELECT submission_id, student_id, assignment_id, file_path, submit_time
        FROM submissions
        WHERE submission_id = ?;
        """,
        (submission_id,),
    ).fetchone()

    if submission is None:
        return {}

    current_text = extract_archive_text(Path(submission["file_path"]))
    candidates = conn.execute(
        """
        SELECT submission_id, student_id, assignment_id, file_path, submit_time
        FROM submissions
        WHERE submission_id != ?
          AND (
                assignment_id = ?
                OR submit_time >= ?
          )
        ORDER BY submit_time DESC;
        """,
        (
            submission_id,
            submission["assignment_id"],
            plagiarism_cutoff_time(),
        ),
    ).fetchall()

    best_rate = 0.0
    best_match = None

    for candidate in candidates:
        candidate_text = extract_archive_text(Path(candidate["file_path"]))
        rate = calculate_similarity_rate(current_text, candidate_text)
        if rate > best_rate:
            best_rate = rate
            best_match = candidate

    scope = "none"
    matched_submission_id = None
    matched_student_id = None
    matched_assignment_id = None

    if best_match is not None:
        matched_submission_id = best_match["submission_id"]
        matched_student_id = best_match["student_id"]
        matched_assignment_id = best_match["assignment_id"]
        scope = (
            "current_assignment"
            if matched_assignment_id == submission["assignment_id"]
            else "last_three_years"
        )

    checked_at = now_str()
    conn.execute(
        """
        INSERT INTO plagiarism_reports (
            submission_id,
            assignment_id,
            student_id,
            plagiarism_rate,
            matched_submission_id,
            matched_student_id,
            matched_assignment_id,
            scope,
            checked_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(submission_id) DO UPDATE SET
            assignment_id = excluded.assignment_id,
            student_id = excluded.student_id,
            plagiarism_rate = excluded.plagiarism_rate,
            matched_submission_id = excluded.matched_submission_id,
            matched_student_id = excluded.matched_student_id,
            matched_assignment_id = excluded.matched_assignment_id,
            scope = excluded.scope,
            checked_at = excluded.checked_at;
        """,
        (
            submission_id,
            submission["assignment_id"],
            submission["student_id"],
            best_rate,
            matched_submission_id,
            matched_student_id,
            matched_assignment_id,
            scope,
            checked_at,
        ),
    )

    return {
        "submission_id": submission_id,
        "assignment_id": submission["assignment_id"],
        "student_id": submission["student_id"],
        "plagiarism_rate": best_rate,
        "matched_submission_id": matched_submission_id,
        "matched_student_id": matched_student_id,
        "matched_assignment_id": matched_assignment_id,
        "scope": scope,
        "checked_at": checked_at,
    }


def score_distribution(scores: list[float]) -> dict[str, int]:
    distribution = {
        "90_100": 0,
        "80_89": 0,
        "70_79": 0,
        "60_69": 0,
        "below_60": 0,
    }
    for score in scores:
        if score >= 90:
            distribution["90_100"] += 1
        elif score >= 80:
            distribution["80_89"] += 1
        elif score >= 70:
            distribution["70_79"] += 1
        elif score >= 60:
            distribution["60_69"] += 1
        else:
            distribution["below_60"] += 1
    return distribution


@app.on_event("startup")
def startup_extra_features():
    init_extra_db()


class PeerReviewConfigPayload(BaseModel):
    assignment_id: str
    enabled: bool = True
    teacher_weight: float = 0.7
    peer_weight: float = 0.3
    bonus_threshold_1: int = 5
    bonus_value_1: float = 1
    bonus_threshold_2: int = 10
    bonus_value_2: float = 0
    bonus_threshold_3: int = 15
    bonus_value_3: float = 0


class PeerReviewConfigRequest(BaseModel):
    action: str
    timestamp: int
    payload: PeerReviewConfigPayload


@app.post("/v1/assignments/peer-review/config")
def config_peer_review(
    req: PeerReviewConfigRequest,
    auth: AuthContext | None = Depends(require_teacher),
):
    """
    C -> B：配置某个作业是否开启互评。

    用法：
    - 期末大作业：enabled = true
    - 普通小作业：enabled = false
    """
    if req.action != "CONFIG_PEER_REVIEW":
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "action must be CONFIG_PEER_REVIEW",
            },
        )

    p = req.payload

    if p.teacher_weight < 0 or p.peer_weight < 0:
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "weights must be non-negative",
            },
        )

    if p.teacher_weight + p.peer_weight <= 0:
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "teacher_weight + peer_weight must be greater than 0",
            },
        )

    conn = get_conn()
    row = conn.execute(
        "SELECT assignment_id FROM assignments WHERE assignment_id = ?;",
        (p.assignment_id,),
    ).fetchone()

    if row is None:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "assignment_id does not exist",
            },
        )

    conn.execute(
        """
        UPDATE assignments
        SET peer_review_enabled = ?,
            peer_review_stage = 'setup',
            teacher_weight = ?,
            peer_weight = ?,
            bonus_threshold_1 = ?,
            bonus_value_1 = ?,
            bonus_threshold_2 = ?,
            bonus_value_2 = ?,
            bonus_threshold_3 = ?,
            bonus_value_3 = ?
        WHERE assignment_id = ?;
        """,
        (
            1 if p.enabled else 0,
            p.teacher_weight,
            p.peer_weight,
            p.bonus_threshold_1,
            1,
            p.bonus_threshold_2,
            0,
            p.bonus_threshold_3,
            0,
            p.assignment_id,
        ),
    )

    conn.commit()
    conn.close()

    return {
        "code": 200,
        "message": "peer review config updated",
        "payload": {
            "assignment_id": p.assignment_id,
            "peer_review_enabled": p.enabled,
            "peer_review_stage": "setup",
            "teacher_weight": p.teacher_weight,
            "peer_weight": p.peer_weight,
            "peer_bonus_rule": f"+1 when peer score is within {p.bonus_threshold_1} points of teacher score",
        },
    }


class PeerReviewStagePayload(BaseModel):
    stage: str


class PeerReviewStageRequest(BaseModel):
    action: str
    timestamp: int
    payload: PeerReviewStagePayload


PEER_REVIEW_STAGES = {"setup", "submission", "peer_review", "final_calculation", "closed"}
DEFAULT_PEER_REVIEWS_PER_STUDENT = 2


@app.post("/v1/assignments/{assignment_id}/peer-review/stage")
def set_peer_review_stage(
    assignment_id: str,
    req: PeerReviewStageRequest,
    auth: AuthContext | None = Depends(require_teacher),
):
    if req.action != "SET_PEER_REVIEW_STAGE":
        raise HTTPException(
            status_code=400,
            detail={"code": 400, "message": "action must be SET_PEER_REVIEW_STAGE"},
        )
    stage = req.payload.stage.strip()
    if stage not in PEER_REVIEW_STAGES:
        raise HTTPException(
            status_code=400,
            detail={"code": 400, "message": "invalid peer review stage"},
        )
    conn = get_conn()
    cur = conn.execute(
        "UPDATE assignments SET peer_review_stage = ? WHERE assignment_id = ?;",
        (stage, assignment_id),
    )
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        raise HTTPException(
            status_code=400,
            detail={"code": 400, "message": "assignment_id does not exist"},
        )
    return {
        "code": 200,
        "message": "peer review stage updated",
        "payload": {"assignment_id": assignment_id, "stage": stage},
    }


@app.post("/v1/assignments/{assignment_id}/peer-review/tasks/auto")
def auto_assign_peer_review_tasks(
    assignment_id: str,
    auth: AuthContext | None = Depends(require_teacher),
):
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT submission_id, student_id, submit_time
        FROM submissions
        WHERE assignment_id = ?
        ORDER BY submit_time ASC, submission_id ASC;
        """,
        (assignment_id,),
    ).fetchall()
    latest_by_student = {}
    for row in rows:
        latest_by_student[str(row["student_id"])] = row
    rows = sorted(
        latest_by_student.values(),
        key=lambda row: (str(row["submit_time"]), int(row["submission_id"])),
    )
    if len(rows) < 2:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail={"code": 400, "message": "at least two students are required"},
        )
    reviews_per_student = min(DEFAULT_PEER_REVIEWS_PER_STUDENT, len(rows) - 1)
    conn.execute("DELETE FROM peer_review_tasks WHERE assignment_id = ?;", (assignment_id,))
    tasks = []
    for index, row in enumerate(rows):
        for offset in range(1, reviews_per_student + 1):
            target = rows[(index + offset) % len(rows)]
            conn.execute(
                """
                INSERT INTO peer_review_tasks (
                    assignment_id, reviewer_student_id, submission_id, created_at
                )
                VALUES (?, ?, ?, ?);
                """,
                (assignment_id, row["student_id"], target["submission_id"], now_str()),
            )
            tasks.append(
                {
                    "assignment_id": assignment_id,
                    "reviewer_student_id": row["student_id"],
                    "submission_id": target["submission_id"],
                }
            )
    conn.commit()
    conn.close()
    return {
        "code": 200,
        "message": "peer review tasks assigned",
        "payload": {
            "assignment_id": assignment_id,
            "student_count": len(rows),
            "reviews_per_student": reviews_per_student,
            "tasks": tasks,
        },
    }


@app.get("/v1/peer-review/tasks/my")
def list_my_peer_review_tasks(
    assignment_id: str | None = None,
    student_id: str = "",
    auth: AuthContext | None = Depends(require_student),
):
    auth = resolved_auth(auth)
    effective_student_id = auth.display_id if auth is not None else student_id.strip()
    if not effective_student_id:
        raise HTTPException(
            status_code=400,
            detail={"code": 400, "message": "student_id is required"},
        )
    where = ["prt.reviewer_student_id = ?"]
    params: list[object] = [effective_student_id]
    if assignment_id:
        where.append("prt.assignment_id = ?")
        params.append(assignment_id.strip())
    conn = get_conn()
    rows = conn.execute(
        f"""
        SELECT
            prt.assignment_id,
            prt.reviewer_student_id,
            prt.submission_id,
            s.student_id AS target_student_id,
            a.title AS assignment_title
        FROM peer_review_tasks prt
        JOIN submissions s ON s.submission_id = prt.submission_id
        LEFT JOIN assignments a ON a.assignment_id = prt.assignment_id
        WHERE {" AND ".join(where)}
        ORDER BY prt.assignment_id ASC, prt.submission_id ASC;
        """,
        params,
    ).fetchall()
    conn.close()
    return {
        "code": 200,
        "message": "peer review tasks returned",
        "payload": {"tasks": [dict(row) for row in rows]},
    }


class PeerReviewPayload(BaseModel):
    reviewer_student_id: str
    submission_id: int
    score: int
    comment: str = ""


class PeerReviewRequest(BaseModel):
    action: str
    timestamp: int
    payload: PeerReviewPayload


@app.post("/v1/peer-reviews")
def submit_peer_review(
    req: PeerReviewRequest,
    auth: AuthContext | None = Depends(require_student),
):
    """
    A -> B：学生提交互评分。

    规则：
    1. 只有开启互评的作业允许学生评分；
    2. 学生不能给自己的提交评分；
    3. 同一个学生对同一个 submission_id 只能保留一条评分，重复提交会覆盖旧评分；
    4. score 必须在 0 到 100 之间。
    """
    if req.action != "SUBMIT_PEER_REVIEW":
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "action must be SUBMIT_PEER_REVIEW",
            },
        )

    p = req.payload
    auth = resolved_auth(auth)
    reviewer_student_id = auth.display_id if auth is not None else p.reviewer_student_id

    if p.score < 0 or p.score > 100:
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "score must be between 0 and 100",
            },
        )

    conn = get_conn()

    submission = conn.execute(
        """
        SELECT submission_id, assignment_id, student_id
        FROM submissions
        WHERE submission_id = ?;
        """,
        (p.submission_id,),
    ).fetchone()

    if submission is None:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "submission_id does not exist",
            },
        )

    assignment_id = submission["assignment_id"]
    owner_student_id = submission["student_id"]

    if reviewer_student_id == owner_student_id:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "student cannot review own submission",
            },
        )

    assignment = conn.execute(
        """
        SELECT assignment_id, peer_review_enabled, peer_review_stage
        FROM assignments
        WHERE assignment_id = ?;
        """,
        (assignment_id,),
    ).fetchone()

    if assignment is None or assignment["peer_review_enabled"] != 1:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "peer review is not enabled for this assignment",
            },
        )

    if assignment["peer_review_stage"] not in {"peer_review", "final_calculation"}:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "peer review stage is not open",
            },
        )

    task_count = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM peer_review_tasks
        WHERE assignment_id = ?;
        """,
        (assignment_id,),
    ).fetchone()["count"]
    if task_count:
        task = conn.execute(
            """
            SELECT task_id
            FROM peer_review_tasks
            WHERE assignment_id = ?
              AND reviewer_student_id = ?
              AND submission_id = ?;
            """,
            (assignment_id, reviewer_student_id, p.submission_id),
        ).fetchone()
        if task is None:
            conn.close()
            raise HTTPException(
                status_code=403,
                detail={
                    "code": 403,
                    "message": "submission is not assigned to this reviewer",
                },
            )

    old_review = conn.execute(
        """
        SELECT review_id
        FROM peer_reviews
        WHERE submission_id = ?
          AND reviewer_student_id = ?;
        """,
        (p.submission_id, reviewer_student_id),
    ).fetchone()

    if old_review is None:
        conn.execute(
            """
            INSERT INTO peer_reviews (
                assignment_id,
                submission_id,
                reviewer_student_id,
                score,
                comment,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (
                assignment_id,
                p.submission_id,
                reviewer_student_id,
                p.score,
                p.comment,
                now_str(),
            ),
        )
    else:
        conn.execute(
            """
            UPDATE peer_reviews
            SET score = ?,
                comment = ?,
                created_at = ?
            WHERE submission_id = ?
              AND reviewer_student_id = ?;
            """,
            (
                p.score,
                p.comment,
                now_str(),
                p.submission_id,
                reviewer_student_id,
            ),
        )

    conn.commit()
    conn.close()

    return {
        "code": 200,
        "message": "peer review submitted",
        "payload": {
            "assignment_id": assignment_id,
            "submission_id": p.submission_id,
            "reviewer_student_id": reviewer_student_id,
            "score": p.score,
        },
    }


def calc_peer_bonus(diff: float, cfg) -> float:
    """
    学生互评分与老师分接近时，给该评分者本次作业最多 +1。
    """
    if diff <= cfg["bonus_threshold_1"]:
        return 1.0
    return 0.0


def recalculate_assignment_scores(assignment_id: str):
    """
    重新计算某个作业的最终成绩。

    计算逻辑：
    1. 对每个 submission 计算 peer_avg_score；
    2. 基础成绩 = 老师分 * teacher_weight + 互评平均分 * peer_weight；
    3. 如果没有互评平均分，则基础成绩 = 老师分；
    4. 根据互评分与老师分的接近程度，给评分者自己的提交增加 peer_bonus；
    5. final_score = min(100, 基础成绩 + peer_bonus)。
    """
    conn = get_conn()

    cfg = conn.execute(
        """
        SELECT *
        FROM assignments
        WHERE assignment_id = ?;
        """,
        (assignment_id,),
    ).fetchone()

    if cfg is None:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "assignment_id does not exist",
            },
        )

    teacher_weight = float(cfg["teacher_weight"])
    peer_weight = float(cfg["peer_weight"])
    assignment_weight = float(cfg["assignment_weight"])
    total_weight = teacher_weight + peer_weight

    if total_weight <= 0:
        teacher_weight = 0.7
        peer_weight = 0.3
        total_weight = 1.0

    teacher_weight = teacher_weight / total_weight
    peer_weight = peer_weight / total_weight

    submissions = conn.execute(
        """
        SELECT submission_id, student_id, assignment_id, score, status
        FROM submissions
        WHERE assignment_id = ?
          AND score IS NOT NULL;
        """,
        (assignment_id,),
    ).fetchall()

    base_score_by_submission = {}
    peer_avg_by_submission = {}

    for sub in submissions:
        submission_id = sub["submission_id"]
        teacher_score = float(sub["score"])

        avg_row = conn.execute(
            """
            SELECT AVG(score) AS peer_avg
            FROM peer_reviews
            WHERE submission_id = ?;
            """,
            (submission_id,),
        ).fetchone()

        peer_avg = avg_row["peer_avg"]

        if peer_avg is None:
            base_score = teacher_score
            peer_avg_by_submission[submission_id] = None
        else:
            peer_avg = float(peer_avg)
            base_score = teacher_score * teacher_weight + peer_avg * peer_weight
            peer_avg_by_submission[submission_id] = round(peer_avg, 2)

        base_score_by_submission[submission_id] = round(base_score, 2)

    bonus_by_student = {}

    reviews = conn.execute(
        """
        SELECT
            pr.reviewer_student_id,
            pr.score AS peer_score,
            s.score AS teacher_score
        FROM peer_reviews pr
        JOIN submissions s ON pr.submission_id = s.submission_id
        WHERE pr.assignment_id = ?
          AND s.score IS NOT NULL;
        """,
        (assignment_id,),
    ).fetchall()

    for review in reviews:
        reviewer_student_id = review["reviewer_student_id"]
        peer_score = float(review["peer_score"])
        teacher_score = float(review["teacher_score"])
        diff = abs(peer_score - teacher_score)
        bonus = calc_peer_bonus(diff, cfg)
        bonus_by_student[reviewer_student_id] = max(
            bonus_by_student.get(reviewer_student_id, 0.0),
            bonus,
        )

    for sub in submissions:
        submission_id = sub["submission_id"]
        student_id = sub["student_id"]

        base_score = base_score_by_submission[submission_id]
        peer_avg = peer_avg_by_submission[submission_id]
        peer_bonus = round(bonus_by_student.get(student_id, 0.0), 2)
        final_score = min(100.0, base_score + peer_bonus)

        conn.execute(
            """
            UPDATE submissions
            SET peer_avg_score = ?,
                peer_bonus = ?,
                final_score = ?
            WHERE submission_id = ?;
            """,
            (
                peer_avg,
                peer_bonus,
                round(final_score, 2),
                submission_id,
            ),
        )

    conn.commit()

    rows = conn.execute(
        """
        SELECT
            submission_id,
            student_id,
            assignment_id,
            score AS teacher_score,
            peer_avg_score,
            peer_bonus,
            final_score,
            ? AS assignment_weight,
            ROUND(final_score * ?, 2) AS weighted_score,
            status
        FROM submissions
        WHERE assignment_id = ?
          AND score IS NOT NULL
        ORDER BY student_id ASC;
        """,
        (assignment_weight, assignment_weight, assignment_id),
    ).fetchall()

    conn.close()

    return [dict(row) for row in rows]


@app.post("/v1/assignments/{assignment_id}/calculate-final-scores")
def calculate_final_scores(
    assignment_id: str,
    auth: AuthContext | None = Depends(require_teacher),
):
    """
    B 内部 / C 端触发：计算某个作业最终成绩。
    """
    results = recalculate_assignment_scores(assignment_id)

    return {
        "code": 200,
        "message": "final scores calculated",
        "payload": {
            "assignment_id": assignment_id,
            "results": results,
        },
    }


@app.get("/v1/assignments/{assignment_id}/final-scores")
def list_final_scores(
    assignment_id: str,
    auth: AuthContext | None = Depends(require_teacher),
):
    """
    C / 老师端查看某个作业的最终成绩。
    """
    conn = get_conn()

    rows = conn.execute(
        """
        SELECT
            s.submission_id,
            s.student_id,
            s.assignment_id,
            s.score AS teacher_score,
            s.peer_avg_score,
            s.peer_bonus,
            s.final_score,
            COALESCE(a.assignment_weight, 1.0) AS assignment_weight,
            ROUND(s.final_score * COALESCE(a.assignment_weight, 1.0), 2) AS weighted_score,
            s.status
        FROM submissions s
        LEFT JOIN assignments a ON a.assignment_id = s.assignment_id
        WHERE s.assignment_id = ?
          AND s.score IS NOT NULL
        ORDER BY s.student_id ASC;
        """,
        (assignment_id,),
    ).fetchall()

    conn.close()

    return {
        "code": 200,
        "message": "final scores returned",
        "payload": {
            "assignment_id": assignment_id,
            "results": [dict(row) for row in rows],
        },
    }


@app.get("/v1/assignments/{assignment_id}/plagiarism")
def list_assignment_plagiarism(
    assignment_id: str,
    auth: AuthContext | None = Depends(require_teacher),
):
    """
    Teacher-facing plagiarism report for one assignment.
    Reports are created automatically when submissions are accepted.
    """
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT
            report_id,
            submission_id,
            assignment_id,
            student_id,
            plagiarism_rate,
            matched_submission_id,
            matched_student_id,
            matched_assignment_id,
            scope,
            checked_at
        FROM plagiarism_reports
        WHERE assignment_id = ?
        ORDER BY plagiarism_rate DESC, checked_at DESC;
        """,
        (assignment_id,),
    ).fetchall()
    conn.close()

    return {
        "code": 200,
        "message": "plagiarism reports returned",
        "payload": {
            "assignment_id": assignment_id,
            "reports": [dict(row) for row in rows],
        },
    }


@app.get("/v1/submissions/{submission_id}/plagiarism")
def get_submission_plagiarism(
    submission_id: int,
    auth: AuthContext | None = Depends(require_teacher),
):
    """
    Teacher-facing plagiarism report for one submission.
    """
    conn = get_conn()
    row = conn.execute(
        """
        SELECT
            report_id,
            submission_id,
            assignment_id,
            student_id,
            plagiarism_rate,
            matched_submission_id,
            matched_student_id,
            matched_assignment_id,
            scope,
            checked_at
        FROM plagiarism_reports
        WHERE submission_id = ?;
        """,
        (submission_id,),
    ).fetchone()
    conn.close()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": 404,
                "message": "plagiarism report does not exist",
            },
        )

    return {
        "code": 200,
        "message": "plagiarism report returned",
        "payload": dict(row),
    }


@app.get("/v1/assignments/{assignment_id}/score-stats")
def get_assignment_score_stats(
    assignment_id: str,
    auth: AuthContext | None = Depends(require_teacher),
):
    """
    Teacher-facing score statistics for one assignment.
    Uses final_score when available, otherwise teacher score.
    """
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT
            s.submission_id,
            s.student_id,
            s.assignment_id,
            s.score AS teacher_score,
            s.peer_avg_score,
            s.peer_bonus,
            s.final_score,
            COALESCE(s.final_score, s.score) AS effective_score,
            COALESCE(a.assignment_weight, 1.0) AS assignment_weight,
            ROUND(COALESCE(s.final_score, s.score) * COALESCE(a.assignment_weight, 1.0), 2) AS weighted_score,
            s.status,
            s.submit_time
        FROM submissions s
        LEFT JOIN assignments a ON a.assignment_id = s.assignment_id
        WHERE s.assignment_id = ?
          AND s.score IS NOT NULL
        ORDER BY s.student_id ASC, s.submit_time ASC;
        """,
        (assignment_id,),
    ).fetchall()
    conn.close()

    score_values = [float(row["effective_score"]) for row in rows if row["effective_score"] is not None]
    if score_values:
        summary = {
            "count": len(score_values),
            "average": round(sum(score_values) / len(score_values), 2),
            "min": min(score_values),
            "max": max(score_values),
            "median": round(float(median(score_values)), 2),
            "distribution": score_distribution(score_values),
        }
    else:
        summary = {
            "count": 0,
            "average": None,
            "min": None,
            "max": None,
            "median": None,
            "distribution": score_distribution([]),
        }

    return {
        "code": 200,
        "message": "score statistics returned",
        "payload": {
            "assignment_id": assignment_id,
            "summary": summary,
            "scores": [dict(row) for row in rows],
        },
    }


@app.get("/v1/students/{student_id}/score-history")
def get_student_score_history(
    student_id: str,
    auth: AuthContext | None = Depends(get_auth_context),
):
    """
    Return one student's historical scores.
    Students can only query themselves when auth is enabled; teachers can query anyone.
    """
    auth = resolved_auth(auth)
    effective_student_id = student_id
    if AUTH_REQUIRED and auth is not None and auth.role == ROLE_STUDENT:
        if auth.display_id != student_id:
            raise create_auth_error("student can only query own score history", 403)
        effective_student_id = auth.display_id

    conn = get_conn()
    rows = conn.execute(
        """
        SELECT
            s.submission_id,
            s.student_id,
            s.assignment_id,
            a.title AS assignment_title,
            s.submit_time,
            s.status,
            s.score AS teacher_score,
            s.peer_avg_score,
            s.peer_bonus,
            s.final_score,
            COALESCE(s.final_score, s.score) AS effective_score,
            COALESCE(a.assignment_weight, 1.0) AS assignment_weight,
            ROUND(COALESCE(s.final_score, s.score) * COALESCE(a.assignment_weight, 1.0), 2) AS weighted_score
        FROM submissions s
        LEFT JOIN assignments a ON s.assignment_id = a.assignment_id
        WHERE s.student_id = ?
          AND s.score IS NOT NULL
        ORDER BY s.submit_time ASC;
        """,
        (effective_student_id,),
    ).fetchall()
    conn.close()

    score_values = [float(row["effective_score"]) for row in rows if row["effective_score"] is not None]
    summary = {
        "count": len(score_values),
        "average": round(sum(score_values) / len(score_values), 2) if score_values else None,
        "best": max(score_values) if score_values else None,
        "latest": score_values[-1] if score_values else None,
    }

    return {
        "code": 200,
        "message": "student score history returned",
        "payload": {
            "student_id": effective_student_id,
            "summary": summary,
            "scores": [dict(row) for row in rows],
        },
    }


class ArchivePayload(BaseModel):
    archive_name: Optional[str] = None
    note: str = ""
    include_db: bool = True
    include_submissions: bool = True
    include_feedback: bool = True
    include_docs: bool = True


class ArchiveRequest(BaseModel):
    action: str
    timestamp: int
    payload: ArchivePayload


ARCHIVE_ALLOWED_EXTENSIONS = {
    ".py",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".java",
    ".js",
    ".html",
    ".css",
    ".md",
    ".txt",
    ".pdf",
    ".docx",
    ".xlsx",
    ".pptx",
    ".ipynb",
    ".png",
    ".jpg",
    ".jpeg",
}
ARCHIVE_EXCLUDED_DIRS = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
}
ARCHIVE_EXCLUDED_NAMES = {".DS_Store", "Thumbs.db"}
ARCHIVE_EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".log",
    ".tmp",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".rar",
}


def sanitize_archive_component(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()).strip("_") or "item"


def should_skip_archive_member(member_path: PurePosixPath) -> bool:
    parts = member_path.parts
    if member_path.is_absolute() or ".." in parts:
        return True
    if any(part in ARCHIVE_EXCLUDED_DIRS for part in parts[:-1]):
        return True

    file_name = parts[-1] if parts else ""
    if file_name in ARCHIVE_EXCLUDED_NAMES:
        return True

    suffix = Path(file_name).suffix.lower()
    if suffix in ARCHIVE_EXCLUDED_SUFFIXES:
        return True
    if suffix not in ARCHIVE_ALLOWED_EXTENSIONS:
        return True
    return False


def dedup_archive_name(file_name: str, used_names: set[str]) -> str:
    if file_name not in used_names:
        used_names.add(file_name)
        return file_name

    stem = Path(file_name).stem
    suffix = Path(file_name).suffix
    index = 2
    while True:
        candidate = f"{stem}_{index}{suffix}"
        if candidate not in used_names:
            used_names.add(candidate)
            return candidate
        index += 1


def iter_submission_archive_files(archive_path: Path):
    try:
        with tarfile.open(archive_path, "r:*") as tar:
            for member in tar.getmembers():
                if not member.isfile():
                    continue
                extracted = tar.extractfile(member)
                if extracted is None:
                    continue
                yield PurePosixPath(member.name), extracted.read()
        return
    except tarfile.TarError:
        pass

    try:
        with zipfile.ZipFile(archive_path, "r") as zf:
            for member in zf.infolist():
                if member.is_dir():
                    continue
                member_path = PurePosixPath(member.filename)
                yield member_path, zf.read(member)
    except zipfile.BadZipFile:
        return


def export_submission_files_to_zip(zipf, assignment_root: str) -> int:
    conn = get_conn()
    submissions = conn.execute(
        """
        SELECT submission_id, student_id, assignment_id, file_path
        FROM submissions
        ORDER BY submit_time ASC, submission_id ASC;
        """
    ).fetchall()
    conn.close()

    exported_count = 0
    used_names: set[str] = set()
    for row in submissions:
        submission_id = int(row["submission_id"])
        student_id = sanitize_archive_component(str(row["student_id"]))
        assignment_id = sanitize_archive_component(str(row["assignment_id"]))
        archive_path = Path(str(row["file_path"]))
        if not archive_path.exists():
            continue

        for member_path, data in iter_submission_archive_files(archive_path):
            if should_skip_archive_member(member_path):
                continue
            safe_original_name = sanitize_archive_component(member_path.name)
            prefixed_name = (
                f"{assignment_id}_{student_id}_{submission_id}_{safe_original_name}"
            )
            final_name = dedup_archive_name(prefixed_name, used_names)
            zipf.writestr(f"{assignment_root}/{final_name}", data)
            exported_count += 1

    return exported_count


def get_archive_assignment_root() -> str:
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT DISTINCT assignment_id
        FROM submissions
        ORDER BY assignment_id ASC;
        """
    ).fetchall()
    conn.close()
    assignment_ids = [sanitize_archive_component(str(row["assignment_id"])) for row in rows]
    if len(assignment_ids) == 1:
        return f"assignment_{assignment_ids[0]}_homework_files"
    return "assignment_all_homework_files"


def build_assignment_score_rows() -> list[dict[str, object]]:
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT
            s.submission_id,
            s.student_id,
            s.assignment_id,
            a.title AS assignment_title,
            COALESCE(a.assignment_weight, 1.0) AS assignment_weight,
            s.score AS teacher_score,
            s.peer_avg_score,
            s.peer_bonus,
            s.final_score,
            COALESCE(s.final_score, s.score) AS effective_score,
            ROUND(COALESCE(s.final_score, s.score) * COALESCE(a.assignment_weight, 1.0), 2) AS weighted_points,
            s.status,
            s.submit_time
        FROM submissions s
        LEFT JOIN assignments a ON a.assignment_id = s.assignment_id
        WHERE s.score IS NOT NULL
        ORDER BY s.student_id ASC, s.assignment_id ASC, s.submit_time ASC;
        """
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def build_course_score_rows() -> list[dict[str, object]]:
    by_student: dict[str, dict[str, object]] = {}
    for row in build_assignment_score_rows():
        student_id = str(row["student_id"])
        effective_score = float(row["effective_score"])
        assignment_weight = float(row["assignment_weight"])
        weighted_points = effective_score * assignment_weight
        entry = by_student.setdefault(
            student_id,
            {
                "student_id": student_id,
                "assignment_count": 0,
                "total_weight": 0.0,
                "weighted_points": 0.0,
                "course_score": None,
            },
        )
        entry["assignment_count"] = int(entry["assignment_count"]) + 1
        entry["total_weight"] = float(entry["total_weight"]) + assignment_weight
        entry["weighted_points"] = float(entry["weighted_points"]) + weighted_points

    for entry in by_student.values():
        total_weight = float(entry["total_weight"])
        weighted_points = float(entry["weighted_points"])
        entry["total_weight"] = round(total_weight, 4)
        entry["weighted_points"] = round(weighted_points, 2)
        entry["course_score"] = round(weighted_points / total_weight, 2) if total_weight > 0 else None
    return sorted(by_student.values(), key=lambda item: str(item["student_id"]))


def write_score_csvs_to_archive(zipf) -> None:
    assignment_rows = build_assignment_score_rows()
    assignment_buffer = io.StringIO()
    assignment_fields = [
        "submission_id",
        "student_id",
        "assignment_id",
        "assignment_title",
        "assignment_weight",
        "teacher_score",
        "peer_avg_score",
        "peer_bonus",
        "final_score",
        "effective_score",
        "weighted_points",
        "status",
        "submit_time",
    ]
    writer = csv.DictWriter(assignment_buffer, fieldnames=assignment_fields)
    writer.writeheader()
    writer.writerows(assignment_rows)
    zipf.writestr("scores/assignment_scores.csv", assignment_buffer.getvalue())

    course_rows = build_course_score_rows()
    course_buffer = io.StringIO()
    course_fields = [
        "student_id",
        "assignment_count",
        "total_weight",
        "weighted_points",
        "course_score",
    ]
    writer = csv.DictWriter(course_buffer, fieldnames=course_fields)
    writer.writeheader()
    writer.writerows(course_rows)
    zipf.writestr("scores/course_final_scores.csv", course_buffer.getvalue())


def backup_sqlite_db(target_path: Path):
    """
    使用 sqlite backup 方式复制数据库，比直接 cp 更稳。
    """
    source_conn = sqlite3.connect(DB_PATH)
    target_conn = sqlite3.connect(target_path)
    source_conn.backup(target_conn)
    target_conn.close()
    source_conn.close()


@app.post("/v1/archives/course")
def create_course_archive(
    req: ArchiveRequest,
    auth: AuthContext | None = Depends(require_teacher),
):
    """
    课程结束后生成归档 zip 文件。

    归档内容可包含：
    1. SQLite 数据库备份；
    2. 学生提交文件 data/submissions；
    3. 反馈 Markdown data/feedback；
    4. docs/api_spec.md 等文档。
    """
    if req.action != "CREATE_COURSE_ARCHIVE":
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "action must be CREATE_COURSE_ARCHIVE",
            },
        )

    p = req.payload

    if p.archive_name:
        archive_base = safe_name(p.archive_name)
    else:
        archive_base = f"course_archive_{int(time.time())}"

    if archive_base.endswith(".zip"):
        archive_name = archive_base
    else:
        archive_name = f"{archive_base}.zip"

    archive_path = ARCHIVE_DIR / archive_name

    if archive_path.exists():
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "archive_name already exists",
            },
        )

    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        assignment_root = get_archive_assignment_root()
        if p.include_submissions:
            export_submission_files_to_zip(zipf, assignment_root)
        write_score_csvs_to_archive(zipf)

    conn = get_conn()
    conn.execute(
        """
        INSERT INTO archives (
            archive_name,
            archive_path,
            created_at,
            note
        )
        VALUES (?, ?, ?, ?);
        """,
        (
            archive_name,
            str(archive_path),
            now_str(),
            p.note,
        ),
    )
    conn.commit()
    conn.close()

    return {
        "code": 200,
        "message": "course archive created",
        "payload": {
            "archive_name": archive_name,
            "archive_path": str(archive_path),
            "download_url": f"/v1/archives/download/{archive_name}",
        },
    }


@app.get("/v1/archives")
def list_archives(
    auth: AuthContext | None = Depends(require_teacher),
):
    """
    查看已经生成过的课程归档包。
    """
    conn = get_conn()

    rows = conn.execute(
        """
        SELECT archive_id, archive_name, archive_path, created_at, note
        FROM archives
        ORDER BY created_at DESC;
        """
    ).fetchall()

    conn.close()

    return {
        "code": 200,
        "message": "archives returned",
        "payload": {
            "archives": [dict(row) for row in rows],
        },
    }


@app.get("/v1/archives/download/{archive_name}")
def download_archive(
    archive_name: str,
    auth: AuthContext | None = Depends(require_teacher),
):
    """
    下载课程归档 zip 文件。
    """
    archive_name = safe_name(archive_name)
    archive_path = ARCHIVE_DIR / archive_name

    if not archive_path.exists():
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "archive does not exist",
            },
        )

    return FileResponse(
        path=str(archive_path),
        filename=archive_name,
        media_type="application/zip",
    )

# =========================
# Phase 6: Plagiarism Check
# =========================

import re
import tarfile
from itertools import combinations


PLAGIARISM_REPORT_DIR = DATA_DIR / "plagiarism_reports"
PLAGIARISM_REPORT_DIR.mkdir(parents=True, exist_ok=True)


def init_plagiarism_db():
    conn = get_conn()

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS plagiarism_check_reports (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id TEXT NOT NULL,
            method TEXT NOT NULL,
            threshold REAL NOT NULL,
            created_at TEXT NOT NULL,
            report_path TEXT NOT NULL,
            report_json TEXT NOT NULL
        );
        """
    )

    conn.commit()
    conn.close()


@app.on_event("startup")
def startup_plagiarism_features():
    init_plagiarism_db()


TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".c", ".cpp", ".h", ".hpp",
    ".java", ".js", ".ts", ".html", ".css", ".sh",
    ".json", ".xml", ".yml", ".yaml"
}


def normalize_text_for_plagiarism(text: str) -> list[str]:
    """
    查重用的文本规范化。

    重点：
    1. 不把数字当作有效查重内容；
    2. 不把下划线当作有效查重内容；
    3. 只保留中文、英文单词；
    4. 过滤长度太短的 token，减少误判。
    """
    text = text.lower()

    # 只提取中文和英文字母，数字、下划线、标点都会被丢掉
    tokens = re.findall(r"[a-zA-Z\u4e00-\u9fff]+", text)

    # 过滤太短的 token
    tokens = [t for t in tokens if len(t) >= 2]

    return tokens


def token_similarity(tokens_a: list[str], tokens_b: list[str]) -> float:
    """
    用 token 集合相似度计算重复程度。

    这里不用原始文本逐字比较，因此数字和下划线不会直接导致重复。
    """
    set_a = set(tokens_a)
    set_b = set(tokens_b)

    if not set_a or not set_b:
        return 0.0

    intersection = set_a & set_b

    # 这里用较小集合覆盖率，更容易发现“一个作业大量抄另一个”的情况
    score = len(intersection) / min(len(set_a), len(set_b))

    return round(score, 4)


def read_text_from_submission_package(file_path: str) -> str:
    """
    从学生提交的压缩包里读取可比较文本。

    支持 tar.gz 包。
    只读取常见文本/代码文件，忽略二进制文件。
    """
    path = Path(file_path)

    if not path.exists():
        return ""

    texts = []

    try:
        if tarfile.is_tarfile(path):
            with tarfile.open(path, "r:*") as tar:
                for member in tar.getmembers():
                    if not member.isfile():
                        continue

                    suffix = Path(member.name).suffix.lower()

                    if suffix not in TEXT_EXTENSIONS:
                        continue

                    f = tar.extractfile(member)
                    if f is None:
                        continue

                    raw = f.read(1024 * 1024)
                    text = raw.decode("utf-8", errors="ignore")
                    texts.append(text)
        else:
            raw = path.read_bytes()[:1024 * 1024]
            texts.append(raw.decode("utf-8", errors="ignore"))

    except Exception as e:
        texts.append(f"[READ_ERROR] {e}")

    return "\n".join(texts)


class PlagiarismCheckPayload(BaseModel):
    assignment_id: str
    threshold: float = 0.75
    method: str = "token"
    ai_prefilter: float | None = None
    ai_limit: int | None = None


class PlagiarismCheckRequest(BaseModel):
    action: str
    timestamp: int
    payload: PlagiarismCheckPayload


PLAGIARISM_METHODS = {"token", "hybrid", "ai"}


def clamp_similarity(value: object) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    return round(max(0.0, min(numeric, 1.0)), 4)


def trim_text_for_ai(text: str) -> str:
    normalized = text.strip()
    if len(normalized) <= DEEPSEEK_MAX_CHARS_PER_SUBMISSION:
        return normalized

    half = max(DEEPSEEK_MAX_CHARS_PER_SUBMISSION // 2, 1000)
    return (
        normalized[:half]
        + "\n\n[... middle content truncated for AI plagiarism review ...]\n\n"
        + normalized[-half:]
    )


def parse_model_json(content: str) -> dict:
    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return {}
        try:
            parsed = json.loads(content[start : end + 1])
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}


def call_deepseek_plagiarism_judge(
    *,
    assignment_id: str,
    pair: dict[str, object],
) -> dict[str, object]:
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")

    body = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a rigorous university programming assignment plagiarism reviewer. "
                    "Compare two submissions for copied algorithmic structure, code organization, "
                    "distinctive mistakes, comments, and naming patterns. Ignore common boilerplate, "
                    "standard imports, assignment-provided template code, trivial I/O wrappers, and "
                    "coincidental short snippets. Return JSON only with keys: ai_similarity "
                    "(number 0..1), likely_plagiarism (boolean), confidence (number 0..1), "
                    "reason (short Chinese sentence), evidence (array of up to 3 short Chinese strings)."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "assignment_id": assignment_id,
                        "scope": pair.get("scope"),
                        "local_similarity": pair.get("local_similarity"),
                        "student_a": pair.get("student_a"),
                        "submission_a": pair.get("submission_a"),
                        "assignment_a": pair.get("assignment_a"),
                        "student_b": pair.get("student_b"),
                        "submission_b": pair.get("submission_b"),
                        "assignment_b": pair.get("assignment_b"),
                        "content_a": pair.get("text_a", ""),
                        "content_b": pair.get("text_b", ""),
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "temperature": 0,
        "max_tokens": 700,
        "response_format": {"type": "json_object"},
        "stream": False,
    }
    if DEEPSEEK_MODEL.startswith("deepseek-v4"):
        body["thinking"] = {"type": "disabled"}
    request = urllib.request.Request(
        f"{DEEPSEEK_BASE_URL}/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=DEEPSEEK_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")[:300]
        raise RuntimeError(f"DeepSeek API error {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"DeepSeek API request failed: {exc.reason}") from exc

    try:
        payload = json.loads(raw)
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("DeepSeek API returned an unexpected response") from exc

    verdict = parse_model_json(str(content))
    ai_similarity = clamp_similarity(verdict.get("ai_similarity", verdict.get("similarity", 0)))
    confidence = clamp_similarity(verdict.get("confidence", 0))
    evidence = verdict.get("evidence", [])
    if not isinstance(evidence, list):
        evidence = []

    return {
        "ai_similarity": ai_similarity,
        "likely_plagiarism": bool(verdict.get("likely_plagiarism", ai_similarity >= 0.75)),
        "confidence": confidence,
        "reason": str(verdict.get("reason", "")).strip(),
        "evidence": [str(item).strip() for item in evidence[:3] if str(item).strip()],
    }


def format_ai_grading_report(report: dict[str, object]) -> str:
    strengths = report.get("strengths") or []
    concerns = report.get("concerns") or []
    suggestions = report.get("suggestions") or []
    lines = [
        str(report.get("summary") or "No summary available."),
        "",
        "Strengths:",
    ]
    lines.extend(f"- {item}" for item in strengths if str(item).strip())
    lines.append("")
    lines.append("Concerns:")
    lines.extend(f"- {item}" for item in concerns if str(item).strip())
    lines.append("")
    lines.append("Suggestions:")
    lines.extend(f"- {item}" for item in suggestions if str(item).strip())
    rationale = str(report.get("score_rationale") or "").strip()
    if rationale:
        lines.extend(["", f"Score rationale: {rationale}"])
    error = str(report.get("ai_error") or "").strip()
    if error:
        lines.extend(["", f"AI unavailable: {error}"])
    return "\n".join(lines).strip()


def local_ai_grading_report(row, excerpt: str) -> dict[str, object]:
    score = row["score"]
    status = row["status"]
    summary = (
        "Local grading report generated from submission metadata and teacher feedback."
        if score is not None
        else "Local preliminary report generated from submission metadata."
    )
    strengths = []
    concerns = []
    suggestions = []
    if excerpt.strip():
        strengths.append("Submission package contains readable text/code content.")
    else:
        concerns.append("No readable text/code content was extracted from the submission package.")
    if score is not None:
        if int(score) >= 90:
            strengths.append("Teacher score indicates excellent completion.")
        elif int(score) >= 70:
            strengths.append("Teacher score indicates the core requirements were mostly met.")
        else:
            concerns.append("Teacher score indicates the work needs substantial revision.")
    if row["comment"]:
        suggestions.append("Review the teacher comment and address the highlighted issues.")
    else:
        suggestions.append("Add concrete teacher feedback during grading for a stronger report.")
    report = {
        "summary": summary,
        "strengths": strengths,
        "concerns": concerns,
        "suggestions": suggestions,
        "score_rationale": f"Current status is {status}; teacher score is {score}.",
    }
    report["report_text"] = format_ai_grading_report(report)
    return report


def call_deepseek_grading_report(row, excerpt: str) -> dict[str, object]:
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")

    body = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a rigorous university assignment grading assistant. "
                    "Review the submitted content and teacher feedback. Return JSON only with keys: "
                    "summary (short Chinese sentence), strengths (array of up to 3 short Chinese strings), "
                    "concerns (array of up to 3 short Chinese strings), suggestions (array of up to 3 short Chinese strings), "
                    "score_rationale (short Chinese sentence). Do not invent files that are not in the excerpt."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "submission_id": row["submission_id"],
                        "student_id": row["student_id"],
                        "assignment_id": row["assignment_id"],
                        "assignment_title": row["assignment_title"],
                        "assignment_description": row["assignment_description"],
                        "teacher_score": row["score"],
                        "teacher_comment": row["comment"],
                        "status": row["status"],
                        "submission_excerpt": excerpt,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "temperature": 0.1,
        "max_tokens": 900,
        "response_format": {"type": "json_object"},
        "stream": False,
    }
    if DEEPSEEK_MODEL.startswith("deepseek-v4"):
        body["thinking"] = {"type": "disabled"}
    request = urllib.request.Request(
        f"{DEEPSEEK_BASE_URL}/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=DEEPSEEK_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")[:300]
        raise RuntimeError(f"DeepSeek API error {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"DeepSeek API request failed: {exc.reason}") from exc

    try:
        payload = json.loads(raw)
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("DeepSeek API returned an unexpected response") from exc

    parsed = parse_model_json(str(content))
    report = {
        "summary": str(parsed.get("summary", "")).strip(),
        "strengths": [str(item).strip() for item in parsed.get("strengths", [])[:3] if str(item).strip()]
        if isinstance(parsed.get("strengths", []), list) else [],
        "concerns": [str(item).strip() for item in parsed.get("concerns", [])[:3] if str(item).strip()]
        if isinstance(parsed.get("concerns", []), list) else [],
        "suggestions": [str(item).strip() for item in parsed.get("suggestions", [])[:3] if str(item).strip()]
        if isinstance(parsed.get("suggestions", []), list) else [],
        "score_rationale": str(parsed.get("score_rationale", "")).strip(),
    }
    report["report_text"] = format_ai_grading_report(report)
    return report


@app.get("/v1/submissions/{submission_id}/ai-grade-report")
def get_submission_ai_grade_report(
    submission_id: int,
    auth: AuthContext | None = Depends(require_teacher),
):
    auth = resolved_auth(auth)
    conn = get_conn()
    row = conn.execute(
        """
        SELECT
            s.submission_id,
            s.student_id,
            s.assignment_id,
            s.file_name,
            s.file_path,
            s.status,
            s.score,
            s.comment,
            a.title AS assignment_title,
            a.description AS assignment_description,
            a.created_by,
            c.teacher_id AS class_teacher_id
        FROM submissions s
        LEFT JOIN assignments a ON a.assignment_id = s.assignment_id
        LEFT JOIN classes c ON c.class_id = a.class_id
        WHERE s.submission_id = ?;
        """,
        (submission_id,),
    ).fetchone()

    if row is None:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail={
                "code": 404,
                "message": "submission_id does not exist",
            },
        )
    if auth is not None and row["created_by"] != auth.display_id and row["class_teacher_id"] != auth.display_id:
        conn.close()
        raise create_auth_error("teacher can only view own class submissions", 403)

    cached = None
    if table_exists(conn, "ai_grading_reports"):
        cached = conn.execute(
            """
            SELECT *
            FROM ai_grading_reports
            WHERE submission_id = ?;
            """,
            (submission_id,),
        ).fetchone()
    if cached is not None:
        conn.close()
        report = json.loads(cached["report_json"])
        return {
            "code": 200,
            "message": "ai grading report returned",
            "payload": {
                **dict(cached),
                "report": report,
            },
        }

    excerpt = trim_text_for_ai(read_text_from_submission_package(row["file_path"]))
    generated_at = now_str()
    source = "deepseek" if DEEPSEEK_API_KEY else "local"
    model = DEEPSEEK_MODEL if DEEPSEEK_API_KEY else "local-summary"
    try:
        report = call_deepseek_grading_report(row, excerpt) if DEEPSEEK_API_KEY else local_ai_grading_report(row, excerpt)
    except Exception as exc:
        source = "local"
        model = "local-summary"
        report = local_ai_grading_report(row, excerpt)
        report["ai_error"] = str(exc)
        report["report_text"] = format_ai_grading_report(report)
    report["submission_excerpt"] = excerpt[:2000]

    if table_exists(conn, "ai_grading_reports"):
        conn.execute(
            """
            INSERT INTO ai_grading_reports (
                submission_id, assignment_id, student_id, model, source, generated_at, report_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(submission_id) DO UPDATE SET
                assignment_id = excluded.assignment_id,
                student_id = excluded.student_id,
                model = excluded.model,
                source = excluded.source,
                generated_at = excluded.generated_at,
                report_json = excluded.report_json;
            """,
            (
                submission_id,
                row["assignment_id"],
                row["student_id"],
                model,
                source,
                generated_at,
                json.dumps(report, ensure_ascii=False),
            ),
        )
        conn.commit()
    conn.close()

    return {
        "code": 200,
        "message": "ai grading report returned",
        "payload": {
            "submission_id": submission_id,
            "assignment_id": row["assignment_id"],
            "student_id": row["student_id"],
            "model": model,
            "source": source,
            "generated_at": generated_at,
            "report": report,
        },
    }


@app.post("/v1/plagiarism/check")
def check_plagiarism(
    req: PlagiarismCheckRequest,
    auth: AuthContext | None = Depends(require_teacher),
):
    """
    C -> B：触发某个作业的查重。

    当前实现：
    - method = token
    - 会过滤数字和下划线
    - 不再直接逐字比较原始文本

    如果后续要接大模型，可以在 method = llm 时扩展。
    """
    if req.action != "CHECK_PLAGIARISM":
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "action must be CHECK_PLAGIARISM",
            },
        )

    p = req.payload
    method = p.method.strip().lower()

    if method not in PLAGIARISM_METHODS:
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "method must be token, hybrid, or ai",
            },
        )

    if p.threshold <= 0 or p.threshold > 1:
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "threshold must be in (0, 1]",
            },
        )

    if method in {"hybrid", "ai"} and not deepseek_configured():
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "DEEPSEEK_API_KEY is required for AI plagiarism check",
            },
        )

    ai_prefilter = (
        DEEPSEEK_PREFILTER_SIMILARITY
        if p.ai_prefilter is None
        else max(0.0, min(float(p.ai_prefilter), 1.0))
    )
    ai_limit = (
        max(DEEPSEEK_MAX_CANDIDATE_PAIRS, 0)
        if p.ai_limit is None
        else max(int(p.ai_limit), 0)
    )

    conn = get_conn()

    target_rows = conn.execute(
        """
        SELECT
            submission_id,
            student_id,
            assignment_id,
            file_name,
            file_path,
            submit_time,
            status
        FROM submissions
        WHERE assignment_id = ?
        ORDER BY submission_id ASC;
        """,
        (p.assignment_id,),
    ).fetchall()

    historical_rows = []
    if target_rows:
        historical_rows = conn.execute(
            """
            SELECT
                submission_id,
                student_id,
                assignment_id,
                file_name,
                file_path,
                submit_time,
                status
            FROM submissions
            WHERE assignment_id != ?
              AND submit_time >= ?
            ORDER BY submit_time DESC, submission_id ASC;
            """,
            (p.assignment_id, plagiarism_cutoff_time()),
        ).fetchall()

    def row_to_doc(row, *, is_target: bool) -> dict[str, object]:
        item = dict(row)
        text = read_text_from_submission_package(item["file_path"])
        tokens = normalize_text_for_plagiarism(text)
        return {
            "submission_id": item["submission_id"],
            "student_id": item["student_id"],
            "assignment_id": item["assignment_id"],
            "file_name": item["file_name"],
            "file_path": item["file_path"],
            "submit_time": item["submit_time"],
            "is_target": is_target,
            "token_count": len(tokens),
            "tokens": tokens,
            "text_excerpt": trim_text_for_ai(text),
        }

    target_docs = [row_to_doc(row, is_target=True) for row in target_rows]
    historical_docs = [row_to_doc(row, is_target=False) for row in historical_rows]
    docs = target_docs + historical_docs

    suspected_pairs = []
    pair_candidates = []

    for a, b in combinations(docs, 2):
        if not a["is_target"] and not b["is_target"]:
            continue
        # 同一个学生自己的多次提交不做互相查重
        if a["student_id"] == b["student_id"]:
            continue

        score = token_similarity(a["tokens"], b["tokens"])
        scope = (
            "current_assignment"
            if a["is_target"] and b["is_target"]
            else "last_three_years"
        )
        pair = {
            "student_a": a["student_id"],
            "submission_a": a["submission_id"],
            "assignment_a": a["assignment_id"],
            "file_a": a["file_name"],
            "student_b": b["student_id"],
            "submission_b": b["submission_id"],
            "assignment_b": b["assignment_id"],
            "file_b": b["file_name"],
            "scope": scope,
            "local_similarity": score,
            "text_a": a["text_excerpt"],
            "text_b": b["text_excerpt"],
        }
        pair_candidates.append(pair)

        if method == "token" and score >= p.threshold:
            suspected_pairs.append(
                {
                    "student_a": pair["student_a"],
                    "submission_a": pair["submission_a"],
                    "assignment_a": pair["assignment_a"],
                    "file_a": pair["file_a"],
                    "student_b": pair["student_b"],
                    "submission_b": pair["submission_b"],
                    "assignment_b": pair["assignment_b"],
                    "file_b": pair["file_b"],
                    "scope": pair["scope"],
                    "similarity": score,
                    "local_similarity": score,
                    "threshold": p.threshold,
                    "reason": "token similarity exceeds threshold",
                }
            )

    ai_reviewed_count = 0
    ai_error_count = 0
    if method in {"hybrid", "ai"}:
        ai_candidates = [
            pair
            for pair in sorted(
                pair_candidates,
                key=lambda item: float(item["local_similarity"]),
                reverse=True,
            )
            if float(pair["local_similarity"]) >= ai_prefilter
        ][:ai_limit]

        for pair in ai_candidates:
            try:
                verdict = call_deepseek_plagiarism_judge(
                    assignment_id=p.assignment_id,
                    pair=pair,
                )
                ai_reviewed_count += 1
            except RuntimeError as exc:
                ai_error_count += 1
                pair["ai_error"] = str(exc)
                continue

            ai_similarity = float(verdict["ai_similarity"])
            likely = bool(verdict["likely_plagiarism"])
            if likely or ai_similarity >= p.threshold:
                suspected_pairs.append(
                    {
                        "student_a": pair["student_a"],
                        "submission_a": pair["submission_a"],
                        "assignment_a": pair["assignment_a"],
                        "file_a": pair["file_a"],
                        "student_b": pair["student_b"],
                        "submission_b": pair["submission_b"],
                        "assignment_b": pair["assignment_b"],
                        "file_b": pair["file_b"],
                        "scope": pair["scope"],
                        "similarity": ai_similarity,
                        "local_similarity": pair["local_similarity"],
                        "ai_similarity": ai_similarity,
                        "ai_confidence": verdict["confidence"],
                        "threshold": p.threshold,
                        "reason": verdict["reason"] or "AI plagiarism review flagged this pair",
                        "evidence": verdict["evidence"],
                    }
                )

    report = {
        "assignment_id": p.assignment_id,
        "method": method,
        "threshold": p.threshold,
        "created_at": now_str(),
        "note": (
            "digits and underscores are ignored during tokenization; "
            "current assignment submissions are compared with each other and with "
            "submissions from the last three years; AI methods first prefilter by "
            "local token similarity for efficiency"
        ),
        "scope": "current_assignment_and_last_three_years",
        "submission_count": len(target_rows),
        "historical_submission_count": len(historical_rows),
        "compared_document_count": len(docs),
        "candidate_pair_count": len(pair_candidates),
        "ai_enabled": method in {"hybrid", "ai"},
        "ai_model": DEEPSEEK_MODEL if method in {"hybrid", "ai"} else None,
        "ai_prefilter": ai_prefilter if method in {"hybrid", "ai"} else None,
        "ai_limit": ai_limit if method in {"hybrid", "ai"} else None,
        "ai_reviewed_count": ai_reviewed_count,
        "ai_error_count": ai_error_count,
        "suspected_pair_count": len(suspected_pairs),
        "suspected_pairs": suspected_pairs,
    }

    report_name = f"plagiarism_{p.assignment_id}_{int(time.time())}.json"
    report_path = PLAGIARISM_REPORT_DIR / report_name

    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    conn.execute(
        """
        INSERT INTO plagiarism_check_reports (
            assignment_id,
            method,
            threshold,
            created_at,
            report_path,
            report_json
        )
        VALUES (?, ?, ?, ?, ?, ?);
        """,
        (
            p.assignment_id,
            method,
            p.threshold,
            now_str(),
            str(report_path),
            json.dumps(report, ensure_ascii=False),
        ),
    )

    conn.commit()
    conn.close()

    return {
        "code": 200,
        "message": "plagiarism check finished",
        "payload": report,
    }


@app.get("/v1/plagiarism/reports/{assignment_id}")
def list_plagiarism_reports(
    assignment_id: str,
    auth: AuthContext | None = Depends(require_teacher),
):
    """
    C / A -> B：查看某个作业的查重报告历史。
    """
    conn = get_conn()

    rows = conn.execute(
        """
        SELECT
            report_id,
            assignment_id,
            method,
            threshold,
            created_at,
            report_path,
            report_json
        FROM plagiarism_check_reports
        WHERE assignment_id = ?
        ORDER BY created_at DESC;
        """,
        (assignment_id,),
    ).fetchall()

    conn.close()

    reports = []

    for row in rows:
        item = dict(row)
        try:
            item["report"] = json.loads(item["report_json"])
        except Exception:
            item["report"] = {}
        item.pop("report_json", None)
        reports.append(item)

    return {
        "code": 200,
        "message": "plagiarism reports returned",
        "payload": {
            "assignment_id": assignment_id,
            "reports": reports,
        },
    }
