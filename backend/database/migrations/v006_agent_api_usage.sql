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

CREATE INDEX IF NOT EXISTS idx_agent_usage_race
    ON agent_api_usage(race_id);
CREATE INDEX IF NOT EXISTS idx_agent_usage_entry
    ON agent_api_usage(entry_id);
CREATE INDEX IF NOT EXISTS idx_agent_usage_provider
    ON agent_api_usage(provider);
