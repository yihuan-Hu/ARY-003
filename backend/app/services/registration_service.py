import sqlite3

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
from app.utils.logging import audit_log


class RegistrationService:
    """Registration 业务状态机。

    CAConnection / RaceProject 接入健康度不属于本状态机，任何 CA 状态都不会触发
    Registration 自动 withdrawn。
    """

    STATUS_SUBMITTED = "submitted"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_WITHDRAWN = "withdrawn"
    VALID_STATUSES = {
        STATUS_SUBMITTED, STATUS_APPROVED, STATUS_REJECTED, STATUS_WITHDRAWN
    }

    ALLOWED_TRANSITIONS = {
        STATUS_SUBMITTED: {
            STATUS_APPROVED,
            STATUS_REJECTED,
            STATUS_WITHDRAWN,
        },
        STATUS_APPROVED: {STATUS_WITHDRAWN},
        STATUS_REJECTED: set(),
        STATUS_WITHDRAWN: set(),
    }

    def __init__(self):
        self.dao = RegistrationDAO()
        self.race_project_dao = RaceProjectDAO()
        self.race_dao = RaceDAO()

    def submit(self, race_id: int, user_id: int) -> dict:
        """Rider 提交报名"""
        # 快速失败检查；真正的状态与重复校验会在写事务内再次执行。
        race = self.race_dao.find_by_id(race_id)
        if race is None:
            raise NotFoundError("Race not found")
        if race["status"] != "registration":
            raise InvalidStateError("Registration is not open for this race")

        # 检查是否已有报名（数据库 UNIQUE 约束会兜底）
        existing = self.dao.find_by_race_and_user(race_id, user_id)
        if existing:
            raise ConflictError("You have already registered for this race")

        db = get_db()
        try:
            # 串行化 Race 状态变更与报名写入，避免预检查后 Race 已结束仍成功报名。
            db.execute("BEGIN IMMEDIATE")
            race = self.race_dao.find_by_id(race_id)
            if race is None:
                raise NotFoundError("Race not found")
            if race["status"] != "registration":
                raise InvalidStateError("Registration is not open for this race")
            if self.dao.find_by_race_and_user(race_id, user_id):
                raise ConflictError("You have already registered for this race")

            registration = self.dao.create(race_id, user_id, commit=False)
            db.commit()
        except sqlite3.IntegrityError as error:
            # 并发请求可能同时通过上面的读取检查，数据库唯一约束是最终防线。
            db.rollback()
            if self.dao.find_by_race_and_user(race_id, user_id):
                raise ConflictError("You have already registered for this race") from error
            raise
        except Exception:
            db.rollback()
            raise
        audit_log(
            "registration.submit", user_id, "registration", registration["id"],
            f"Submitted for race {race_id}",
        )
        return registration

    def get_for_rider(self, registration_id: int, user_id: int) -> dict:
        registration = self.dao.find_by_id(registration_id)
        # 不区分“不存在”和“不属于当前 Rider”，避免通过 404/403 枚举资源。
        if registration is None or registration["user_id"] != user_id:
            raise NotFoundError("Registration not found")
        return registration

    def list_for_rider(
        self, user_id: int, page: int, per_page: int, status: str | None
    ) -> dict:
        self._validate_filter_status(status)
        return self.dao.paginate_by_user(user_id, page, per_page, status)

    def list_for_organizer(
        self,
        race_id: int,
        organizer_user_id: int,
        page: int,
        per_page: int,
        status: str | None,
    ) -> dict:
        race = self.race_dao.find_by_id(race_id)
        if race is None:
            raise NotFoundError("Race not found")
        if race["created_by_user_id"] != organizer_user_id:
            raise ForbiddenError("You can only manage your own races")
        self._validate_filter_status(status)
        return self.dao.paginate_by_race(race_id, page, per_page, status)

    def _validate_filter_status(self, status: str | None) -> None:
        if status and status not in self.VALID_STATUSES:
            from app.utils.errors import ValidationError
            raise ValidationError("Invalid registration status filter")

    def _require_transition(self, current_status: str, target_status: str) -> None:
        allowed_targets = self.ALLOWED_TRANSITIONS.get(current_status, set())
        if target_status not in allowed_targets:
            raise InvalidStateError(
                f"Cannot transition registration from '{current_status}' "
                f"to '{target_status}'"
            )

    def _require_reviewer_scope(self, registration: dict, reviewer_user_id: int) -> None:
        race = self.race_dao.find_by_id(registration["race_id"])
        if race is None or race["created_by_user_id"] != reviewer_user_id:
            raise ForbiddenError("Only the race organizer can review this registration")

    def approve_registration(self, registration_id: int, reviewer_user_id: int) -> dict:
        """
        *** 核心事务入口 ***

        审批报名并幂等生成 RaceProject。

        保证：
        1. 状态更新和 RaceProject 创建在同一事务中
        2. 重复审批不创建第二个 RaceProject（双重幂等）
        3. 只有 submitted → approved 才生成 RaceProject
        """
        reg = self.dao.find_by_id(registration_id)
        if reg is None:
            raise NotFoundError("Registration not found")
        self._require_reviewer_scope(reg, reviewer_user_id)

        # === 事务边界：approve + 创建 RaceProject 必须原子 ===
        db = get_db()
        audit_needed = False
        try:
            # IMMEDIATE 让并发审核串行化；进入事务后重新读取，避免使用陈旧状态。
            db.execute("BEGIN IMMEDIATE")
            reg = self.dao.find_by_id(registration_id)
            self._require_reviewer_scope(reg, reviewer_user_id)

            # 重复 approve 幂等返回；若历史脏数据缺少 RaceProject，则在同一入口补齐。
            if reg["status"] == self.STATUS_APPROVED:
                race_project = self.race_project_dao.find_by_registration(registration_id)
                if race_project is None:
                    race_project = self.race_project_dao.create(
                        registration_id,
                        commit=False,
                    )
                    audit_needed = True
                result = {
                    "registration": reg,
                    "race_project": race_project,
                    "idempotent": True,
                }
            else:
                self._require_transition(reg["status"], self.STATUS_APPROVED)
                updated_reg = self.dao.update_status(
                    registration_id,
                    self.STATUS_APPROVED,
                    reviewer_user_id,
                    commit=False,
                )
                audit_needed = True
                race_project = self.race_project_dao.find_by_registration(
                    registration_id
                )
                idempotent = race_project is not None
                if race_project is None:
                    race_project = self.race_project_dao.create(
                        registration_id,
                        commit=False,
                    )
                result = {
                    "registration": updated_reg,
                    "race_project": race_project,
                    "idempotent": idempotent,
                }
            db.commit()
        except Exception:
            db.rollback()
            raise
        if audit_needed:
            audit_log(
                "registration.approve", reviewer_user_id, "registration",
                registration_id, "Registration approved",
            )
        return result

    def reject_registration(self, registration_id: int, reviewer_user_id: int) -> dict:
        """拒绝报名"""
        reg = self.dao.find_by_id(registration_id)
        if reg is None:
            raise NotFoundError("Registration not found")

        self._require_reviewer_scope(reg, reviewer_user_id)
        self._require_transition(reg["status"], self.STATUS_REJECTED)

        db = get_db()
        try:
            db.execute("BEGIN IMMEDIATE")
            reg = self.dao.find_by_id(registration_id)
            self._require_reviewer_scope(reg, reviewer_user_id)
            self._require_transition(reg["status"], self.STATUS_REJECTED)

            existing_rp = self.race_project_dao.find_by_registration(registration_id)
            if existing_rp is not None:
                raise InvalidStateError(
                    "RaceProject exists for rejected registration—data inconsistency"
                )

            updated_reg = self.dao.update_status(
                registration_id,
                self.STATUS_REJECTED,
                reviewer_user_id,
                commit=False,
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        audit_log(
            "registration.reject", reviewer_user_id, "registration",
            registration_id, "Registration rejected",
        )
        return {"registration": updated_reg}

    def withdraw(self, registration_id: int, user_id: int) -> dict:
        """Rider 退赛"""
        reg = self.dao.find_by_id(registration_id)
        if reg is None or reg["user_id"] != user_id:
            raise NotFoundError("Registration not found")

        self._require_transition(reg["status"], self.STATUS_WITHDRAWN)

        db = get_db()
        try:
            # 与 approve/reject 使用同一写锁策略，并在事务内重读防止 TOCTOU。
            db.execute("BEGIN IMMEDIATE")
            reg = self.dao.find_by_id(registration_id)
            if reg is None or reg["user_id"] != user_id:
                raise NotFoundError("Registration not found")
            self._require_transition(reg["status"], self.STATUS_WITHDRAWN)

            updated_reg = self.dao.update_status(
                registration_id,
                self.STATUS_WITHDRAWN,
                commit=False,
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        audit_log(
            "registration.withdraw", user_id, "registration",
            registration_id, "Registration withdrawn",
        )
        return {"registration": updated_reg}
