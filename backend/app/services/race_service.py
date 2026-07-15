from app.dao.race_dao import RaceDAO
from app.database import get_db
from app.utils.errors import (
    ForbiddenError,
    InvalidStateError,
    NotFoundError,
    ValidationError,
)
from app.utils.logging import audit_log


class RaceService:
    ALLOWED_TRANSITIONS = {
        "draft": {"published"},
        "published": {"registration"},
        "registration": {"running"},
        "running": {"submitting"},
        "submitting": {"judging"},
        "judging": {"completed"},
        "completed": {"archived"},
        "archived": set(),
    }
    EDITABLE_STATES = {"draft", "published", "registration"}

    def __init__(self):
        self.dao = RaceDAO()

    @staticmethod
    def _require_owner(race: dict | None, user_id: int) -> dict:
        if race is None:
            raise NotFoundError("Race not found")
        if race["created_by_user_id"] != user_id:
            raise ForbiddenError("You can only manage your own races")
        return race

    def create(self, user_id: int, data: dict) -> dict:
        payload = dict(data)
        payload.pop("status", None)
        name = payload.pop("name").strip()
        if not name:
            raise ValidationError("Race name cannot be blank")
        if not payload.get("slug"):
            payload["slug"] = name.lower().replace(" ", "-")
        db = get_db()
        try:
            db.execute("BEGIN IMMEDIATE")
            race = self.dao.create(name, user_id, commit=False, **payload)
            db.commit()
        except Exception:
            db.rollback()
            raise
        audit_log("race.create", user_id, "race", race["id"], "Race created as draft")
        return race

    def transition(self, race_id: int, target_status: str, user_id: int) -> dict:
        db = get_db()
        try:
            db.execute("BEGIN IMMEDIATE")
            race = self._require_owner(self.dao.find_by_id(race_id), user_id)
            if target_status not in self.ALLOWED_TRANSITIONS.get(race["status"], set()):
                raise InvalidStateError(
                    f"Cannot transition from {race['status']} to {target_status}"
                )
            updated = self.dao.update_status(race_id, target_status, commit=False)
            db.commit()
        except Exception:
            db.rollback()
            raise
        audit_log(
            f"race.{target_status}", user_id, "race", race_id,
            f"Transitioned from {race['status']} to {target_status}",
        )
        return updated

    def edit(self, race_id: int, user_id: int, data: dict) -> dict:
        payload = dict(data)
        if "name" in payload:
            payload["name"] = payload["name"].strip()
            if not payload["name"]:
                raise ValidationError("Race name cannot be blank")
        db = get_db()
        try:
            db.execute("BEGIN IMMEDIATE")
            race = self._require_owner(self.dao.find_by_id(race_id), user_id)
            if race["status"] not in self.EDITABLE_STATES:
                raise InvalidStateError(
                    "Race can only be edited in draft/published/registration status"
                )
            updated = self.dao.update_fields(race_id, payload, commit=False)
            db.commit()
        except Exception:
            db.rollback()
            raise
        audit_log("race.update", user_id, "race", race_id, "Race details updated")
        return updated
