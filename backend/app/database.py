import os
import re
import secrets
import sqlite3

from flask import g, current_app
from app.config import Config


# ---- 白名单正则：只允许字母数字下划线，防止 table/column 注入 ----
_VALID_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

_RACES_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS races (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        slug TEXT,
        status TEXT NOT NULL DEFAULT 'draft'
            CHECK (status IN (
                'draft', 'published', 'registration', 'running',
                'submitting', 'judging', 'completed', 'archived'
            )),
        description TEXT,
        rules TEXT,
        schedule TEXT,
        visibility TEXT DEFAULT 'private',
        created_by_user_id INTEGER REFERENCES users(id),
        theme TEXT DEFAULT '',
        organizer_name TEXT DEFAULT '',
        start_time TEXT,
        end_time TEXT,
        submission_deadline TEXT,
        judging_deadline TEXT,
        judging_mode TEXT NOT NULL DEFAULT 'blind'
            CHECK (judging_mode IN ('blind', 'open')),
        judging_tiebreaker TEXT NOT NULL DEFAULT 'avg'
            CHECK (judging_tiebreaker IN ('avg', 'median', 'trimmed_mean')),
        ca_policy TEXT NOT NULL DEFAULT 'rider_choice'
            CHECK (ca_policy IN ('organizer_specified', 'rider_choice')),
        ca_policy_config TEXT DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
"""


def _validate_identifier(name: str, context: str) -> None:
    if not _VALID_IDENTIFIER.match(name):
        raise ValueError(f"Invalid identifier '{name}' in {context}")


# ---- 数据库连接 ----

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


# ---- 安全补列（白名单校验版） ----

def _add_column_if_missing(cursor, table: str, column: str, col_def: str):
    """安全补列——table 和 column 经白名单校验后才拼接"""
    _validate_identifier(table, "ALTER TABLE")
    _validate_identifier(column, "ADD COLUMN")
    cursor.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cursor.fetchall()}
    if column not in existing:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")


def _migrate_legacy_races(cursor) -> None:
    row = cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='races'"
    ).fetchone()
    if row is None or "'upcoming'" not in row[0]:
        return

    cursor.execute("PRAGMA legacy_alter_table=ON")
    cursor.execute("ALTER TABLE races RENAME TO races_legacy")
    cursor.execute(_RACES_TABLE_SQL)

    legacy_columns = {
        item["name"] for item in cursor.execute("PRAGMA table_info(races_legacy)")
    }
    target_columns = [
        item["name"] for item in cursor.execute("PRAGMA table_info(races)")
        if item["name"] in legacy_columns
    ]
    for column in target_columns:
        _validate_identifier(column, "race migration")
    select_parts = []
    for column in target_columns:
        if column == "status":
            select_parts.append(
                "CASE status "
                "WHEN 'upcoming' THEN 'draft' "
                "WHEN 'open' THEN 'registration' "
                "WHEN 'ended' THEN 'completed' "
                "ELSE status END"
            )
        else:
            select_parts.append(column)
    cursor.execute(
        f"""INSERT INTO races ({', '.join(target_columns)})
            SELECT {', '.join(select_parts)} FROM races_legacy"""
    )
    cursor.execute("DROP TABLE races_legacy")
    cursor.execute("PRAGMA legacy_alter_table=OFF")


# ---- 数据库初始化 ----

def init_db(app=None):
    db_path = Config.DATABASE_PATH if app is None else app.config.get("DATABASE_PATH", Config.DATABASE_PATH)
    db_path = os.path.abspath(db_path)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # Schema migrations may rebuild parent tables. Re-enable FK checks after
    # the migration transaction commits.
    conn.execute("PRAGMA foreign_keys=OFF")

    cursor = conn.cursor()

    # =============================================
    # 旧表（保留兼容）
    # =============================================
    cursor.execute(_RACES_TABLE_SQL)
    _migrate_legacy_races(cursor)

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

    # users 补充新字段
    _add_column_if_missing(cursor, "users", "roles", "TEXT NOT NULL DEFAULT '[\"rider\"]'")
    _add_column_if_missing(cursor, "users", "github_user_id", "TEXT")
    _add_column_if_missing(cursor, "users", "github_login", "TEXT")
    _add_column_if_missing(cursor, "users", "profile_completed", "INTEGER DEFAULT 0")
    _add_column_if_missing(cursor, "users", "display_name", "TEXT DEFAULT ''")
    _add_column_if_missing(cursor, "users", "school_org", "TEXT DEFAULT ''")
    _add_column_if_missing(cursor, "users", "bio", "TEXT DEFAULT ''")

    # races 补充 organizer 关系
    _add_column_if_missing(cursor, "races", "created_by_user_id", "INTEGER REFERENCES users(id)")
    _add_column_if_missing(cursor, "races", "theme", "TEXT DEFAULT ''")
    _add_column_if_missing(cursor, "races", "organizer_name", "TEXT DEFAULT ''")
    _add_column_if_missing(cursor, "races", "start_time", "TEXT")
    _add_column_if_missing(cursor, "races", "end_time", "TEXT")
    _add_column_if_missing(cursor, "races", "submission_deadline", "TEXT")
    _add_column_if_missing(cursor, "races", "judging_deadline", "TEXT")
    _add_column_if_missing(
        cursor,
        "races",
        "judging_mode",
        "TEXT NOT NULL DEFAULT 'blind' CHECK (judging_mode IN ('blind', 'open'))",
    )
    _add_column_if_missing(
        cursor,
        "races",
        "judging_tiebreaker",
        "TEXT NOT NULL DEFAULT 'avg' CHECK (judging_tiebreaker IN ('avg', 'median', 'trimmed_mean'))",
    )
    _add_column_if_missing(
        cursor,
        "races",
        "ca_policy",
        "TEXT NOT NULL DEFAULT 'rider_choice' CHECK (ca_policy IN ('organizer_specified', 'rider_choice'))",
    )
    _add_column_if_missing(cursor, "races", "ca_policy_config", "TEXT DEFAULT '{}'")

    # registrations
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

    # race_projects
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS race_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            registration_id INTEGER NOT NULL UNIQUE REFERENCES registrations(id),
            aggregate_ingestion_status TEXT NOT NULL DEFAULT 'not_configured',
            connection_health TEXT NOT NULL DEFAULT 'no_signal',
            primary_work_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # works: B freezes this table first so C can build judging and exports.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS works (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            race_project_id INTEGER NOT NULL REFERENCES race_projects(id),
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            repo_url TEXT DEFAULT '',
            demo_url TEXT DEFAULT '',
            video_url TEXT DEFAULT '',
            cover_image_url TEXT DEFAULT '',
            screenshot_urls TEXT DEFAULT '[]',
            readme_body TEXT DEFAULT '',
            work_status TEXT NOT NULL DEFAULT 'draft'
                CHECK (work_status IN ('draft', 'submitted')),
            visibility TEXT NOT NULL DEFAULT 'private'
                CHECK (visibility IN ('private', 'public')),
            content_hash TEXT DEFAULT '',
            content_commitment TEXT DEFAULT '',
            prev_hash TEXT,
            version INTEGER NOT NULL DEFAULT 1,
            submitted_at TEXT,
            disqualified INTEGER NOT NULL DEFAULT 0
                CHECK (disqualified IN (0, 1)),
            disqualify_reason TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # Rider-facing content is immutable once judging starts. Moderation fields
    # remain writable so C can disqualify or restore a submitted work.
    cursor.execute("DROP TRIGGER IF EXISTS trg_works_sealed")
    cursor.execute("""
        CREATE TRIGGER trg_works_sealed
        BEFORE UPDATE ON works
        WHEN (
            SELECT r.status FROM race_projects rp
            JOIN registrations reg ON rp.registration_id = reg.id
            JOIN races r ON reg.race_id = r.id
            WHERE rp.id = NEW.race_project_id
        ) IN ('judging', 'completed', 'archived')
        AND (
            OLD.race_project_id IS NOT NEW.race_project_id OR
            OLD.title IS NOT NEW.title OR
            OLD.description IS NOT NEW.description OR
            OLD.repo_url IS NOT NEW.repo_url OR
            OLD.demo_url IS NOT NEW.demo_url OR
            OLD.video_url IS NOT NEW.video_url OR
            OLD.cover_image_url IS NOT NEW.cover_image_url OR
            OLD.screenshot_urls IS NOT NEW.screenshot_urls OR
            OLD.readme_body IS NOT NEW.readme_body OR
            OLD.work_status IS NOT NEW.work_status OR
            OLD.visibility IS NOT NEW.visibility OR
            OLD.content_hash IS NOT NEW.content_hash OR
            OLD.content_commitment IS NOT NEW.content_commitment OR
            OLD.prev_hash IS NOT NEW.prev_hash OR
            OLD.version IS NOT NEW.version OR
            OLD.submitted_at IS NOT NEW.submitted_at
        )
        BEGIN
            SELECT RAISE(ABORT, 'works are sealed once judging begins');
        END
    """)

    cursor.execute("DROP TRIGGER IF EXISTS trg_works_sealed_delete")
    cursor.execute("""
        CREATE TRIGGER trg_works_sealed_delete
        BEFORE DELETE ON works
        WHEN (
            SELECT r.status FROM race_projects rp
            JOIN registrations reg ON rp.registration_id = reg.id
            JOIN races r ON reg.race_id = r.id
            WHERE rp.id = OLD.race_project_id
        ) IN ('judging', 'completed', 'archived')
        BEGIN
            SELECT RAISE(ABORT, 'works are sealed once judging begins');
        END
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            race_id INTEGER NOT NULL REFERENCES races(id),
            title TEXT NOT NULL,
            body TEXT DEFAULT '',
            visibility TEXT NOT NULL DEFAULT 'draft'
                CHECK (visibility IN ('draft', 'private', 'public')),
            created_by_user_id INTEGER NOT NULL REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # =============================================
    # 新增：integrity_log（append-only 不可变）
    # =============================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS integrity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id INTEGER NOT NULL,
            actor_user_id INTEGER NOT NULL,
            content_hash TEXT NOT NULL,
            prev_hash TEXT,
            commitment TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_integrity_log_immutable
        BEFORE UPDATE ON integrity_log
        BEGIN
            SELECT RAISE(ABORT, 'integrity_log is append-only');
        END
    """)

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_integrity_log_no_delete
        BEFORE DELETE ON integrity_log
        BEGIN
            SELECT RAISE(ABORT, 'integrity_log records cannot be deleted');
        END
    """)

    # =============================================
    # 新增：audit_logs（append-only 不可变）
    # =============================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            actor_user_id INTEGER NOT NULL,
            target_type TEXT NOT NULL,
            target_id INTEGER,
            detail TEXT DEFAULT '',
            request_id TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_audit_logs_immutable
        BEFORE UPDATE ON audit_logs
        BEGIN
            SELECT RAISE(ABORT, 'audit_logs is append-only');
        END
    """)

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_audit_logs_no_delete
        BEFORE DELETE ON audit_logs
        BEGIN
            SELECT RAISE(ABORT, 'audit_logs records cannot be deleted');
        END
    """)

    # =============================================
    # 新增：token_blacklist（logout 持久化）
    # =============================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS token_blacklist (
            jti TEXT PRIMARY KEY,
            expires_at TEXT NOT NULL
        )
    """)

    # =============================================
    # 新增：login_rate_limit（限流持久化）
    # =============================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS login_rate_limit (
            key TEXT PRIMARY KEY,
            key_type TEXT NOT NULL CHECK(key_type IN ('ip', 'account')),
            failure_count INTEGER NOT NULL DEFAULT 0,
            locked_until TEXT,
            window_start TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # =============================================
    # 新增：notifications（系统内通知）
    # =============================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient_user_id INTEGER NOT NULL REFERENCES users(id),
            title TEXT NOT NULL,
            body TEXT DEFAULT '',
            link TEXT DEFAULT '',
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.execute("PRAGMA foreign_keys=ON")

    # ---- 种子用户（随机密码，打印到控制台） ----
    seed_default_users(conn)

    conn.close()


# ---- 种子用户（启动时随机生成密码） ----

def seed_default_users(conn):
    """不检查是否已有用户——每次 init_db 都确保三账号存在；密码首次随机生成并打印。"""
    from app.utils.auth import hash_password

    defaults = [
        ("rider", ["rider"]),
        ("organizer", ["organizer"]),
        ("admin", ["admin", "organizer"]),
    ]

    import json as _json

    for username, roles in defaults:
        existing = conn.execute(
            "SELECT id, password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()

        if existing:
            # 已有用户：保留已设密码，只确保 roles 字段是最新的
            conn.execute(
                "UPDATE users SET roles = ? WHERE username = ? AND (roles IS NULL OR roles = '')",
                (_json.dumps(roles), username),
            )
        else:
            # 生成满足复杂度要求的随机密码：大写+小写+数字+特殊字符
            import string
            alphabet = string.ascii_letters + string.digits
            password = (
                secrets.choice(string.ascii_uppercase)
                + secrets.choice(string.ascii_lowercase)
                + secrets.choice(string.digits)
                + ''.join(secrets.choice(alphabet) for _ in range(9))
            )
            pw_hash = hash_password(password)
            conn.execute(
                "INSERT INTO users (username, password_hash, roles) VALUES (?, ?, ?)",
                (username, pw_hash, _json.dumps(roles)),
            )
            print(f"[ARY] Created user '{username}' with password: {password}")

    conn.commit()


# =============================================
# 测试用 reset
# =============================================

def reset_db(app=None):
    """仅测试用：关闭所有连接后删除并重建数据库"""
    from flask import g as flask_g
    db_path = Config.DATABASE_PATH if app is None else app.config.get("DATABASE_PATH", Config.DATABASE_PATH)
    db_path = os.path.abspath(db_path)
    # 关闭 Flask g 中的连接
    if app:
        with app.app_context():
            db = flask_g.pop("db", None)
            if db is not None:
                db.close()
    if os.path.exists(db_path):
        os.remove(db_path)
    init_db(app)
