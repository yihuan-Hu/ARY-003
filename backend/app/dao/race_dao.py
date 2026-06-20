from app.database import get_db


class RaceDAO:
    def create(self, name: str, created_by_user_id: int, **kwargs) -> dict:
        db = get_db()
        cursor = db.execute(
            """INSERT INTO races (name, slug, status, description, created_by_user_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            (
                name,
                kwargs.get("slug", name.lower().replace(" ", "-")),
                kwargs.get("status", "upcoming"),
                kwargs.get("description", ""),
                created_by_user_id,
            ),
        )
        db.commit()
        return self.find_by_id(cursor.lastrowid)

    def find_by_id(self, race_id: int) -> dict | None:
        db = get_db()
        row = db.execute("SELECT * FROM races WHERE id = ?", (race_id,)).fetchone()
        return dict(row) if row else None

    def find_all(self) -> list[dict]:
        db = get_db()
        rows = db.execute("SELECT * FROM races ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def find_by_organizer(self, user_id: int) -> list[dict]:
        db = get_db()
        rows = db.execute(
            "SELECT * FROM races WHERE created_by_user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def update_status(self, race_id: int, status: str) -> dict | None:
        db = get_db()
        db.execute(
            "UPDATE races SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (status, race_id),
        )
        db.commit()
        return self.find_by_id(race_id)
