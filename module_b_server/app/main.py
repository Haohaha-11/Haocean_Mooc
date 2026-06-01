from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
import difflib
import hashlib
import json
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
DATA_DIR = ROOT_DIR / "data"
DB_DIR = DATA_DIR / "db"
TMP_DIR = DATA_DIR / "tmp"
SUBMISSIONS_DIR = DATA_DIR / "submissions"
FEEDBACK_DIR = DATA_DIR / "feedback"
DB_PATH = DB_DIR / "engine.db"

SYSTEM_NAME = os.getenv("MODULE_B_SYSTEM_NAME", "HaoceanLab Course")
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

ROLE_STUDENT = "student"
ROLE_TEACHER = "teacher"

for d in [DB_DIR, TMP_DIR, SUBMISSIONS_DIR, FEEDBACK_DIR]:
    d.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Module B - Assignment Engine")


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


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
            client.login(SMTP_ACCOUNT, SMTP_TOKEN)
            client.send_message(message)
        return

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as client:
        client.starttls(context=ssl.create_default_context())
        client.login(SMTP_ACCOUNT, SMTP_TOKEN)
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
                created_by, class_id, created_at, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                p.assignment_id,
                p.title,
                p.description,
                p.deadline,
                teacher_id,
                class_id,
                now_str(),
                "open",
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


@app.get("/v1/submissions/pending")
def list_pending_submissions(
    auth: AuthContext | None = Depends(require_teacher),
):
    """
    B -> C 待批改列表接口。
    C 端后面就调用这个接口，渲染老师/助教的 TUI 列表。
    """
    auth = resolved_auth(auth)
    conn = get_conn()
    if auth is not None:
        rows = conn.execute(
            """
            SELECT
                s.submission_id,
                s.student_id,
                s.assignment_id,
                s.file_name,
                s.file_path,
                s.md5,
                s.submit_time,
                s.status,
                a.class_id,
                a.title AS assignment_title,
                c.class_name
            FROM submissions s
            JOIN assignments a ON a.assignment_id = s.assignment_id
            LEFT JOIN classes c ON c.class_id = a.class_id
            WHERE s.status = 'pending'
              AND (
                    a.created_by = ?
                    OR c.teacher_id = ?
              )
            ORDER BY s.submit_time ASC;
            """,
            (auth.display_id, auth.display_id),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT
                s.submission_id,
                s.student_id,
                s.assignment_id,
                s.file_name,
                s.file_path,
                s.md5,
                s.submit_time,
                s.status,
                a.class_id,
                a.title AS assignment_title,
                c.class_name
            FROM submissions s
            LEFT JOIN assignments a ON a.assignment_id = s.assignment_id
            LEFT JOIN classes c ON c.class_id = a.class_id
            WHERE s.status = 'pending'
            ORDER BY s.submit_time ASC;
            """
        ).fetchall()
    conn.close()
    submissions = []
    for row in rows:
        item = dict(row)
        item["download_url"] = f"/v1/submissions/{item['submission_id']}/download"
        submissions.append(item)

    return {
        "code": 200,
        "message": "pending submissions returned",
        "payload": {
            "submissions": submissions
        },
    }


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
        SELECT submission_id, student_id, assignment_id, file_name, status
        FROM submissions
        WHERE submission_id = ?;
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

    if row["status"] != "pending":
        conn.close()
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "submission is not pending",
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
            "status": p.status,
            "feedback_path": str(feedback_file),
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
        "peer_review_enabled",
        "peer_review_enabled INTEGER NOT NULL DEFAULT 0",
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
        "bonus_value_1 REAL NOT NULL DEFAULT 5",
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
        "bonus_value_2 REAL NOT NULL DEFAULT 3",
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
        "bonus_value_3 REAL NOT NULL DEFAULT 1",
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
    bonus_value_1: float = 5
    bonus_threshold_2: int = 10
    bonus_value_2: float = 3
    bonus_threshold_3: int = 15
    bonus_value_3: float = 1


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
            p.bonus_value_1,
            p.bonus_threshold_2,
            p.bonus_value_2,
            p.bonus_threshold_3,
            p.bonus_value_3,
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
            "teacher_weight": p.teacher_weight,
            "peer_weight": p.peer_weight,
        },
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
        SELECT assignment_id, peer_review_enabled
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
    根据学生互评分与老师评分的差距计算奖励分。
    """
    if diff <= cfg["bonus_threshold_1"]:
        return float(cfg["bonus_value_1"])
    if diff <= cfg["bonus_threshold_2"]:
        return float(cfg["bonus_value_2"])
    if diff <= cfg["bonus_threshold_3"]:
        return float(cfg["bonus_value_3"])
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
        bonus_by_student[reviewer_student_id] = bonus_by_student.get(reviewer_student_id, 0.0) + bonus

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
            status
        FROM submissions
        WHERE assignment_id = ?
          AND score IS NOT NULL
        ORDER BY student_id ASC;
        """,
        (assignment_id,),
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
            submission_id,
            student_id,
            assignment_id,
            score AS teacher_score,
            peer_avg_score,
            peer_bonus,
            final_score,
            status
        FROM submissions
        WHERE assignment_id = ?
          AND score IS NOT NULL
        ORDER BY student_id ASC;
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
            submission_id,
            student_id,
            assignment_id,
            score AS teacher_score,
            peer_avg_score,
            peer_bonus,
            final_score,
            COALESCE(final_score, score) AS effective_score,
            status,
            submit_time
        FROM submissions
        WHERE assignment_id = ?
          AND score IS NOT NULL
        ORDER BY student_id ASC, submit_time ASC;
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
            COALESCE(s.final_score, s.score) AS effective_score
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


def add_file_or_dir_to_zip(zipf, source_path: Path, arc_prefix: str):
    """
    把文件或目录加入 zip 包。
    arc_prefix 是压缩包内部的目录名。
    """
    if not source_path.exists():
        return

    if source_path.is_file():
        zipf.write(source_path, arcname=str(Path(arc_prefix) / source_path.name))
        return

    for p in source_path.rglob("*"):
        if p.is_file():
            zipf.write(p, arcname=str(Path(arc_prefix) / p.relative_to(source_path)))


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

    tmp_db_path = ARCHIVE_DIR / f"{archive_name}.engine.db.tmp"

    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        if p.include_db:
            backup_sqlite_db(tmp_db_path)
            zipf.write(tmp_db_path, arcname="database/engine.db")
            tmp_db_path.unlink(missing_ok=True)

        if p.include_submissions:
            add_file_or_dir_to_zip(zipf, SUBMISSIONS_DIR, "submissions")

        if p.include_feedback:
            add_file_or_dir_to_zip(zipf, FEEDBACK_DIR, "feedback")

        if p.include_docs:
            add_file_or_dir_to_zip(zipf, PROJECT_DIR / "docs", "docs")
            readme_path = ROOT_DIR / "README.md"
            if readme_path.exists():
                zipf.write(readme_path, arcname="README.md")

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
