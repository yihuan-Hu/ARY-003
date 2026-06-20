import sqlite3
import os
from flask import g, current_app
from app.config import Config


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        db_path = current_app.config.get("DATABASE_PATH", Config.DATABASE_PATH)
        db_path = os.path.abspath(db_path)
        conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        g.db = conn
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app=None):
    """初始化数据库：建表 + migration"""
    db_path = Config.DATABASE_PATH if app is None else app.config.get("DATABASE_PATH", Config.DATABASE_PATH)
    db_path = os.path.abspath(db_path)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")

    cursor = conn.cursor()

    # =============================================
    # 旧表（保留兼容，不修改结构）
    # =============================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS races (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            slug TEXT,
            status TEXT NOT NULL DEFAULT 'upcoming'
                CHECK (status IN ('upcoming', 'open', 'judging', 'ended')),
            description TEXT,
            rules TEXT,
            schedule TEXT,
            visibility TEXT DEFAULT 'private',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS riders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            student_name TEXT,
            race_id INTEGER REFERENCES races(id),
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS racing_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            race_id INTEGER NOT NULL REFERENCES races(id),
            rider_id INTEGER REFERENCES riders(id),
            student_name TEXT,
            round_progress REAL DEFAULT 0,
            risk_level TEXT,
            ca_provider TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS track_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            race_id INTEGER REFERENCES races(id),
            profile_data TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_api_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            race_id INTEGER REFERENCES races(id),
            entry_id INTEGER REFERENCES racing_entries(id),
            rider_id INTEGER REFERENCES riders(id),
            provider TEXT,
            tokens_used INTEGER DEFAULT 0,
            cost REAL DEFAULT 0,
            latency_ms INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            race_id INTEGER NOT NULL REFERENCES races(id),
            student_name TEXT NOT NULL,
            content_hash TEXT,
            message TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (race_id, student_name)
        )
    """)

    # =============================================
    # 新表（ARY MVP Checkpoint 1）
    # =============================================

    # 为 users 表补充新字段（如果旧表缺列）
    _add_column_if_missing(cursor, "users", "roles", "TEXT NOT NULL DEFAULT '[\"contestant\"]'")
    _add_column_if_missing(cursor, "users", "github_user_id", "TEXT")
    _add_column_if_missing(cursor, "users", "github_login", "TEXT")
    _add_column_if_missing(cursor, "users", "profile_completed", "INTEGER DEFAULT 0")

    # 为 races 表补充 created_by_user_id
    _add_column_if_missing(cursor, "races", "created_by_user_id", "INTEGER REFERENCES users(id)")

    # registrations 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            race_id INTEGER NOT NULL REFERENCES races(id),
            user_id INTEGER NOT NULL REFERENCES users(id),
            status TEXT NOT NULL DEFAULT 'submitted'
                CHECK (status IN ('submitted', 'approved', 'rejected', 'withdrawn')),
            submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
            reviewed_at TEXT,
            reviewed_by_user_id INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (race_id, user_id)
        )
    """)

    # race_projects 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS race_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            registration_id INTEGER NOT NULL UNIQUE REFERENCES registrations(id),
            aggregate_ingestion_status TEXT NOT NULL DEFAULT 'not_configured',
            connection_health TEXT NOT NULL DEFAULT 'no_signal',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()


def _add_column_if_missing(cursor, table, column, col_def):
    """安全补列：如果列不存在则 ALTER TABLE ADD COLUMN"""
    cursor.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cursor.fetchall()}
    if column not in existing:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")


def reset_db(app=None):
    """仅测试用：删除并重建数据库"""
    db_path = Config.DATABASE_PATH if app is None else app.config.get("DATABASE_PATH", Config.DATABASE_PATH)
    db_path = os.path.abspath(db_path)
    if os.path.exists(db_path):
        os.remove(db_path)
    init_db(app)
