from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil
import sqlite3
import time
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from pydantic import BaseModel


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
DB_DIR = DATA_DIR / "db"
TMP_DIR = DATA_DIR / "tmp"
SUBMISSIONS_DIR = DATA_DIR / "submissions"
FEEDBACK_DIR = DATA_DIR / "feedback"
DB_PATH = DB_DIR / "engine.db"

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
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open'
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

    conn.commit()
    conn.close()


class AssignmentPayload(BaseModel):
    teacher_id: str
    assignment_id: str
    title: str
    description: str = ""
    deadline: str = ""


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


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
def health():
    return {
        "code": 200,
        "message": "module_b_server is running",
        "db_path": str(DB_PATH),
        "time": now_str(),
    }


@app.post("/v1/assignments")
def create_assignment(req: AssignmentRequest):
    if req.action != "CREATE_ASSIGNMENT":
        raise HTTPException(
            status_code=400,
            detail={
                "code": 400,
                "message": "action must be CREATE_ASSIGNMENT",
            },
        )

    p = req.payload

    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO assignments (
                assignment_id, title, description, deadline,
                created_by, created_at, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                p.assignment_id,
                p.title,
                p.description,
                p.deadline,
                p.teacher_id,
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
            "status": "open",
        },
    }


@app.get("/v1/assignments/open")
def list_open_assignments():
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT assignment_id, title, description, deadline, created_by, created_at, status
        FROM assignments
        WHERE status = 'open'
        ORDER BY created_at DESC;
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
    upload_file_name = safe_name(file.filename or p.file_name or "submission.tar.gz")

    conn = get_conn()
    assignment = conn.execute(
        """
        SELECT assignment_id, status
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

    timestamp = int(time.time())
    tmp_file = TMP_DIR / f"{timestamp}_{p.student_id}_{p.assignment_id}_{upload_file_name}"

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

    student_dir = SUBMISSIONS_DIR / p.student_id / p.assignment_id
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
            p.student_id,
            p.assignment_id,
            upload_file_name,
            str(final_file),
            actual_md5,
            now_str(),
            "pending",
        ),
    )
    conn.commit()
    submission_id = cur.lastrowid
    conn.close()

    return {
        "code": 200,
        "message": "submission accepted",
        "payload": {
            "submission_id": submission_id,
            "student_id": p.student_id,
            "assignment_id": p.assignment_id,
            "file_name": upload_file_name,
            "md5": actual_md5,
            "status": "pending",
            "archive_path": str(final_file),
        },
    }


@app.get("/v1/submissions/pending")
def list_pending_submissions():
    """
    B -> C 待批改列表接口。
    C 端后面就调用这个接口，渲染老师/助教的 TUI 列表。
    """
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT
            submission_id,
            student_id,
            assignment_id,
            file_name,
            file_path,
            md5,
            submit_time,
            status
        FROM submissions
        WHERE status = 'pending'
        ORDER BY submit_time ASC;
        """
    ).fetchall()
    conn.close()

    return {
        "code": 200,
        "message": "pending submissions returned",
        "payload": {
            "submissions": [dict(row) for row in rows]
        },
    }
