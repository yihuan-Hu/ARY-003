from app.database import get_db
from app.dao.registration_dao import RegistrationDAO
from app.dao.race_project_dao import RaceProjectDAO
from app.dao.race_dao import RaceDAO
from app.utils.errors import (
    NotFoundError,
    InvalidStateError,
    ConflictError,
    ForbiddenError,
)


class RegistrationService:
    def __init__(self):
        self.dao = RegistrationDAO()
        self.race_project_dao = RaceProjectDAO()
        self.race_dao = RaceDAO()

    def submit(self, race_id: int, user_id: int) -> dict:
        """Rider 提交报名"""
        # 检查 Race 是否存在且可报名
        race = self.race_dao.find_by_id(race_id)
        if race is None:
            raise NotFoundError("Race not found")
        if race["status"] not in ("upcoming", "open"):
            raise InvalidStateError(f"Cannot register for race in '{race['status']}' status")

        # 检查是否已有报名（数据库 UNIQUE 约束会兜底）
        existing = self.dao.find_by_race_and_user(race_id, user_id)
        if existing:
            raise ConflictError("You have already registered for this race")

        return self.dao.create(race_id, user_id)

    def approve_registration(self, registration_id: int, reviewer_user_id: int) -> dict:
        """
        *** 核心事务入口 ***

        审批报名并幂等生成 RaceProject。

        保证：
        1. 状态更新和 RaceProject 创建在同一事务中
        2. 重复审批不创建第二个 RaceProject（双重幂等）
        3. 只有 submitted → approved 才生成 RaceProject
        """
        db = get_db()

        # 验证 registration 存在
        reg = self.dao.find_by_id(registration_id)
        if reg is None:
            raise NotFoundError("Registration not found")

        # 验证审核者是该 Race 的 Organizer
        race = self.race_dao.find_by_id(reg["race_id"])
        if race is None or race["created_by_user_id"] != reviewer_user_id:
            raise ForbiddenError("Only the race organizer can review this registration")

        # 如果已经 approved，幂等返回已有的 RaceProject
        if reg["status"] == "approved":
            existing_rp = self.race_project_dao.find_by_registration(registration_id)
            return {
                "registration": reg,
                "race_project": existing_rp,
                "idempotent": True,
            }

        # 只有 submitted 状态可以 approve
        if reg["status"] != "submitted":
            raise InvalidStateError(
                f"Cannot approve registration in '{reg['status']}' status. "
                "Only 'submitted' registrations can be approved."
            )

        # === 事务边界：approve + 创建 RaceProject 必须原子 ===
        try:
            # 1. 更新状态
            updated_reg = self.dao.update_status(registration_id, "approved", reviewer_user_id)

            # 2. 幂等检查（双重保险：即使绕过 Service 直接调 DAO，DB UNIQUE 也会拦截）
            existing_rp = self.race_project_dao.find_by_registration(registration_id)
            if existing_rp:
                db.commit()
                return {
                    "registration": updated_reg,
                    "race_project": existing_rp,
                    "idempotent": True,
                }

            # 3. 创建 RaceProject
            race_project = self.race_project_dao.create(registration_id)

            db.commit()
            return {
                "registration": updated_reg,
                "race_project": race_project,
                "idempotent": False,
            }
        except Exception:
            db.rollback()
            raise

    def reject_registration(self, registration_id: int, reviewer_user_id: int) -> dict:
        """拒绝报名"""
        reg = self.dao.find_by_id(registration_id)
        if reg is None:
            raise NotFoundError("Registration not found")

        # 验证审核者是该 Race 的 Organizer
        race = self.race_dao.find_by_id(reg["race_id"])
        if race is None or race["created_by_user_id"] != reviewer_user_id:
            raise ForbiddenError("Only the race organizer can review this registration")

        if reg["status"] not in ("submitted",):
            raise InvalidStateError(
                f"Cannot reject registration in '{reg['status']}' status"
            )

        updated_reg = self.dao.update_status(registration_id, "rejected", reviewer_user_id)

        # rejected 不生成 RaceProject，确认没有
        existing_rp = self.race_project_dao.find_by_registration(registration_id)
        if existing_rp is not None:
            raise InvalidStateError("RaceProject exists for rejected registration—data inconsistency")

        return {"registration": updated_reg}

    def withdraw(self, registration_id: int, user_id: int) -> dict:
        """Rider 退赛"""
        reg = self.dao.find_by_id(registration_id)
        if reg is None:
            raise NotFoundError("Registration not found")

        if reg["user_id"] != user_id:
            raise ForbiddenError("You can only withdraw your own registration")

        if reg["status"] not in ("submitted", "approved"):
            raise InvalidStateError(
                f"Cannot withdraw registration in '{reg['status']}' status"
            )

        updated_reg = self.dao.update_status(registration_id, "withdrawn", None)
        return {"registration": updated_reg}
