from app.database import get_db


class RegistrationDAO:
    def create(self, race_id: int, user_id: int, *, commit: bool = True) -> dict:
        """创建报名，UNIQUE(race_id, user_id) 保证同一用户同一赛事只有一个报名"""
        db = get_db()
        cursor = db.execute(
            """INSERT INTO registrations (race_id, user_id, status, submitted_at, created_at, updated_at)
               VALUES (?, ?, 'submitted', datetime('now'), datetime('now'), datetime('now'))""",
            (race_id, user_id),
        )
        if commit:
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

    def paginate_by_user(
        self,
        user_id: int,
        page: int = 1,
        per_page: int = 20,
        status: str | None = None,
    ) -> dict:
        return self._paginate("user_id", user_id, page, per_page, status)

    def paginate_by_race(
        self,
        race_id: int,
        page: int = 1,
        per_page: int = 20,
        status: str | None = None,
    ) -> dict:
        return self._paginate("race_id", race_id, page, per_page, status)

    def _paginate(
        self,
        owner_column: str,
        owner_id: int,
        page: int,
        per_page: int,
        status: str | None,
    ) -> dict:
        if owner_column not in {"user_id", "race_id"}:
            raise ValueError("Unsupported registration owner column")
        db = get_db()
        where = f"{owner_column} = ?"
        values: tuple = (owner_id,)
        if status:
            where += " AND status = ?"
            values += (status,)
        total = db.execute(
            f"SELECT COUNT(*) AS count FROM registrations WHERE {where}", values
        ).fetchone()["count"]
        rows = db.execute(
            f"""SELECT * FROM registrations WHERE {where}
                ORDER BY submitted_at DESC, id DESC LIMIT ? OFFSET ?""",
            values + (per_page, (page - 1) * per_page),
        ).fetchall()
        return {
            "items": [dict(row) for row in rows],
            "total": total,
            "page": page,
            "per_page": per_page,
        }

    def update_status(
        self,
        registration_id: int,
        new_status: str,
        reviewer_user_id: int | None = None,
        *,
        commit: bool = True,
    ) -> dict | None:
        """更新报名状态。

        reviewer_user_id 仅用于 Organizer 审核动作。Rider withdraw 时保留原审核信息，
        避免把退赛误记为一次匿名审核。
        """
        db = get_db()
        if reviewer_user_id is None:
            db.execute(
                """UPDATE registrations
                   SET status = ?, updated_at = datetime('now')
                   WHERE id = ?""",
                (new_status, registration_id),
            )
        else:
            db.execute(
                """UPDATE registrations
                   SET status = ?, reviewed_at = datetime('now'),
                       reviewed_by_user_id = ?, updated_at = datetime('now')
                   WHERE id = ?""",
                (new_status, reviewer_user_id, registration_id),
            )
        if commit:
            db.commit()
        return self.find_by_id(registration_id)
