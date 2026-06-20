class AgentUsageDAO:
    @staticmethod
    def create(conn, values):
        conn.execute('''
            INSERT INTO agent_api_usage
                (id, race_id, entry_id, rider_id, provider, model, api_endpoint,
                 prompt_tokens, completion_tokens, total_tokens, cost_usd,
                 latency_ms, status_code, detected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            values['id'],
            values['race_id'],
            values['entry_id'],
            values['rider_id'],
            values['provider'],
            values['model'],
            values['api_endpoint'],
            values['prompt_tokens'],
            values['completion_tokens'],
            values['total_tokens'],
            values['cost_usd'],
            values['latency_ms'],
            values['status_code'],
            values['detected_at'],
        ))
        return AgentUsageDAO.get_by_id(conn, values['id'])

    @staticmethod
    def get_by_id(conn, usage_id):
        return conn.execute('''
            SELECT u.*, r.name AS rider_name
            FROM agent_api_usage u
            LEFT JOIN riders r ON r.id = u.rider_id
            WHERE u.id = ?
        ''', (usage_id,)).fetchone()

    @staticmethod
    def list_by_race(conn, race_id, limit=100):
        return conn.execute('''
            SELECT u.*, r.name AS rider_name
            FROM agent_api_usage u
            LEFT JOIN riders r ON r.id = u.rider_id
            WHERE u.race_id = ?
            ORDER BY u.detected_at DESC, u.id DESC
            LIMIT ?
        ''', (race_id, limit)).fetchall()

    @staticmethod
    def provider_totals(conn, race_id):
        return conn.execute('''
            SELECT
                provider,
                COUNT(*) AS call_count,
                COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                COALESCE(SUM(completion_tokens), 0) AS completion_tokens,
                COALESCE(SUM(total_tokens), 0) AS total_tokens,
                COALESCE(SUM(cost_usd), 0) AS cost_usd,
                COALESCE(AVG(latency_ms), 0) AS avg_latency_ms,
                SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) AS error_count,
                MAX(detected_at) AS last_detected_at
            FROM agent_api_usage
            WHERE race_id = ?
            GROUP BY provider
            ORDER BY total_tokens DESC, provider ASC
        ''', (race_id,)).fetchall()

    @staticmethod
    def model_totals(conn, race_id):
        return conn.execute('''
            SELECT
                provider,
                model,
                COUNT(*) AS call_count,
                COALESCE(SUM(total_tokens), 0) AS total_tokens,
                COALESCE(SUM(cost_usd), 0) AS cost_usd
            FROM agent_api_usage
            WHERE race_id = ?
            GROUP BY provider, model
            ORDER BY provider ASC, total_tokens DESC
        ''', (race_id,)).fetchall()

    @staticmethod
    def total_by_race(conn, race_id):
        return conn.execute('''
            SELECT
                COUNT(*) AS call_count,
                COALESCE(SUM(total_tokens), 0) AS total_tokens,
                COALESCE(SUM(cost_usd), 0) AS cost_usd,
                MAX(detected_at) AS last_detected_at
            FROM agent_api_usage
            WHERE race_id = ?
        ''', (race_id,)).fetchone()
