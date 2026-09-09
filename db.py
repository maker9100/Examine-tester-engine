import sqlite3
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = Path(__file__).resolve().parent.parent / "study_ai.db"

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    stored_name TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    size INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'uploaded',
    title TEXT,
    subject TEXT,
    chapter TEXT,
    summary_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quizzes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    questions_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(material_id) REFERENCES materials(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quiz_id INTEGER NOT NULL,
    score_percent INTEGER NOT NULL,
    results_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mastery (
    concept TEXT PRIMARY KEY,
    score REAL NOT NULL DEFAULT 0.5,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_accuracy REAL NOT NULL DEFAULT 0.0,
    updated_at TEXT NOT NULL
);
"""

def now_iso():
    return datetime.now(timezone.utc).isoformat()

@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)
