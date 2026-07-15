"""
人员 C：奖项服务

提供奖项 CRUD + 跨赛事隔离校验。
"""
from app.dao.award_dao import AwardDAO
from app.dao.race_dao import RaceDAO
from app.dao.registration_dao import RegistrationDAO
from app.database import get_db
from app.utils.errors import (
    NotFoundError,
    ForbiddenError,
    InvalidStateError,
)
from app.utils.logging import audit_log


class AwardService:
    def __init__(self):
        self.award_dao = AwardDAO()
        self.race_dao = RaceDAO()

    def _check_race_ownership(self, race_id: int, user_id: int) -> dict:
        """校验赛事归属，返回 race dict 或 raise"""
        race = self.race_dao.find_by_id(race_id)
        if race is None:
            raise NotFoundError("Race not found")
        if race["created_by_user_id"] != user_id:
            raise ForbiddenError("You can only manage your own races")
        return race

    def create(self, race_id: int, user_id: int, data: dict) -> dict:
        """创建奖项"""
        race = self._check_race_ownership(race_id, user_id)

        award = self.award_dao.create(
            race_id=race_id,
            title=data["title"],
            position=data["position"],
            work_id=data.get("work_id"),
            registration_id=data.get("registration_id"),
            description=data.get("description", ""),
        )

        audit_log(
            "award.create",
            user_id,
            "award",
            award["id"],
            f"Created award '{data['title']}' for race {race_id}",
        )
        return award

    def update(self, award_id: int, user_id: int, data: dict) -> dict:
        """编辑奖项"""
        award = self.award_dao.find_by_id(award_id)
        if award is None:
            raise NotFoundError("Award not found")

        # 校验赛事归属
        self._check_race_ownership(award["race_id"], user_id)

        update_fields = {}
        for key in ("title", "position", "work_id", "registration_id", "description"):
            if key in data and data[key] is not None:
                update_fields[key] = data[key]

        updated = self.award_dao.update(award_id, **update_fields)

        audit_log(
            "award.update",
            user_id,
            "award",
            award_id,
            f"Updated award for race {award['race_id']}",
        )
        return updated

    def delete(self, award_id: int, user_id: int) -> dict:
        """删除奖项（race 不能是 ended）"""
        award = self.award_dao.find_by_id(award_id)
        if award is None:
            raise NotFoundError("Award not found")

        race = self._check_race_ownership(award["race_id"], user_id)
        if race["status"] in ("completed", "archived"):
            raise InvalidStateError("Cannot delete awards after race has ended")

        self.award_dao.delete(award_id)

        audit_log(
            "award.delete",
            user_id,
            "award",
            award_id,
            f"Deleted award from race {award['race_id']}",
        )
        return {"deleted": True}

    def list_for_race(self, race_id: int, user_id: int) -> list[dict]:
        """管理端奖项列表"""
        self._check_race_ownership(race_id, user_id)
        return self.award_dao.find_by_race(race_id)

    def get_leaderboard(self, race_id: int) -> list[dict]:
        """公开榜单"""
        race = self.race_dao.find_by_id(race_id)
        if race is None or race["status"] == "draft":
            raise NotFoundError("Race not found")
        return self.award_dao.find_leaderboard(race_id)
