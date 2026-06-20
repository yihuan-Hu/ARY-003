import os
import sqlite3
import tempfile


def test_init_db_seals_legacy_plaintext_before_immutable_trigger():
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    os.unlink(db_path)

    conn = sqlite3.connect(db_path)
    conn.executescript('''
        CREATE TABLE races (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'upcoming',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE submissions (
            id TEXT PRIMARY KEY,
            race_id TEXT NOT NULL,
            student_name TEXT NOT NULL,
            content TEXT NOT NULL,
            submitted_at TEXT NOT NULL,
            UNIQUE (race_id, student_name),
            FOREIGN KEY (race_id) REFERENCES races(id)
        );

        INSERT INTO races
            (id, title, description, start_time, end_time, status, created_at, updated_at)
        VALUES
            ('race_001', 'Race', 'Desc', '2026-06-13T00:00:00Z',
             '2026-06-14T00:00:00Z', 'open', '2026-06-13T00:00:00Z',
             '2026-06-13T00:00:00Z');

        INSERT INTO submissions
            (id, race_id, student_name, content, submitted_at)
        VALUES
            ('sub_001', 'race_001', 'Ada', 'legacy private code',
             '2026-06-13T00:00:00Z');
    ''')
    conn.commit()
    conn.close()

    previous = os.environ.get('ORGANIZER_DB')
    os.environ['ORGANIZER_DB'] = db_path
    try:
        from app import create_app

        create_app('test')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute('SELECT * FROM submissions WHERE id = ?', ('sub_001',)).fetchone()
        trigger = conn.execute('''
            SELECT name FROM sqlite_master
            WHERE type = 'trigger' AND name = 'trg_submissions_immutable'
        ''').fetchone()
        conn.close()
    finally:
        if previous is None:
            os.environ.pop('ORGANIZER_DB', None)
        else:
            os.environ['ORGANIZER_DB'] = previous
        if os.path.exists(db_path):
            os.unlink(db_path)

    assert row['content'] == '[protected submission]'
    assert row['content_commitment']
    assert row['content_protection'] == 'sealed_commitment_v1'
    assert trigger is not None
