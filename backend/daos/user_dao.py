class UserDAO:
    @staticmethod
    def get_by_username(conn, username):
        return conn.execute(
            'SELECT * FROM users WHERE username = ?',
            (username,),
        ).fetchone()

    @staticmethod
    def get_by_id(conn, user_id):
        return conn.execute(
            'SELECT * FROM users WHERE id = ?',
            (user_id,),
        ).fetchone()
