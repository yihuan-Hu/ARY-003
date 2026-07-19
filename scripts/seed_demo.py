"""Seed a complete ARY demo dataset for final presentation.

Run from repository root:
    python scripts/seed_demo.py
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.config import Config  # noqa: E402
from app.database import init_db  # noqa: E402
from app.utils.auth import hash_password  # noqa: E402


DEMO_PASSWORD = "Demo1234"
DEMO_USERS = {
    "admin_demo": ["admin"],
    "organizer_demo": ["organizer"],
    "rider_demo": ["rider"],
    "judge_demo": ["judge"],
}


def _connect() -> sqlite3.Connection:
    os.environ.setdefault("ARY_SECRET_KEY", "demo-secret-key-for-local-final-review")
    os.environ.setdefault("ARY_SUBMISSION_SECRET", "demo-submission-secret-for-local-final-review")
    os.environ.setdefault("ARY_CORS_ORIGINS", "http://localhost:5000,http://localhost:3000")
    init_db()
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _one(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> sqlite3.Row | None:
    return conn.execute(sql, params).fetchone()


def _ensure_user(conn: sqlite3.Connection, username: str, roles: list[str]) -> int:
    password_hash = hash_password(DEMO_PASSWORD)
    role_value = 3 if "admin" in roles else 2 if "organizer" in roles else 1
    row = _one(conn, "SELECT id FROM users WHERE username=?", (username,))
    if row:
      conn.execute(
          "UPDATE users SET password_hash=?, roles=?, role=? WHERE id=?",
          (password_hash, json.dumps(roles), role_value, row["id"]),
      )
      return int(row["id"])
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, role, roles) VALUES (?, ?, ?, ?)",
        (username, password_hash, role_value, json.dumps(roles)),
    )
    return int(cur.lastrowid)


def _ensure_race(conn: sqlite3.Connection, name: str, status: str, organizer_id: int, description: str) -> int:
    row = _one(conn, "SELECT id FROM races WHERE name=?", (name,))
    if row:
        race_id = int(row["id"])
        conn.execute(
            "UPDATE races SET status=?, visibility='public', created_by_user_id=?, description=?, judging_mode='blind' WHERE id=?",
            (status, organizer_id, description, race_id),
        )
        return race_id
    cur = conn.execute(
        """
        INSERT INTO races
            (name, slug, status, description, rules, visibility, created_by_user_id,
             theme, organizer_name, judging_mode, ca_policy)
        VALUES (?, ?, ?, ?, ?, 'public', ?, ?, 'ARY 组委会', 'blind', 'rider_choice')
        """,
        (
            name,
            name.lower().replace(" ", "-"),
            status,
            description,
            "提交作品需包含说明、仓库链接和演示入口。",
            organizer_id,
            "智能体骑行",
        ),
    )
    return int(cur.lastrowid)


def _ensure_registration(conn: sqlite3.Connection, race_id: int, user_id: int, status: str, reviewer_id: int) -> int:
    row = _one(conn, "SELECT id FROM registrations WHERE race_id=? AND user_id=?", (race_id, user_id))
    if row:
        conn.execute(
            "UPDATE registrations SET status=?, reviewed_by_user_id=?, reviewed_at=datetime('now') WHERE id=?",
            (status, reviewer_id, row["id"]),
        )
        return int(row["id"])
    cur = conn.execute(
        """
        INSERT INTO registrations (race_id, user_id, status, reviewed_by_user_id, reviewed_at)
        VALUES (?, ?, ?, ?, datetime('now'))
        """,
        (race_id, user_id, status, reviewer_id),
    )
    return int(cur.lastrowid)


def _ensure_project(conn: sqlite3.Connection, registration_id: int) -> int:
    row = _one(conn, "SELECT id FROM race_projects WHERE registration_id=?", (registration_id,))
    if row:
        conn.execute(
            "UPDATE race_projects SET aggregate_ingestion_status='ready', connection_health='healthy' WHERE id=?",
            (row["id"],),
        )
        return int(row["id"])
    cur = conn.execute(
        """
        INSERT INTO race_projects (registration_id, aggregate_ingestion_status, connection_health)
        VALUES (?, 'ready', 'healthy')
        """,
        (registration_id,),
    )
    return int(cur.lastrowid)


def _ensure_work(conn: sqlite3.Connection, project_id: int, title: str, status: str, public: bool) -> int:
    row = _one(conn, "SELECT id FROM works WHERE race_project_id=? AND title=?", (project_id, title))
    digest = hashlib.sha256(f"{project_id}:{title}".encode("utf-8")).hexdigest()
    visibility = "public" if public else "private"
    if row:
        conn.execute(
            "UPDATE works SET work_status=?, visibility=?, content_hash=?, content_commitment=?, submitted_at=datetime('now') WHERE id=?",
            (status, visibility, digest, digest, row["id"]),
        )
        return int(row["id"])
    cur = conn.execute(
        """
        INSERT INTO works
            (race_project_id, title, description, repo_url, demo_url, work_status,
             visibility, content_hash, content_commitment, submitted_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (
            project_id,
            title,
            "期末演示用智能体骑行作品，包含 CA 接入、进度追踪和公开展示。",
            "https://github.com/demo/ary-agent",
            "https://demo.local/ary-agent",
            status,
            visibility,
            digest,
            digest,
        ),
    )
    return int(cur.lastrowid)


def seed_demo() -> None:
    conn = _connect()
    try:
        users = {name: _ensure_user(conn, name, roles) for name, roles in DEMO_USERS.items()}
        registration_race = _ensure_race(
            conn,
            "ARY 公开报名赛",
            "registration",
            users["organizer_demo"],
            "用于演示报名入口、参与工作区和组织者审核流程。",
        )
        judging_race = _ensure_race(
            conn,
            "ARY 智能体决赛",
            "judging",
            users["organizer_demo"],
            "用于演示作品提交、评委评分、榜单和 Live Hall。",
        )

        pending_reg = _ensure_registration(conn, registration_race, users["rider_demo"], "submitted", users["organizer_demo"])
        approved_reg = _ensure_registration(conn, judging_race, users["rider_demo"], "approved", users["organizer_demo"])
        project_id = _ensure_project(conn, approved_reg)
        draft_work_id = _ensure_work(conn, project_id, "ARY 草稿作品", "draft", False)
        submitted_work_id = _ensure_work(conn, project_id, "ARY 决赛作品", "submitted", True)

        conn.execute("UPDATE race_projects SET primary_work_id=? WHERE id=?", (submitted_work_id, project_id))
        conn.execute(
            """
            INSERT OR IGNORE INTO judge_invitations
                (race_id, judge_user_id, status, invited_by_user_id, message, responded_at)
            VALUES (?, ?, 'accepted', ?, '请参与 ARY 决赛盲审。', datetime('now'))
            """,
            (judging_race, users["judge_demo"], users["organizer_demo"]),
        )
        conn.execute(
            "INSERT OR IGNORE INTO judge_assignments (race_id, work_id, judge_user_id) VALUES (?, ?, ?)",
            (judging_race, submitted_work_id, users["judge_demo"]),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO judging_records
                (work_id, judge_user_id, technical_score, innovation_score,
                 presentation_score, completeness_score, comment)
            VALUES (?, ?, 9, 9, 8, 9, '演示数据：作品完成度高，链路完整。')
            """,
            (submitted_work_id, users["judge_demo"]),
        )
        conn.execute(
            """
            INSERT INTO awards (race_id, title, position, work_id, registration_id, description)
            SELECT ?, '最佳智能体表现奖', 1, ?, ?, '演示数据：综合评分第一。'
            WHERE NOT EXISTS (SELECT 1 FROM awards WHERE race_id=? AND position=1)
            """,
            (judging_race, submitted_work_id, approved_reg, judging_race),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO ca_connections
                (race_project_id, ca_type, provider_name, connection_status,
                 ca_policy_source, api_key_hash, handshake_at, last_signal_at, config_json)
            VALUES (?, 'codex', 'Codex Demo CA', 'active', 'rider_choice',
                    'demo-key-hash', datetime('now'), datetime('now'), '{"mode":"demo"}')
            """,
            (project_id,),
        )
        conn.execute(
            """
            INSERT INTO racing_entries
                (race_id, student_name, round_progress, risk_level, ca_provider)
            VALUES (?, 'rider_demo', 86, 'low', 'Codex Demo CA')
            """,
            (judging_race,),
        )
        conn.execute(
            """
            INSERT INTO audit_logs (action, actor_user_id, target_type, target_id, detail, request_id)
            VALUES ('seed_demo', ?, 'race', ?, '期末演示数据已生成', 'seed-demo')
            """,
            (users["admin_demo"], judging_race),
        )
        conn.commit()
        print("Demo data seeded.")
        print(f"Users: {', '.join(DEMO_USERS)}")
        print(f"Password: {DEMO_PASSWORD}")
        print(f"Races: registration=#{registration_race}, judging=#{judging_race}")
    finally:
        conn.close()


if __name__ == "__main__":
    seed_demo()
