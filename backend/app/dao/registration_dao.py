from app.database import get_db


class RegistrationDAO:
    def create(self, race_id: int, user_id: int) -> dict:
        """创建报名，UNIQUE(race_id, user_id) 保证同一用户同一赛事只有一个报名"""
        db = get_db()
        cursor = db.execute(
            """INSERT INTO registrations (race_id, user_id, status, submitted_at, created_at, updated_at)
               VALUES (?, ?, 'submitted', datetime('now'), datetime('now'), datetime('now'))""",
            (race_id, user_id),
        )
        db.commit()
        return self.find_by_id(cursor.lastrowid)

    def find_by_id(self, registration_id: int) -> dict | None:
        db = get_db()
        row = db.execute("SELECT * FROM registrations WHERE id = ?", (registration_id,)).fetchone()
        return dict(row) if row else None

    def find_by_race_and_user(self, race_id: int, user_id: int) -> dict | None:
        db = get_db()
        row = db.execute(
            "SELECT * FROM registrations WHERE race_id = ? AND user_id = ?",
            (race_id, user_id),
        ).fetchone()
        return dict(row) if row else None

    def find_by_race(self, race_id: int) -> list[dict]:
        db = get_db()
        rows = db.execute(
            "SELECT * FROM registrations WHERE race_id = ? ORDER BY submitted_at DESC",
            (race_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def find_by_user(self, user_id: int) -> list[dict]:
        db = get_db()
        rows = db.execute(
            "SELECT * FROM registrations WHERE user_id = ? ORDER BY submitted_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def update_status(self, registration_id: int, new_status: str, reviewer_user_id: int | None = None) -> dict | None:
        db = get_db()
        db.execute(
            """UPDATE registrations
               SET status = ?, reviewed_at = datetime('now'),
                   reviewed_by_user_id = ?, updated_at = datetime('now')
               WHERE id = ?""",
            (new_status, reviewer_user_id, registration_id),
        )
        db.commit()
        return self.find_by_id(registration_id)

    def count_by_race(self, race_id: int) -> int:
        db = get_db()
        row = db.execute(
            "SELECT COUNT(*) as cnt FROM registrations WHERE race_id = ?",
            (race_id,),
        ).fetchone()
        return row["cnt"] if row else 0
