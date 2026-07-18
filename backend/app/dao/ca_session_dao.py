"""
CASessionDAO（人员 D 交付）
继承 BaseDAO，提供 CA Session 数据记录的标准 CRUD + 关联查询。
"""
from app.dao.base import BaseDAO
from app.database import get_db


class CASessionDAO(BaseDAO):
    table = "ca_sessions"

    def find_by_connection(self, ca_connection_id: int) -> list[dict]:
        """查询某 CA 连接下的所有会话记录"""
        db = get_db()
        rows = db.execute(
            "SELECT * FROM ca_sessions WHERE ca_connection_id = ? ORDER BY created_at DESC",
            (ca_connection_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def find_latest_by_connection(self, ca_connection_id: int) -> dict | None:
        """查询某 CA 连接的最新会话"""
        db = get_db()
        row = db.execute(
            "SELECT * FROM ca_sessions WHERE ca_connection_id = ? ORDER BY created_at DESC LIMIT 1",
            (ca_connection_id,),
        ).fetchone()
        return dict(row) if row else None

    def find_by_race(self, race_id: int) -> list[dict]:
        """查询某赛事下所有 CA Session（通过 ca_connections → race_projects → registrations 关联）"""
        db = get_db()
        rows = db.execute(
            """SELECT cs.* FROM ca_sessions cs
               JOIN ca_connections cc ON cs.ca_connection_id = cc.id
               JOIN race_projects rp ON cc.race_project_id = rp.id
               JOIN registrations reg ON rp.registration_id = reg.id
               WHERE reg.race_id = ?
               ORDER BY cs.created_at DESC""",
            (race_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def find_latest_by_race_project(self, race_project_id: int) -> list[dict]:
        """查询某 RaceProject 下每个连接的最新 Session（用于聚合）"""
        db = get_db()
        rows = db.execute(
            """SELECT cs.* FROM ca_sessions cs
               JOIN ca_connections cc ON cs.ca_connection_id = cc.id
               WHERE cc.race_project_id = ?
               AND cs.id IN (
                   SELECT MAX(cs2.id) FROM ca_sessions cs2
                   WHERE cs2.ca_connection_id = cc.id
               )
               ORDER BY cs.created_at DESC""",
            (race_project_id,),
        ).fetchall()
        return [dict(r) for r in rows]
