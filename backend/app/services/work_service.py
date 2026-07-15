import hashlib
import hmac
from datetime import datetime, timezone

from flask import current_app

from app.dao.race_dao import RaceDAO
from app.dao.race_project_dao import RaceProjectDAO
from app.dao.registration_dao import RegistrationDAO
from app.dao.work_dao import WorkDAO
from app.database import get_db
from app.utils.errors import InvalidStateError, NotFoundError
from app.utils.logging import audit_log


class WorkService:
    SEALED_STATES = {"judging", "completed", "archived"}
    HASH_FIELDS = (
        "title",
        "description",
        "repo_url",
        "demo_url",
        "video_url",
        "cover_image_url",
        "screenshot_urls",
        "readme_body",
    )

    def __init__(self):
        self.dao = WorkDAO()
        self.race_project_dao = RaceProjectDAO()
        self.registration_dao = RegistrationDAO()
        self.race_dao = RaceDAO()

    def _context_for_project(self, race_project_id: int, user_id: int):
        project = self.race_project_dao.find_by_id(race_project_id)
        if project is None:
            raise NotFoundError("RaceProject not found")
        registration = self.registration_dao.find_by_id(project["registration_id"])
        if registration is None or registration["user_id"] != user_id:
            raise NotFoundError("RaceProject not found")
        race = self.race_dao.find_by_id(registration["race_id"])
        if race is None:
            raise NotFoundError("Race not found")
        return project, registration, race

    def _context_for_work(self, work_id: int, user_id: int):
        work = self.dao.find_by_id(work_id)
        if work is None:
            raise NotFoundError("Work not found")
        project, registration, race = self._context_for_project(
            work["race_project_id"], user_id
        )
        return work, project, registration, race

    def _require_unsealed(self, race: dict) -> None:
        if race["status"] in self.SEALED_STATES:
            raise InvalidStateError("Works are sealed once judging begins")

    def _compute_content_hash(self, work: dict, prev_hash: str | None) -> str:
        data = "|".join(str(work.get(field) or "") for field in self.HASH_FIELDS)
        if prev_hash:
            data += "|" + prev_hash
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    def _compute_commitment(self, content_hash: str) -> str:
        secret = current_app.config["SUBMISSION_SECRET"]
        return hmac.new(
            secret.encode("utf-8"),
            content_hash.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def create_draft(self, race_project_id: int, user_id: int, data: dict) -> dict:
        db = get_db()
        try:
            db.execute("BEGIN IMMEDIATE")
            _, _, race = self._context_for_project(race_project_id, user_id)
            self._require_unsealed(race)
            fields = dict(data)
            title = fields.pop("title")
            work = self.dao.create_draft_uncommitted(
                race_project_id, title, **fields
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        audit_log("work.create", user_id, "work", work["id"], "Draft created")
        return work

    def update(self, work_id: int, user_id: int, data: dict) -> dict:
        db = get_db()
        try:
            db.execute("BEGIN IMMEDIATE")
            _, _, _, race = self._context_for_work(work_id, user_id)
            self._require_unsealed(race)
            updated = self.dao.update_content_uncommitted(work_id, data)
            db.commit()
        except Exception:
            db.rollback()
            raise
        audit_log("work.update", user_id, "work", work_id, "Work draft updated")
        return updated

    def submit(self, work_id: int, user_id: int) -> dict:
        db = get_db()
        try:
            db.execute("BEGIN IMMEDIATE")
            work, project, _, race = self._context_for_work(work_id, user_id)
            if race["status"] != "submitting":
                raise InvalidStateError(
                    "Submissions are only accepted during 'submitting'. "
                    "Works are sealed once judging begins."
                )
            if work["work_status"] != "draft":
                raise InvalidStateError(f"Work is already {work['work_status']}")
            self._require_before_deadline(race.get("submission_deadline"))

            prev_hash = work.get("content_hash") or None
            content_hash = self._compute_content_hash(work, prev_hash)
            commitment = self._compute_commitment(content_hash)
            updated = self.dao.mark_submitted_uncommitted(
                work_id, content_hash, commitment, prev_hash
            )
            db.execute(
                """INSERT INTO integrity_log
                   (event_type, resource_type, resource_id, actor_user_id,
                    content_hash, prev_hash, commitment)
                   VALUES ('work.submit', 'work', ?, ?, ?, ?, ?)""",
                (work_id, user_id, content_hash, prev_hash, commitment),
            )
            db.execute(
                """UPDATE race_projects
                   SET primary_work_id = COALESCE(primary_work_id, ?),
                       updated_at = datetime('now') WHERE id = ?""",
                (work_id, project["id"]),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        audit_log(
            "work.submit",
            user_id,
            "work",
            work_id,
            f"Submitted v{updated['version']}",
        )
        return updated

    def delete(self, work_id: int, user_id: int) -> bool:
        db = get_db()
        try:
            db.execute("BEGIN IMMEDIATE")
            _, project, _, race = self._context_for_work(work_id, user_id)
            self._require_unsealed(race)
            db.execute(
                """UPDATE race_projects SET primary_work_id=NULL,
                          updated_at=datetime('now')
                   WHERE id=? AND primary_work_id=?""",
                (project["id"], work_id),
            )
            deleted = self.dao.delete_uncommitted(work_id)
            db.commit()
        except Exception:
            db.rollback()
            raise
        audit_log("work.delete", user_id, "work", work_id, "Work deleted")
        return deleted

    @staticmethod
    def _require_before_deadline(deadline: str | None) -> None:
        if not deadline:
            return
        parsed = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > parsed.astimezone(timezone.utc):
            raise InvalidStateError("Submission deadline has passed")
