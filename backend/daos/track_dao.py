class TrackDAO:
    @staticmethod
    def get_by_id_or_race(conn, profile_or_race_id):
        return conn.execute(
            'SELECT * FROM track_profiles WHERE id = ? OR race_id = ?',
            (profile_or_race_id, profile_or_race_id),
        ).fetchone()

    @staticmethod
    def get_by_race(conn, race_id):
        return conn.execute(
            'SELECT * FROM track_profiles WHERE race_id = ?',
            (race_id,),
        ).fetchone()

    @staticmethod
    def create(conn, profile_id, race_id, profile_json, created_at):
        conn.execute(
            'INSERT INTO track_profiles (id, race_id, profile_json, created_at) VALUES (?, ?, ?, ?)',
            (profile_id, race_id, profile_json, created_at),
        )
        return TrackDAO.get_by_id_or_race(conn, profile_id)

    @staticmethod
    def update(conn, profile_id, profile_json, created_at):
        conn.execute(
            'UPDATE track_profiles SET profile_json=?, created_at=? WHERE id=?',
            (profile_json, created_at, profile_id),
        )
        return TrackDAO.get_by_id_or_race(conn, profile_id)
