from app.dao.base import BaseDAO
from app.database import get_db


class WorkDAO(BaseDAO):
    table = "works"

    _draft_fields = {
        "description",
        "repo_url",
        "demo_url",
        "video_url",
        "cover_image_url",
        "screenshot_urls",
        "readme_body",
        "visibility",
    }

    def create_draft(self, race_project_id: int, title: str, **fields) -> dict:
        allowed_fields = {
            key: value
            for key, value in fields.items()
            if key in self._draft_fields
        }
        return self.create(
            race_project_id=race_project_id,
            title=title,
            work_status="draft",
            **allowed_fields,
        )

    def find_by_race_project(self, race_project_id: int) -> list[dict]:
        db = get_db()
        rows = db.execute(
            """SELECT * FROM works
               WHERE race_project_id = ?
               ORDER BY created_at DESC, id DESC""",
            (race_project_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def find_submitted_by_race(self, race_id: int) -> list[dict]:
        db = get_db()
        rows = db.execute(
            """SELECT w.* FROM works w
               JOIN race_projects rp ON w.race_project_id = rp.id
               JOIN registrations reg ON rp.registration_id = reg.id
               WHERE reg.race_id = ?
                 AND w.work_status = 'submitted'
               ORDER BY w.submitted_at DESC, w.id DESC""",
            (race_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def find_public_by_race(self, race_id: int) -> list[dict]:
        db = get_db()
        rows = db.execute(
            """SELECT w.* FROM works w
               JOIN race_projects rp ON w.race_project_id = rp.id
               JOIN registrations reg ON rp.registration_id = reg.id
               WHERE reg.race_id = ?
                 AND w.work_status = 'submitted'
                 AND w.visibility = 'public'
                 AND w.disqualified = 0
               ORDER BY w.submitted_at DESC, w.id DESC""",
            (race_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def mark_submitted(
        self,
        work_id: int,
        content_hash: str,
        content_commitment: str,
        prev_hash: str | None = None,
    ) -> dict | None:
        db = get_db()
        db.execute(
            """UPDATE works
               SET work_status = 'submitted',
                   content_hash = ?,
                   content_commitment = ?,
                   prev_hash = ?,
                   submitted_at = COALESCE(submitted_at, datetime('now')),
                   updated_at = datetime('now')
               WHERE id = ?""",
            (content_hash, content_commitment, prev_hash, work_id),
        )
        db.commit()
        return self.find_by_id(work_id)

    def set_disqualified(self, work_id: int, reason: str) -> dict | None:
        return self.update(
            work_id,
            disqualified=1,
            disqualify_reason=reason,
        )

    def restore(self, work_id: int) -> dict | None:
        return self.update(
            work_id,
            disqualified=0,
            disqualify_reason="",
        )
