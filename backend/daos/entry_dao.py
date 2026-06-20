class EntryDAO:
    @staticmethod
    def list_by_race(conn, race_id):
        return conn.execute('''
            SELECT e.*, r.name AS rider_name
            FROM racing_entries e
            JOIN riders r ON r.id = e.rider_id
            WHERE e.race_id = ?
            ORDER BY e.round_progress DESC, e.updated_at DESC
        ''', (race_id,)).fetchall()

    @staticmethod
    def get_by_id(conn, entry_id):
        return conn.execute('''
            SELECT e.*, r.name AS rider_name
            FROM racing_entries e
            JOIN riders r ON r.id = e.rider_id
            WHERE e.id = ?
        ''', (entry_id,)).fetchone()

    @staticmethod
    def get_by_race_rider(conn, race_id, rider_id):
        return conn.execute(
            'SELECT * FROM racing_entries WHERE race_id = ? AND rider_id = ?',
            (race_id, rider_id),
        ).fetchone()

    @staticmethod
    def create(conn, values):
        conn.execute('''
            INSERT INTO racing_entries
                (id, race_id, rider_id, project_name, ca_provider,
                 overall_progress, round_progress, phase_progress, current_phase,
                 cost_tokens, cost_usd, risk_level, obstacle_count,
                 violation_count, lane_id, status, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            values['id'], values['race_id'], values['rider_id'],
            values['project_name'], values['ca_provider'],
            values['overall_progress'], values['round_progress'],
            values['phase_progress'], values['current_phase'],
            values['cost_tokens'], values['cost_usd'], values['risk_level'],
            values['obstacle_count'], values['violation_count'],
            values['lane_id'], values['status'], values['updated_at'],
        ))
        return EntryDAO.get_by_id(conn, values['id'])

    @staticmethod
    def update(conn, entry_id, values):
        conn.execute('''
            UPDATE racing_entries
            SET project_name=?, ca_provider=?, overall_progress=?, round_progress=?,
                phase_progress=?, current_phase=?, cost_tokens=?, cost_usd=?,
                risk_level=?, obstacle_count=?, violation_count=?, lane_id=?,
                status=?, updated_at=?
            WHERE id=?
        ''', (
            values['project_name'], values['ca_provider'], values['overall_progress'],
            values['round_progress'], values['phase_progress'], values['current_phase'],
            values['cost_tokens'], values['cost_usd'], values['risk_level'],
            values['obstacle_count'], values['violation_count'], values['lane_id'],
            values['status'], values['updated_at'], entry_id,
        ))
        return EntryDAO.get_by_id(conn, entry_id)

    @staticmethod
    def kpi_by_race(conn, race_id):
        return conn.execute('''
            SELECT
                COUNT(*) AS entry_count,
                AVG(overall_progress) AS completion_rate,
                COALESCE(SUM(cost_tokens), 0) AS total_tokens,
                COALESCE(SUM(CASE WHEN ca_provider = 'codex' THEN cost_tokens ELSE 0 END), 0) AS codex_tokens,
                COALESCE(SUM(CASE WHEN ca_provider = 'claude' THEN cost_tokens ELSE 0 END), 0) AS claude_tokens,
                SUM(CASE WHEN status NOT IN ('finished', 'stale') THEN 1 ELSE 0 END) AS active_riders,
                COUNT(DISTINCT rider_id) AS online_riders,
                SUM(CASE WHEN risk_level != 'none' THEN 1 ELSE 0 END) AS risk_count,
                COALESCE(SUM(obstacle_count), 0) AS obstacle_count,
                COALESCE(SUM(violation_count), 0) AS violation_count
            FROM racing_entries
            WHERE race_id = ?
        ''', (race_id,)).fetchone()
