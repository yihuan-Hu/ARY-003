-- ARY Organizer backend migration: v1 two-table DB -> v2 five-table DB.
-- Historical migration from the v1 two-table database.
-- New environments should start the Flask application and let schema.py
-- initialize the current schema.
--
-- If the Flask app has already started with the v2 code, these ALTER TABLE
-- statements may already be applied. In that case, no manual migration is needed.

BEGIN;

ALTER TABLE races ADD COLUMN theme TEXT DEFAULT '';
ALTER TABLE races ADD COLUMN organizer TEXT DEFAULT '';
ALTER TABLE races ADD COLUMN current_round INTEGER DEFAULT 1;
ALTER TABLE races ADD COLUMN current_phase TEXT DEFAULT 'DEV';

CREATE TABLE IF NOT EXISTS riders (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    created_at TEXT NOT NULL
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

ALTER TABLE submissions ADD COLUMN rider_id TEXT DEFAULT NULL;
ALTER TABLE submissions ADD COLUMN content_hash TEXT DEFAULT '';
ALTER TABLE submissions ADD COLUMN content_commitment TEXT DEFAULT '';
ALTER TABLE submissions ADD COLUMN content_public_summary TEXT DEFAULT '[protected submission]';
ALTER TABLE submissions ADD COLUMN content_protection TEXT DEFAULT 'sealed_commitment_v1';
ALTER TABLE submissions ADD COLUMN msg_type TEXT DEFAULT 'progress_update';
ALTER TABLE submissions ADD COLUMN severity TEXT DEFAULT 'info';

CREATE INDEX IF NOT EXISTS idx_entries_race ON racing_entries(race_id);
CREATE INDEX IF NOT EXISTS idx_entries_rider ON racing_entries(rider_id);
CREATE INDEX IF NOT EXISTS idx_subs_race ON submissions(race_id);

COMMIT;
