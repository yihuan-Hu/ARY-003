from app.dao.announcement_dao import AnnouncementDAO
from app.dao.race_dao import RaceDAO
from app.database import get_db
from app.utils.errors import ForbiddenError, NotFoundError
from app.utils.logging import audit_log


class AnnouncementService:
    def __init__(self):
        self.dao = AnnouncementDAO()
        self.race_dao = RaceDAO()

    def _require_race_owner(self, race_id: int, user_id: int) -> dict:
        race = self.race_dao.find_by_id(race_id)
        if race is None:
            raise NotFoundError("Race not found")
        if race["created_by_user_id"] != user_id:
            raise ForbiddenError("You can only manage your own races")
        return race

    def _require_announcement_owner(
        self, announcement_id: int, user_id: int
    ) -> dict:
        announcement = self.dao.find_by_id(announcement_id)
        if announcement is None:
            raise NotFoundError("Announcement not found")
        self._require_race_owner(announcement["race_id"], user_id)
        return announcement

    def create(self, race_id: int, user_id: int, data: dict) -> dict:
        db = get_db()
        try:
            db.execute("BEGIN IMMEDIATE")
            self._require_race_owner(race_id, user_id)
            announcement = self.dao.create_uncommitted(
                race_id, user_id, data["title"], data.get("body", "")
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        audit_log(
            "announcement.create", user_id, "announcement",
            announcement["id"], "Announcement created",
        )
        return announcement

    def update(self, announcement_id: int, user_id: int, data: dict) -> dict:
        db = get_db()
        try:
            db.execute("BEGIN IMMEDIATE")
            self._require_announcement_owner(announcement_id, user_id)
            announcement = self.dao.update_uncommitted(announcement_id, data)
            db.commit()
        except Exception:
            db.rollback()
            raise
        audit_log(
            "announcement.update", user_id, "announcement",
            announcement_id, "Announcement updated",
        )
        return announcement

    def set_visibility(
        self, announcement_id: int, user_id: int, visibility: str
    ) -> dict:
        db = get_db()
        try:
            db.execute("BEGIN IMMEDIATE")
            self._require_announcement_owner(announcement_id, user_id)
            announcement = self.dao.set_visibility_uncommitted(
                announcement_id, visibility
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        action = "publish" if visibility == "public" else "hide"
        audit_log(
            f"announcement.{action}", user_id, "announcement",
            announcement_id, f"Announcement visibility set to {visibility}",
        )
        return announcement

    def delete(self, announcement_id: int, user_id: int) -> bool:
        db = get_db()
        try:
            db.execute("BEGIN IMMEDIATE")
            self._require_announcement_owner(announcement_id, user_id)
            deleted = self.dao.delete_uncommitted(announcement_id)
            db.commit()
        except Exception:
            db.rollback()
            raise
        audit_log(
            "announcement.delete", user_id, "announcement",
            announcement_id, "Announcement deleted",
        )
        return deleted
