CREATE TABLE IF NOT EXISTS races (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    description TEXT NOT NULL,
    start_time  TEXT NOT NULL,
    end_time    TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'upcoming',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS submissions (
    id           TEXT PRIMARY KEY,
    race_id      TEXT NOT NULL,
    student_name TEXT NOT NULL,
    content      TEXT NOT NULL,
    submitted_at TEXT NOT NULL,
    UNIQUE (race_id, student_name),
    FOREIGN KEY (race_id) REFERENCES races(id)
);
