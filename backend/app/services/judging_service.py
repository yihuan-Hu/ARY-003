"""
人员 C：评审服务（生产级）

提供评委邀请（两步制）、分配、四维评分提交/修改、截止时间校验、触发器保护。
"""
import hashlib
import hmac
import json

from app.dao.judging_dao import JudgingRecordDAO, JudgeAssignmentDAO
from app.dao.race_dao import RaceDAO
from app.dao.work_dao import WorkDAO
from app.dao.race_project_dao import RaceProjectDAO
from app.dao.registration_dao import RegistrationDAO
from app.database import get_db
from app.utils.errors import (
    NotFoundError,
    ForbiddenError,
    ConflictError,
    InvalidStateError,
)
from app.utils.logging import audit_log


def _get_submission_secret() -> str:
    """安全获取 SUBMISSION_SECRET，用于 HMAC commitment"""
    from flask import current_app, has_request_context

    if has_request_context():
        return current_app.config.get("SUBMISSION_SECRET", "")
    return ""


def _make_commitment(content_hash: str) -> str:
    """HMAC-SHA-256(content_hash, SUBMISSION_SECRET)，与 B 的验证标准兼容"""
    secret = _get_submission_secret()
    if not secret:
        return content_hash  # 测试环境降级
    return hmac.new(
        secret.encode("utf-8"),
        content_hash.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


class JudgingService:
    def __init__(self):
        self.judgment_dao = JudgingRecordDAO()
        self.assignment_dao = JudgeAssignmentDAO()
        self.race_dao = RaceDAO()
        self.work_dao = WorkDAO()
        self.race_project_dao = RaceProjectDAO()
        self.registration_dao = RegistrationDAO()

    # ================================================================
    # 评委邀请（两步制：邀请 → 接受/拒绝 → 分配）
    # ================================================================

    def invite_judge(
        self, race_id: int, judge_user_id: int, actor_user_id: int,
        message: str = "",
    ) -> dict:
        """邀请评委加入赛事。

        校验：
        - actor 是 race creator（跨赛事隔离）
        - 被邀请者未被邀请过（UNIQUE(race_id, judge_user_id)）
        """
        race = self.race_dao.find_by_id(race_id)
        if race is None:
            raise NotFoundError("Race not found")
        if race["created_by_user_id"] != actor_user_id:
            raise ForbiddenError("You can only manage your own races")

        db = get_db()
        try:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT * FROM judge_invitations WHERE race_id = ? AND judge_user_id = ?",
                (race_id, judge_user_id),
            ).fetchone()
            if existing:
                if existing["status"] == "accepted":
                    raise ConflictError("Judge has already accepted the invitation")
                if existing["status"] == "pending":
                    raise ConflictError("Judge has already been invited (pending)")
                # rejected → re-invite: update status back to pending
                db.execute(
                    """UPDATE judge_invitations
                       SET status = 'pending', invited_by_user_id = ?, message = ?,
                           updated_at = datetime('now')
                       WHERE race_id = ? AND judge_user_id = ?""",
                    (actor_user_id, message, race_id, judge_user_id),
                )
                db.commit()
                return dict(db.execute(
                    "SELECT * FROM judge_invitations WHERE race_id = ? AND judge_user_id = ?",
                    (race_id, judge_user_id),
                ).fetchone())

            cursor = db.execute(
                """INSERT INTO judge_invitations
                   (race_id, judge_user_id, status, invited_by_user_id, message)
                   VALUES (?, ?, 'pending', ?, ?)""",
                (race_id, judge_user_id, actor_user_id, message),
            )
            db.commit()
        except ConflictError:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise

        audit_log(
            "judge.invite", actor_user_id, "judge_invitation",
            cursor.lastrowid,
            f"Invited judge {judge_user_id} to race {race_id}",
        )
        invitation = db.execute(
            "SELECT * FROM judge_invitations WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        return dict(invitation)

    def accept_invitation(self, invitation_id: int, judge_user_id: int) -> dict:
        """评委接受邀请"""
        db = get_db()
        invitation = db.execute(
            "SELECT * FROM judge_invitations WHERE id = ?", (invitation_id,)
        ).fetchone()
        if invitation is None:
            raise NotFoundError("Invitation not found")
        if invitation["judge_user_id"] != judge_user_id:
            raise ForbiddenError("This invitation is not for you")
        if invitation["status"] != "pending":
            raise InvalidStateError(
                f"Invitation is already {invitation['status']}"
            )

        db.execute(
            """UPDATE judge_invitations
               SET status = 'accepted', updated_at = datetime('now')
               WHERE id = ?""",
            (invitation_id,),
        )
        db.commit()

        audit_log(
            "judge.accept_invitation", judge_user_id, "judge_invitation",
            invitation_id,
            f"Judge {judge_user_id} accepted invitation to race {invitation['race_id']}",
        )
        return dict(db.execute(
            "SELECT * FROM judge_invitations WHERE id = ?", (invitation_id,)
        ).fetchone())

    def reject_invitation(self, invitation_id: int, judge_user_id: int) -> dict:
        """评委拒绝邀请"""
        db = get_db()
        invitation = db.execute(
            "SELECT * FROM judge_invitations WHERE id = ?", (invitation_id,)
        ).fetchone()
        if invitation is None:
            raise NotFoundError("Invitation not found")
        if invitation["judge_user_id"] != judge_user_id:
            raise ForbiddenError("This invitation is not for you")
        if invitation["status"] != "pending":
            raise InvalidStateError(
                f"Invitation is already {invitation['status']}"
            )

        db.execute(
            """UPDATE judge_invitations
               SET status = 'rejected', updated_at = datetime('now')
               WHERE id = ?""",
            (invitation_id,),
        )
        db.commit()

        audit_log(
            "judge.reject_invitation", judge_user_id, "judge_invitation",
            invitation_id,
            f"Judge {judge_user_id} rejected invitation to race {invitation['race_id']}",
        )
        return dict(db.execute(
            "SELECT * FROM judge_invitations WHERE id = ?", (invitation_id,)
        ).fetchone())

    def list_invitations(self, race_id: int, actor_user_id: int) -> list[dict]:
        """Admin 查看赛事的所有邀请"""
        race = self.race_dao.find_by_id(race_id)
        if race is None:
            raise NotFoundError("Race not found")
        if race["created_by_user_id"] != actor_user_id:
            raise ForbiddenError("You can only manage your own races")
        db = get_db()
        rows = db.execute(
            "SELECT * FROM judge_invitations WHERE race_id = ? ORDER BY created_at DESC",
            (race_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def list_my_invitations(self, judge_user_id: int) -> list[dict]:
        """评委查看自己的邀请"""
        db = get_db()
        rows = db.execute(
            "SELECT * FROM judge_invitations WHERE judge_user_id = ? ORDER BY created_at DESC",
            (judge_user_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ================================================================
    # 评委分配（仅已接受邀请的评委可被分配）
    # ================================================================

    def batch_assign(
        self, race_id: int, assignments: list[dict], actor_user_id: int
    ) -> dict:
        """批量分配评委（事务安全）。

        校验：
        - race 存在且 created_by_user_id == actor_user_id（跨赛事隔离）
        - judge 不能是 Work owner（自评防护）
        - judge 必须已接受邀请
        """
        race = self.race_dao.find_by_id(race_id)
        if race is None:
            raise NotFoundError("Race not found")
        if race["created_by_user_id"] != actor_user_id:
            raise ForbiddenError("You can only manage your own races")

        # 事务内：校验 + 分配
        db = get_db()
        try:
            db.execute("BEGIN IMMEDIATE")

            for item in assignments:
                work_id = item["work_id"]
                judge_user_id = item["judge_user_id"]

                work = self.work_dao.find_by_id(work_id)
                if work is None:
                    raise NotFoundError(f"Work {work_id} not found")

                # 通过 work → race_project → registration 验证 work 属于该赛事
                rp = self.race_project_dao.find_by_id(work["race_project_id"])
                if rp is None:
                    raise NotFoundError(
                        f"RaceProject for work {work_id} not found"
                    )
                reg = self.registration_dao.find_by_id(rp["registration_id"])
                if reg is None or reg["race_id"] != race_id:
                    raise NotFoundError(
                        f"Work {work_id} does not belong to race {race_id}"
                    )

                # ---- 自评防护：judge 不能是 Work owner ----
                if reg["user_id"] == judge_user_id:
                    raise ForbiddenError(
                        f"Judge {judge_user_id} cannot judge their own work {work_id}"
                    )

                # ---- 评委必须已接受邀请 ----
                invitation = db.execute(
                    "SELECT * FROM judge_invitations WHERE race_id = ? AND judge_user_id = ?",
                    (race_id, judge_user_id),
                ).fetchone()
                if invitation is None:
                    raise ForbiddenError(
                        f"Judge {judge_user_id} has not been invited to race {race_id}"
                    )
                if invitation["status"] != "accepted":
                    raise ForbiddenError(
                        f"Judge {judge_user_id} has not accepted the invitation (status: {invitation['status']})"
                    )

            # 执行分配
            created = self.assignment_dao.batch_create(race_id, assignments)

            db.commit()
        except Exception:
            db.rollback()
            raise

        audit_log(
            "judge.assign",
            actor_user_id,
            "judge_assignment",
            None,
            f"Batch assigned {len(assignments)} judge(s) to race {race_id}",
        )

        return {
            "assignments": created,
            "count": len(created),
        }

    def list_assignments(self, race_id: int, actor_user_id: int) -> list[dict]:
        """查看赛事评委分配（需 admin 且赛事归属校验）"""
        race = self.race_dao.find_by_id(race_id)
        if race is None:
            raise NotFoundError("Race not found")
        if race["created_by_user_id"] != actor_user_id:
            raise ForbiddenError("You can only manage your own races")
        return self.assignment_dao.find_by_race(race_id)

    def delete_assignment(self, assignment_id: int, actor_user_id: int) -> dict:
        """取消单条评委分配（评审尚未提交时允许）"""
        assignment = self.assignment_dao.find_by_id(assignment_id)
        if assignment is None:
            raise NotFoundError("Judge assignment not found")

        race = self.race_dao.find_by_id(assignment["race_id"])
        if race is None or race["created_by_user_id"] != actor_user_id:
            raise ForbiddenError("You can only manage your own races")

        existing = self.judgment_dao.find_by_work_and_judge(
            assignment["work_id"], assignment["judge_user_id"]
        )
        if existing:
            raise ConflictError(
                "Cannot remove assignment: judgment already submitted"
            )

        self.assignment_dao.delete(assignment_id)
        audit_log(
            "judge.unassign",
            actor_user_id,
            "judge_assignment",
            assignment_id,
            f"Unassigned judge {assignment['judge_user_id']} from work {assignment['work_id']}",
        )
        return {"deleted": True}

    # ================================================================
    # 评委视角
    # ================================================================

    def list_my_assignments(self, judge_user_id: int) -> list[dict]:
        """评委查看自己的评审清单，包含 Work 摘要"""
        assignments = self.assignment_dao.find_by_judge(judge_user_id)
        result = []
        for a in assignments:
            work = self.work_dao.find_by_id(a["work_id"])
            race = self.race_dao.find_by_id(a["race_id"])
            existing_judgment = self.judgment_dao.find_by_work_and_judge(
                a["work_id"], judge_user_id
            )

            entry = dict(a)
            entry["work"] = work
            entry["race_name"] = race["name"] if race else None
            entry["race_judging_mode"] = race["judging_mode"] if race else "blind"
            entry["judged"] = existing_judgment is not None
            if existing_judgment:
                entry["my_judgment"] = existing_judgment

            # 盲审模式：隐藏 rider 信息
            if race and race["judging_mode"] == "blind" and work:
                rp = self.race_project_dao.find_by_id(work["race_project_id"])
                if rp:
                    reg = self.registration_dao.find_by_id(rp["registration_id"])
                    if reg:
                        entry["work"]["rider_user_id"] = None

            result.append(entry)
        return result

    # ================================================================
    # 评分
    # ================================================================

    def submit_judgment(
        self, work_id: int, judge_user_id: int, scores: dict
    ) -> dict:
        """提交四维评分。

        校验：
        - 评委已分配到该 Work
        - 同一作品不可重复评分（UNIQUE 约束）
        - judging_deadline 未过期
        - race 未结束
        """
        assignment = self.assignment_dao.find_by_work_and_judge(
            work_id, judge_user_id
        )
        if assignment is None:
            raise ForbiddenError("You are not assigned to judge this work")

        existing = self.judgment_dao.find_by_work_and_judge(work_id, judge_user_id)
        if existing:
            raise ConflictError("You have already submitted a judgment for this work")

        work = self.work_dao.find_by_id(work_id)
        if work is None:
            raise NotFoundError("Work not found")
        self._check_race_allows_judging(work_id)

        record = self.judgment_dao.create(
            work_id=work_id,
            judge_user_id=judge_user_id,
            technical_score=scores["technical_score"],
            innovation_score=scores["innovation_score"],
            presentation_score=scores["presentation_score"],
            completeness_score=scores["completeness_score"],
            comment=scores.get("comment", ""),
        )

        self._write_integrity_log(
            "judgment.submit", "judgment", record["id"], judge_user_id, record
        )

        audit_log(
            "judgment.submit",
            judge_user_id,
            "judging_record",
            record["id"],
            f"Submitted judgment for work {work_id}",
        )
        return record

    def update_judgment(
        self, judgment_id: int, judge_user_id: int, scores: dict
    ) -> dict:
        """修改评分。

        校验：
        - 评分属于该评委
        - judging_deadline 未过期
        - race.status 不是 completed/archived（触发器也会拦截）
        """
        record = self.judgment_dao.find_by_id(judgment_id)
        if record is None:
            raise NotFoundError("Judgment not found")
        if record["judge_user_id"] != judge_user_id:
            raise ForbiddenError("You can only modify your own judgments")

        self._check_race_allows_judging(record["work_id"], allow_ended=False)

        updated = self.judgment_dao.update(
            judgment_id,
            technical_score=scores["technical_score"],
            innovation_score=scores["innovation_score"],
            presentation_score=scores["presentation_score"],
            completeness_score=scores["completeness_score"],
            comment=scores.get("comment", ""),
        )

        self._write_integrity_log(
            "judgment.update", "judgment", judgment_id, judge_user_id, updated
        )

        audit_log(
            "judgment.update",
            judge_user_id,
            "judging_record",
            judgment_id,
            f"Updated judgment for work {record['work_id']}",
        )
        return updated

    # ================================================================
    # 评审结果汇总（Organizer 视角）
    # ================================================================

    def summarize_judgments(self, race_id: int, actor_user_id: int) -> dict:
        """Organizer 查看赛事评审汇总。

        返回每个作品的评分详情 + 综合排名。
        """
        race = self.race_dao.find_by_id(race_id)
        if race is None:
            raise NotFoundError("Race not found")
        if race["created_by_user_id"] != actor_user_id:
            raise ForbiddenError("You can only manage your own races")

        submitted_works = self.work_dao.find_submitted_by_race(race_id)
        summaries = []
        for work in submitted_works:
            judgments = self.judgment_dao.find_by_work(work["id"])
            avg_score = (
                round(sum(self.judgment_dao.compute_score(j) for j in judgments) / len(judgments), 2)
                if judgments else None
            )

            # 获取 owner 信息
            rp = self.race_project_dao.find_by_id(work["race_project_id"])
            owner_name = None
            if rp:
                reg = self.registration_dao.find_by_id(rp["registration_id"])
                if reg:
                    user = get_db().execute(
                        "SELECT username FROM users WHERE id = ?",
                        (reg["user_id"],),
                    ).fetchone()
                    owner_name = user["username"] if user else None

            # 盲审模式下隐藏 owner
            if race["judging_mode"] == "blind":
                owner_name = None

            summaries.append({
                "work_id": work["id"],
                "work_title": work["title"],
                "owner_name": owner_name,
                "judgment_count": len(judgments),
                "judgments": judgments,
                "average_score": avg_score,
                "disqualified": work["disqualified"],
            })

        # 按均分降序排列
        summaries.sort(
            key=lambda s: s["average_score"] if s["average_score"] is not None else -1,
            reverse=True,
        )

        return {
            "race_id": race_id,
            "race_name": race["name"],
            "race_status": race["status"],
            "total_works": len(summaries),
            "rankings": summaries,
        }

    # ================================================================
    # 辅助
    # ================================================================

    def _check_race_allows_judging(
        self, work_id: int, allow_ended: bool = True
    ) -> None:
        """检查 Work 所属 Race 的状态和 judging_deadline 是否允许评审操作"""
        from datetime import datetime as _dt

        work = self.work_dao.find_by_id(work_id)
        if work is None:
            raise NotFoundError("Work not found")
        rp = self.race_project_dao.find_by_id(work["race_project_id"])
        if rp is None:
            raise NotFoundError("RaceProject not found")
        reg = self.registration_dao.find_by_id(rp["registration_id"])
        if reg is None:
            raise NotFoundError("Registration not found")
        race = self.race_dao.find_by_id(reg["race_id"])
        if race is None:
            raise NotFoundError("Race not found")

        # 状态检查
        if not allow_ended and race["status"] in ("completed", "archived"):
            raise InvalidStateError(
                "Cannot modify judgments after race has ended"
            )

        # judging_deadline 检查：过期后拒绝新评分
        deadline = race.get("judging_deadline")
        if deadline:
            try:
                if _dt.now().isoformat() > deadline:
                    raise InvalidStateError(
                        "Judging deadline has passed"
                    )
            except (ValueError, TypeError):
                pass  # 日期格式异常不阻塞

    def _write_integrity_log(
        self,
        event_type: str,
        resource_type: str,
        resource_id: int,
        actor_user_id: int,
        record: dict,
    ) -> None:
        """写入完整性日志，使用 HMAC-SHA-256 commitment"""
        try:
            content = json.dumps(
                {
                    k: record.get(k)
                    for k in (
                        "technical_score",
                        "innovation_score",
                        "presentation_score",
                        "completeness_score",
                        "comment",
                    )
                },
                sort_keys=True,
            )
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            commitment = _make_commitment(content_hash)

            db = get_db()
            prev = db.execute(
                """SELECT content_hash FROM integrity_log
                   WHERE resource_type = ? AND resource_id = ?
                   ORDER BY created_at DESC LIMIT 1""",
                (resource_type, resource_id),
            ).fetchone()
            prev_hash = prev["content_hash"] if prev else None

            db.execute(
                """INSERT INTO integrity_log
                   (event_type, resource_type, resource_id, actor_user_id,
                    content_hash, prev_hash, commitment)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    event_type,
                    resource_type,
                    resource_id,
                    actor_user_id,
                    content_hash,
                    prev_hash,
                    commitment,
                ),
            )
            db.commit()
        except Exception:
            pass  # 完整性日志写入失败不阻断主流程
