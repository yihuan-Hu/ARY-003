CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL
);
