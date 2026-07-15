"""IntegrityLogDAO（人员 A 交付）"""
from app.dao.base import BaseDAO
from app.database import get_db


class IntegrityLogDAO(BaseDAO):
    table = "integrity_log"

    def find_by_resource(self, resource_type: str, resource_id: int) -> list[dict]:
        db = get_db()
        rows = db.execute(
            """SELECT * FROM integrity_log
               WHERE resource_type = ? AND resource_id = ?
               ORDER BY created_at ASC""",
            (resource_type, resource_id),
        ).fetchall()
        return [dict(r) for r in rows]
