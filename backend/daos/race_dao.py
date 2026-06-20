class RaceDAO:
    @staticmethod
    def list_all(conn, keyword='', status=''):
        sql = 'SELECT * FROM races WHERE 1=1'
        args = []
        if keyword:
            sql += ' AND title LIKE ?'
            args.append(f'%{keyword}%')
        if status:
            sql += ' AND status = ?'
            args.append(status)
        sql += ' ORDER BY id DESC'
        return conn.execute(sql, args).fetchall()

    @staticmethod
    def get_by_id(conn, race_id):
        return conn.execute('SELECT * FROM races WHERE id = ?', (race_id,)).fetchone()

    @staticmethod
    def create(conn, values):
        conn.execute('''
            INSERT INTO races
                (id, title, description, start_time, end_time, status, theme,
                 organizer, current_round, current_phase, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            values['id'], values['title'], values['description'],
            values['start_time'], values['end_time'], values['status'],
            values['theme'], values['organizer'], values['current_round'],
            values['current_phase'], values['created_at'], values['updated_at'],
        ))
        return RaceDAO.get_by_id(conn, values['id'])

    @staticmethod
    def update(conn, race_id, values):
        conn.execute('''
            UPDATE races
            SET title=?, description=?, start_time=?, end_time=?, status=?,
                theme=?, organizer=?, current_round=?, current_phase=?, updated_at=?
            WHERE id=?
        ''', (
            values['title'], values['description'], values['start_time'],
            values['end_time'], values['status'], values['theme'],
            values['organizer'], values['current_round'], values['current_phase'],
            values['updated_at'], race_id,
        ))
        return RaceDAO.get_by_id(conn, race_id)

    @staticmethod
    def count(conn):
        return conn.execute('SELECT COUNT(*) AS c FROM races').fetchone()['c']

    @staticmethod
    def count_open(conn):
        return conn.execute("SELECT COUNT(*) AS c FROM races WHERE status = 'open'").fetchone()['c']

    @staticmethod
    def list_for_export(conn):
        return conn.execute('SELECT * FROM races ORDER BY id').fetchall()

    @staticmethod
    def submissions_by_race(conn):
        return conn.execute('''
            SELECT r.id AS raceId, r.title,
                   (SELECT COUNT(*) FROM submissions s WHERE s.race_id = r.id) AS submissionCount
            FROM races r ORDER BY r.id
        ''').fetchall()
