import json
from app.database import get_db


class UserDAO:
    def create(self, username: str, password_hash: str, roles: list[str] = None) -> dict:
        db = get_db()
        roles_json = json.dumps(roles or ["contestant"])
        cursor = db.execute(
            "INSERT INTO users (username, password_hash, roles) VALUES (?, ?, ?)",
            (username, password_hash, roles_json),
        )
        db.commit()
        return self.find_by_id(cursor.lastrowid)

    def find_by_id(self, user_id: int) -> dict | None:
        db = get_db()
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

    def find_by_username(self, username: str) -> dict | None:
        db = get_db()
        row = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None

    def find_all(self) -> list[dict]:
        db = get_db()
        rows = db.execute("SELECT * FROM users").fetchall()
        return [dict(r) for r in rows]

    def update_roles(self, user_id: int, roles: list[str]) -> dict | None:
        db = get_db()
        roles_json = json.dumps(roles)
        db.execute(
            "UPDATE users SET roles = ?, updated_at = datetime('now') WHERE id = ?",
            (roles_json, user_id),
        )
        db.commit()
        return self.find_by_id(user_id)

    def get_roles(self, user: dict) -> list[str]:
        raw = user.get("roles", '["contestant"]')
        if isinstance(raw, str):
            return json.loads(raw) if raw else ["contestant"]
        return raw if isinstance(raw, list) else ["contestant"]
