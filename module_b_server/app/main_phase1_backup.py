from pathlib import Path
from datetime import datetime
import sqlite3
import time

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
DB_DIR = DATA_DIR / "db"
DB_PATH = DB_DIR / "engine.db"

DB_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Module B - Assignment Engine")


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


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
