import re
from .connection import get_db

# 白名单正则
_VALID_IDENTIFIER = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


def table_columns(conn, table):
    if not _VALID_IDENTIFIER.match(table):
        raise ValueError(f"Invalid table name: {table}")
    return {row['name'] for row in conn.execute(f'PRAGMA table_info({table})')}


def add_column_if_missing(conn, table, column, ddl):
    if not _VALID_IDENTIFIER.match(table):
        raise ValueError(f"Invalid table name: {table}")
    if not _VALID_IDENTIFIER.match(column):
        raise ValueError(f"Invalid column name: {column}")
    if column not in table_columns(conn, table):
        conn.execute(f'ALTER TABLE {table} ADD COLUMN {column} {ddl}')


def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS races (
            id            TEXT PRIMARY KEY,
            title         TEXT NOT NULL,
            description   TEXT NOT NULL,
            start_time    TEXT NOT NULL,
            end_time      TEXT NOT NULL,
            status        TEXT NOT NULL DEFAULT 'upcoming',
            theme         TEXT DEFAULT '',
            organizer     TEXT DEFAULT '',
            current_round INTEGER DEFAULT 1,
            current_phase TEXT DEFAULT 'DEV',
            created_at    TEXT NOT NULL,
            updated_at    TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS riders (
            id         TEXT PRIMARY KEY,
            name       TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS users (
            id            TEXT PRIMARY KEY,
            username      TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role          INTEGER NOT NULL DEFAULT 0,
            created_at    TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS racing_entries (
            id               TEXT PRIMARY KEY,
            race_id          TEXT NOT NULL,
            rider_id         TEXT NOT NULL,
            project_name     TEXT NOT NULL DEFAULT '',
            ca_provider      TEXT NOT NULL DEFAULT 'codex',
            overall_progress REAL DEFAULT 0.0,
            round_progress   REAL DEFAULT 0.0,
            phase_progress   REAL DEFAULT 0.0,
            current_phase    TEXT,
            cost_tokens      INTEGER DEFAULT 0,
            cost_usd         REAL DEFAULT 0.0,
            risk_level       TEXT DEFAULT 'none',
            obstacle_count   INTEGER DEFAULT 0,
            violation_count  INTEGER DEFAULT 0,
            lane_id          TEXT,
            status           TEXT DEFAULT 'idle',
            updated_at       TEXT NOT NULL,
            UNIQUE (race_id, rider_id),
            FOREIGN KEY (race_id) REFERENCES races(id),
            FOREIGN KEY (rider_id) REFERENCES riders(id)
        );

        CREATE TABLE IF NOT EXISTS track_profiles (
            id           TEXT PRIMARY KEY,
            race_id      TEXT UNIQUE,
            profile_json TEXT NOT NULL,
            created_at   TEXT NOT NULL,
            FOREIGN KEY (race_id) REFERENCES races(id)
        );

        CREATE TABLE IF NOT EXISTS agent_api_usage (
            id                TEXT PRIMARY KEY,
            race_id           TEXT NOT NULL,
            entry_id          TEXT DEFAULT NULL,
            rider_id          TEXT DEFAULT NULL,
            provider          TEXT NOT NULL,
            model             TEXT NOT NULL DEFAULT '',
            api_endpoint      TEXT NOT NULL DEFAULT '',
            prompt_tokens     INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            total_tokens      INTEGER DEFAULT 0,
            cost_usd          REAL DEFAULT 0.0,
            latency_ms        INTEGER DEFAULT 0,
            status_code       INTEGER DEFAULT 200,
            detected_at       TEXT NOT NULL,
            FOREIGN KEY (race_id) REFERENCES races(id),
            FOREIGN KEY (entry_id) REFERENCES racing_entries(id),
            FOREIGN KEY (rider_id) REFERENCES riders(id)
        );

        CREATE TABLE IF NOT EXISTS submissions (
            id           TEXT PRIMARY KEY,
            race_id      TEXT NOT NULL,
            rider_id     TEXT DEFAULT NULL,
            student_name TEXT NOT NULL,
            content      TEXT NOT NULL,
            content_hash TEXT DEFAULT '',
            content_commitment TEXT DEFAULT '',
            content_public_summary TEXT DEFAULT '[protected submission]',
            content_protection TEXT DEFAULT 'sealed_commitment_v1',
            msg_type     TEXT DEFAULT 'progress_update',
            severity     TEXT DEFAULT 'info',
            submitted_at TEXT NOT NULL,
            UNIQUE (race_id, student_name),
            FOREIGN KEY (race_id) REFERENCES races(id),
            FOREIGN KEY (rider_id) REFERENCES riders(id)
        );

        CREATE INDEX IF NOT EXISTS idx_entries_race ON racing_entries(race_id);
        CREATE INDEX IF NOT EXISTS idx_entries_rider ON racing_entries(rider_id);
        CREATE INDEX IF NOT EXISTS idx_agent_usage_race ON agent_api_usage(race_id);
        CREATE INDEX IF NOT EXISTS idx_agent_usage_entry ON agent_api_usage(entry_id);
        CREATE INDEX IF NOT EXISTS idx_agent_usage_provider ON agent_api_usage(provider);
        CREATE INDEX IF NOT EXISTS idx_subs_race ON submissions(race_id);
    ''')

    add_column_if_missing(conn, 'races', 'theme', "theme TEXT DEFAULT ''")
    add_column_if_missing(conn, 'races', 'organizer', "organizer TEXT DEFAULT ''")
    add_column_if_missing(conn, 'races', 'current_round', 'current_round INTEGER DEFAULT 1')
    add_column_if_missing(conn, 'races', 'current_phase', "current_phase TEXT DEFAULT 'DEV'")
    add_column_if_missing(conn, 'submissions', 'rider_id', 'rider_id TEXT DEFAULT NULL')
    add_column_if_missing(conn, 'submissions', 'content_hash', "content_hash TEXT DEFAULT ''")
    add_column_if_missing(conn, 'submissions', 'content_commitment', "content_commitment TEXT DEFAULT ''")
    add_column_if_missing(conn, 'submissions', 'content_public_summary', "content_public_summary TEXT DEFAULT '[protected submission]'")
    add_column_if_missing(conn, 'submissions', 'content_protection', "content_protection TEXT DEFAULT 'sealed_commitment_v1'")
    add_column_if_missing(conn, 'submissions', 'msg_type', "msg_type TEXT DEFAULT 'progress_update'")
    add_column_if_missing(conn, 'submissions', 'severity', "severity TEXT DEFAULT 'info'")

    seal_legacy_submissions(conn)
    create_immutable_submission_trigger(conn)
    seed_default_users(conn)

    conn.commit()
    conn.close()


def seal_legacy_submissions(conn):
    from utils.content_security import PROTECTED_CONTENT, protect_content

    rows = conn.execute('''
        SELECT id, content
        FROM submissions
        WHERE COALESCE(content_commitment, '') = ''
          AND content != ?
    ''', (PROTECTED_CONTENT,)).fetchall()
    for row in rows:
        protected = protect_content(row['content'])
        conn.execute('''
            UPDATE submissions
            SET content=?,
                content_hash=?,
                content_commitment=?,
                content_public_summary=?,
                content_protection=?
            WHERE id=?
        ''', (
            protected['content'],
            protected['content_hash'],
            protected['content_commitment'],
            protected['content_public_summary'],
            protected['content_protection'],
            row['id'],
        ))


def create_immutable_submission_trigger(conn):
    conn.execute('''
        CREATE TRIGGER IF NOT EXISTS trg_submissions_immutable
        BEFORE UPDATE ON submissions
        BEGIN
            SELECT RAISE(ABORT, 'submissions are immutable once created');
        END;
    ''')


def seed_default_users(conn):
    from utils.auth import hash_password
    from utils.helpers import now

    if conn.execute('SELECT COUNT(*) AS c FROM users').fetchone()['c']:
        return

    ts = now()
    users = [
        ('user_001', 'contestant', hash_password('contestant123'), 0, ts),
        ('user_002', 'organizer', hash_password('organizer123'), 1, ts),
        ('user_003', 'admin', hash_password('admin123'), 2, ts),
    ]
    conn.executemany('''
        INSERT INTO users (id, username, password_hash, role, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', users)
