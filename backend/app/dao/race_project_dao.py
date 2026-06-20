from app.database import get_db


class RaceProjectDAO:
    def create(self, registration_id: int) -> dict:
        """创建 RaceProject，UNIQUE(registration_id) 保证一对一"""
        db = get_db()
        cursor = db.execute(
            """INSERT INTO race_projects (registration_id, created_at, updated_at)
               VALUES (?, datetime('now'), datetime('now'))""",
            (registration_id,),
        )
        db.commit()
        return self.find_by_id(cursor.lastrowid)

    def find_by_id(self, race_project_id: int) -> dict | None:
        db = get_db()
        row = db.execute("SELECT * FROM race_projects WHERE id = ?", (race_project_id,)).fetchone()
        return dict(row) if row else None

    def find_by_registration(self, registration_id: int) -> dict | None:
        db = get_db()
        row = db.execute(
            "SELECT * FROM race_projects WHERE registration_id = ?",
            (registration_id,),
        ).fetchone()
        return dict(row) if row else None

    def find_by_race(self, race_id: int) -> list[dict]:
        """通过 registrations 关联查询某赛事下的所有 RaceProject"""
        db = get_db()
        rows = db.execute(
            """SELECT rp.* FROM race_projects rp
               JOIN registrations reg ON rp.registration_id = reg.id
               WHERE reg.race_id = ?
               ORDER BY rp.created_at DESC""",
            (race_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def find_by_user(self, user_id: int) -> list[dict]:
        """通过 registrations 关联查询某用户的所有 RaceProject"""
        db = get_db()
        rows = db.execute(
            """SELECT rp.* FROM race_projects rp
               JOIN registrations reg ON rp.registration_id = reg.id
               WHERE reg.user_id = ?
               ORDER BY rp.created_at DESC""",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def count_by_registration(self, registration_id: int) -> int:
        """幂等检查：统计某报名下的 RaceProject 数量"""
        db = get_db()
        row = db.execute(
            "SELECT COUNT(*) as cnt FROM race_projects WHERE registration_id = ?",
            (registration_id,),
        ).fetchone()
        return row["cnt"] if row else 0
