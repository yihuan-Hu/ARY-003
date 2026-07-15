"""AuditLogDAO（人员 A 交付）"""
from app.dao.base import BaseDAO
from app.database import get_db


class AuditLogDAO(BaseDAO):
    table = "audit_logs"

    def find_by_actor(self, actor_user_id: int, limit: int = 50) -> list[dict]:
        db = get_db()
        rows = db.execute(
            """SELECT * FROM audit_logs
               WHERE actor_user_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (actor_user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def find_by_target(self, target_type: str, target_id: int, limit: int = 50) -> list[dict]:
        db = get_db()
        rows = db.execute(
            """SELECT * FROM audit_logs
               WHERE target_type = ? AND target_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (target_type, target_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
