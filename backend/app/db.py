import sqlite3
from contextlib import contextmanager

from .settings import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS model_config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    base_url TEXT NOT NULL DEFAULT '',
    model_name TEXT NOT NULL DEFAULT '',
    api_key TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS workspace (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    name TEXT NOT NULL DEFAULT '我的简历工作区',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS experience_library (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    original_filename TEXT NOT NULL DEFAULT '',
    content_text TEXT NOT NULL DEFAULT '',
    source_format TEXT NOT NULL DEFAULT 'text',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS resume_preferences (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    page_limit TEXT NOT NULL DEFAULT 'one',
    structure_mode TEXT NOT NULL DEFAULT 'reorder',
    layout_mode TEXT NOT NULL DEFAULT 'adaptive',
    date_order TEXT NOT NULL DEFAULT 'desc',
    profile_text TEXT NOT NULL DEFAULT '',
    calibrated INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS master_resume (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    original_filename TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    file_type TEXT NOT NULL,
    parsed_json TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS job_session (
    id TEXT PRIMARY KEY,
    jd_text TEXT NOT NULL,
    messages_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS template (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    config_json TEXT NOT NULL DEFAULT '{"font_size": 10.5, "line_height": 1.55, "margin_top": 14, "margin_right": 16, "margin_bottom": 14, "margin_left": 16}',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS resume_version (
    id TEXT PRIMARY KEY,
    job_session_id TEXT NOT NULL,
    content_json TEXT NOT NULL,
    html TEXT NOT NULL DEFAULT '',
    pdf_path TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(job_session_id) REFERENCES job_session(id)
);
"""

@contextmanager
def connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db() -> None:
    with connection() as conn:
        conn.executescript(SCHEMA)
        _ensure_column(conn, "resume_preferences", "date_order", "TEXT NOT NULL DEFAULT 'desc'")
        _ensure_column(conn, "job_session", "company", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "job_session", "role", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "job_session", "display_name", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "job_session", "analysis_json", "TEXT NOT NULL DEFAULT '{}'")
        _ensure_column(conn, "resume_version", "display_name", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "resume_version", "initial_content_json", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "resume_version", "previous_content_json", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "resume_version", "updated_at", "TEXT NOT NULL DEFAULT ''")
        conn.execute("INSERT OR IGNORE INTO workspace (id) VALUES (1)")
        conn.execute("INSERT OR IGNORE INTO model_config (id) VALUES (1)")
        conn.execute("INSERT OR IGNORE INTO template (id) VALUES (1)")
        conn.execute("INSERT OR IGNORE INTO experience_library (id) VALUES (1)")
        conn.execute("INSERT OR IGNORE INTO resume_preferences (id) VALUES (1)")
