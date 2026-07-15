from app.dao.base import BaseDAO
from app.database import get_db


class AnnouncementDAO(BaseDAO):
    table = "announcements"

    def find_by_race(
        self, race_id: int, visibility: str | None = None
    ) -> list[dict]:
        db = get_db()
        if visibility:
            rows = db.execute(
                """SELECT * FROM announcements
                   WHERE race_id = ? AND visibility = ?
                   ORDER BY created_at DESC, id DESC""",
                (race_id, visibility),
            ).fetchall()
        else:
            rows = db.execute(
                """SELECT * FROM announcements WHERE race_id = ?
                   ORDER BY created_at DESC, id DESC""",
                (race_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_uncommitted(
        self, race_id: int, user_id: int, title: str, body: str
    ) -> dict:
        cursor = get_db().execute(
            """INSERT INTO announcements
               (race_id, title, body, visibility, created_by_user_id)
               VALUES (?, ?, ?, 'draft', ?)""",
            (race_id, title, body, user_id),
        )
        return self.find_by_id(cursor.lastrowid)

    def update_uncommitted(self, announcement_id: int, data: dict) -> dict | None:
        allowed = {key: value for key, value in data.items() if key in {"title", "body"}}
        if not allowed:
            return self.find_by_id(announcement_id)
        assignments = ", ".join(f"{key} = ?" for key in allowed)
        get_db().execute(
            f"""UPDATE announcements SET {assignments}, updated_at=datetime('now')
                WHERE id=?""",
            tuple(allowed.values()) + (announcement_id,),
        )
        return self.find_by_id(announcement_id)

    def set_visibility_uncommitted(
        self, announcement_id: int, visibility: str
    ) -> dict | None:
        get_db().execute(
            """UPDATE announcements SET visibility=?, updated_at=datetime('now')
               WHERE id=?""",
            (visibility, announcement_id),
        )
        return self.find_by_id(announcement_id)

    def delete_uncommitted(self, announcement_id: int) -> bool:
        cursor = get_db().execute(
            "DELETE FROM announcements WHERE id=?", (announcement_id,)
        )
        return cursor.rowcount > 0
