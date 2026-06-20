class RiderDAO:
    @staticmethod
    def list_all(conn):
        return conn.execute('SELECT * FROM riders ORDER BY id').fetchall()

    @staticmethod
    def get_by_id(conn, rider_id):
        return conn.execute('SELECT * FROM riders WHERE id = ?', (rider_id,)).fetchone()

    @staticmethod
    def create(conn, rider_id, name, created_at):
        conn.execute(
            'INSERT INTO riders (id, name, created_at) VALUES (?, ?, ?)',
            (rider_id, name, created_at),
        )
        return RiderDAO.get_by_id(conn, rider_id)
