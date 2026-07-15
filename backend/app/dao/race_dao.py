from app.database import get_db


class RaceDAO:
    EDITABLE_FIELDS = {
        "name", "description", "start_time", "end_time", "rules", "schedule",
        "theme", "organizer_name", "ca_policy", "ca_policy_config",
        "submission_deadline", "judging_deadline", "judging_mode",
        "judging_tiebreaker",
    }

    def create(
        self,
        name: str,
        created_by_user_id: int,
        *,
        commit: bool = True,
        **kwargs,
    ) -> dict:
        db = get_db()
        cursor = db.execute(
            """INSERT INTO races (
                   name, slug, status, description, rules, schedule, visibility,
                   created_by_user_id, theme, organizer_name, start_time, end_time,
                   submission_deadline, judging_deadline, judging_mode,
                   judging_tiebreaker, ca_policy, ca_policy_config,
                   created_at, updated_at
               ) VALUES (
                   ?, ?, 'draft', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                   datetime('now'), datetime('now')
               )""",
            (
                name,
                kwargs.get("slug", name.lower().replace(" ", "-")),
                kwargs.get("description", ""),
                kwargs.get("rules", ""),
                kwargs.get("schedule", ""),
                kwargs.get("visibility", "private"),
                created_by_user_id,
                kwargs.get("theme", ""),
                kwargs.get("organizer_name", ""),
                kwargs.get("start_time"),
                kwargs.get("end_time"),
                kwargs.get("submission_deadline"),
                kwargs.get("judging_deadline"),
                kwargs.get("judging_mode", "blind"),
                kwargs.get("judging_tiebreaker", "avg"),
                kwargs.get("ca_policy", "rider_choice"),
                kwargs.get("ca_policy_config", "{}"),
            ),
        )
        if commit:
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

    def paginate_by_organizer(
        self, user_id: int, page: int = 1, per_page: int = 20
    ) -> dict:
        db = get_db()
        total = db.execute(
            "SELECT COUNT(*) AS count FROM races WHERE created_by_user_id = ?",
            (user_id,),
        ).fetchone()["count"]
        rows = db.execute(
            """SELECT * FROM races WHERE created_by_user_id = ?
               ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?""",
            (user_id, per_page, (page - 1) * per_page),
        ).fetchall()
        return {
            "items": [dict(row) for row in rows],
            "total": total,
            "page": page,
            "per_page": per_page,
        }

    def update_status(
        self, race_id: int, status: str, *, commit: bool = True
    ) -> dict | None:
        db = get_db()
        db.execute(
            "UPDATE races SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (status, race_id),
        )
        if commit:
            db.commit()
        return self.find_by_id(race_id)

    def update_fields(
        self, race_id: int, fields: dict, *, commit: bool = True
    ) -> dict | None:
        values = {key: value for key, value in fields.items() if key in self.EDITABLE_FIELDS}
        if not values:
            return self.find_by_id(race_id)
        assignments = ", ".join(f"{key} = ?" for key in values)
        db = get_db()
        db.execute(
            f"UPDATE races SET {assignments}, updated_at = datetime('now') WHERE id = ?",
            tuple(values.values()) + (race_id,),
        )
        if commit:
            db.commit()
        return self.find_by_id(race_id)
