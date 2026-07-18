"""
CAConnectionDAO（人员 D 交付）
继承 BaseDAO，提供 CA 连接记录的标准 CRUD + 关联查询。
"""
from app.dao.base import BaseDAO
from app.database import get_db


class CAConnectionDAO(BaseDAO):
    table = "ca_connections"

    def find_by_race_project(self, race_project_id: int) -> list[dict]:
        """查询某 RaceProject 下的所有 CA 连接"""
        db = get_db()
        rows = db.execute(
            "SELECT * FROM ca_connections WHERE race_project_id = ? ORDER BY created_at DESC",
            (race_project_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def find_by_race(self, race_id: int) -> list[dict]:
        """查询某赛事下所有 CA 连接（通过 race_projects → registrations 关联）"""
        db = get_db()
        rows = db.execute(
            """SELECT cc.* FROM ca_connections cc
               JOIN race_projects rp ON cc.race_project_id = rp.id
               JOIN registrations reg ON rp.registration_id = reg.id
               WHERE reg.race_id = ?
               ORDER BY cc.created_at DESC""",
            (race_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def find_by_project_and_provider(self, race_project_id: int, provider_name: str) -> dict | None:
        """按 RaceProject + provider 查找"""
        db = get_db()
        row = db.execute(
            "SELECT * FROM ca_connections WHERE race_project_id = ? AND provider_name = ?",
            (race_project_id, provider_name),
        ).fetchone()
        return dict(row) if row else None

    def find_active_by_race(self, race_id: int) -> list[dict]:
        """查询某赛事下活跃的 CA 连接（connected 或 active 状态）"""
        db = get_db()
        rows = db.execute(
            """SELECT cc.* FROM ca_connections cc
               JOIN race_projects rp ON cc.race_project_id = rp.id
               JOIN registrations reg ON rp.registration_id = reg.id
               WHERE reg.race_id = ? AND cc.connection_status IN ('connected', 'active')
               ORDER BY cc.created_at DESC""",
            (race_id,),
        ).fetchall()
        return [dict(r) for r in rows]
