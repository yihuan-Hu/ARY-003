class SubmissionDAO:
    @staticmethod
    def list_by_race(conn, race_id):
        return conn.execute(
            'SELECT * FROM submissions WHERE race_id = ? ORDER BY submitted_at DESC',
            (race_id,),
        ).fetchall()

    @staticmethod
    def get_by_id(conn, submission_id):
        return conn.execute('SELECT * FROM submissions WHERE id = ?', (submission_id,)).fetchone()

    @staticmethod
    def get_by_race_student(conn, race_id, student_name):
        return conn.execute(
            'SELECT * FROM submissions WHERE race_id = ? AND student_name = ?',
            (race_id, student_name),
        ).fetchone()

    @staticmethod
    def latest_for_entry(conn, race_id, rider_id, rider_name):
        return conn.execute('''
            SELECT *
            FROM submissions
            WHERE race_id = ?
              AND (rider_id = ? OR student_name = ?)
            ORDER BY submitted_at DESC
            LIMIT 1
        ''', (race_id, rider_id, rider_name)).fetchone()

    @staticmethod
    def recent_messages(conn, race_id, limit=20):
        return conn.execute('''
            SELECT
                s.*,
                e.id AS entry_id,
                COALESCE(r.name, s.student_name) AS source_name
            FROM submissions s
            LEFT JOIN riders r ON r.id = s.rider_id OR r.name = s.student_name
            LEFT JOIN racing_entries e ON e.race_id = s.race_id AND e.rider_id = r.id
            WHERE s.race_id = ?
            ORDER BY s.submitted_at DESC
            LIMIT ?
        ''', (race_id, limit)).fetchall()

    @staticmethod
    def create(conn, values):
        conn.execute('''
            INSERT INTO submissions
                (id, race_id, rider_id, student_name, content, content_hash,
                 content_commitment, content_public_summary, content_protection,
                 msg_type, severity, submitted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            values['id'], values['race_id'], values['rider_id'],
            values['student_name'], values['content'], values['content_hash'],
            values['content_commitment'], values['content_public_summary'],
            values['content_protection'], values['msg_type'], values['severity'],
            values['submitted_at'],
        ))
        return SubmissionDAO.get_by_id(conn, values['id'])

    @staticmethod
    def update(conn, submission_id, values):
        conn.execute('''
            UPDATE submissions
            SET rider_id=?,
                content=?,
                content_hash=?,
                content_commitment=?,
                content_public_summary=?,
                content_protection=?,
                msg_type=?,
                severity=?,
                submitted_at=?
            WHERE id=?
        ''', (
            values['rider_id'], values['content'], values['content_hash'],
            values['content_commitment'], values['content_public_summary'],
            values['content_protection'], values['msg_type'], values['severity'],
            values['submitted_at'], submission_id,
        ))
        return SubmissionDAO.get_by_id(conn, submission_id)

    @staticmethod
    def count(conn):
        return conn.execute('SELECT COUNT(*) AS c FROM submissions').fetchone()['c']

    @staticmethod
    def distinct_student_count(conn):
        return conn.execute(
            'SELECT COUNT(DISTINCT student_name) AS c FROM submissions'
        ).fetchone()['c']

    @staticmethod
    def list_for_export(conn):
        return conn.execute('''
            SELECT s.id, s.race_id, r.title AS race_title, s.rider_id,
                   s.student_name, s.content, s.content_commitment,
                   s.content_protection, s.msg_type, s.severity, s.submitted_at
            FROM submissions s
            LEFT JOIN races r ON r.id = s.race_id
            ORDER BY s.id
        ''').fetchall()
