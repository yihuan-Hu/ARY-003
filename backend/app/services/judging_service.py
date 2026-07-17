"""
人员 C：评审服务（生产级）

提供评委邀请（两步制）、分配、四维评分提交/修改、截止时间校验、触发器保护。
"""
import hashlib
import hmac
import json
import statistics
from datetime import datetime, timezone

from app.dao.judging_dao import JudgingRecordDAO, JudgeAssignmentDAO
from app.dao.race_dao import RaceDAO
from app.dao.work_dao import WorkDAO
from app.dao.race_project_dao import RaceProjectDAO
from app.dao.registration_dao import RegistrationDAO
from app.dao.user_dao import UserDAO
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
        # 生产路径不可裸 hash 降级；测试环境由 TestConfig 注入 SUBMISSION_SECRET
        raise RuntimeError("SUBMISSION_SECRET is not configured — HMAC commitment cannot be produced")
    return hmac.new(
        secret.encode("utf-8"),
        content_hash.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _parse_deadline(deadline_str: str | None):
    """将 deadline 字符串解析为 offset-aware UTC datetime。

    接受的格式：ISO-8601（含时区偏移或 'Z' 后缀），以及无时区的 ISO-8601。
    无时区字符串按 UTC 解析并记录警告。
    返回 None 表示无截止时间；格式错误抛出 InvalidStateError。
    """
    if not deadline_str:
        return None
    try:
        s = deadline_str.strip()
        # Python 3.7+ 的 fromisoformat 对 'Z' 后缀处理不统一，先规范化
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            # 无时区信息，按 UTC 处理
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError) as e:
        raise InvalidStateError(f"Invalid deadline format: {deadline_str}") from e


class JudgingService:
    def __init__(self):
        self.judgment_dao = JudgingRecordDAO()
        self.assignment_dao = JudgeAssignmentDAO()
        self.race_dao = RaceDAO()
        self.work_dao = WorkDAO()
        self.race_project_dao = RaceProjectDAO()
        self.registration_dao = RegistrationDAO()
        self.user_dao = UserDAO()

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

        # 通知受邀者
        try:
            from app.services.notification_service import NotificationService
            ns = NotificationService()
            race_name = race["name"] if race else f"Race #{race_id}"
            ns.send(
                judge_user_id,
                "You've been invited to judge",
                f"You have been invited to judge '{race_name}'. {message}",
                f"/judge/invitations",
            )
        except Exception:
            pass

        return dict(invitation)

    def accept_invitation(self, invitation_id: int, judge_user_id: int) -> dict:
        """评委接受邀请（事务：更新邀请状态 + 追加 judge 角色 + 审计日志 + 通知）。

        只要求登录即可接受；若用户当前 roles 不含 'judge'，自动追加并持久化。
        """
        db = get_db()
        try:
            db.execute("BEGIN IMMEDIATE")
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
                   SET status = 'accepted', responded_at = datetime('now'),
                       updated_at = datetime('now')
                   WHERE id = ?""",
                (invitation_id,),
            )

            # 自动追加 judge 角色
            user = db.execute(
                "SELECT roles FROM users WHERE id = ?", (judge_user_id,)
            ).fetchone()
            if user:
                import json as _json
                roles = _json.loads(user["roles"]) if user["roles"] else []
                if "judge" not in roles:
                    roles.append("judge")
                    db.execute(
                        "UPDATE users SET roles = ?, updated_at = datetime('now') WHERE id = ?",
                        (_json.dumps(roles), judge_user_id),
                    )

            # 通知邀请者
            try:
                from app.services.notification_service import NotificationService
                ns = NotificationService()
                race = self.race_dao.find_by_id(invitation["race_id"])
                race_name = race["name"] if race else f"Race #{invitation['race_id']}"
                ns.send(
                    invitation["invited_by_user_id"],
                    "Judge Invitation Accepted",
                    f"A user has accepted your invitation to judge '{race_name}'.",
                )
            except Exception:
                pass

            db.commit()
        except Exception:
            db.rollback()
            raise

        audit_log(
            "judge.accept_invitation", judge_user_id, "judge_invitation",
            invitation_id,
            f"Judge {judge_user_id} accepted invitation to race {invitation['race_id']}",
        )
        return dict(db.execute(
            "SELECT * FROM judge_invitations WHERE id = ?", (invitation_id,)
        ).fetchone())

    def reject_invitation(self, invitation_id: int, judge_user_id: int) -> dict:
        """评委拒绝邀请（事务安全）"""
        db = get_db()
        try:
            db.execute("BEGIN IMMEDIATE")
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
                   SET status = 'rejected', responded_at = datetime('now'),
                       updated_at = datetime('now')
                   WHERE id = ?""",
                (invitation_id,),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise

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

                # ---- 自评防护：judge 不能是 Work owner（返回 422） ----
                if reg["user_id"] == judge_user_id:
                    raise InvalidStateError(
                        f"Judge {judge_user_id} cannot judge their own work {work_id}"
                    )

                # ---- 评委必须已接受邀请 ----
                invitation = db.execute(
                    "SELECT * FROM judge_invitations WHERE race_id = ? AND judge_user_id = ?",
                    (race_id, judge_user_id),
                ).fetchone()
                if invitation is None:
                    raise InvalidStateError(
                        f"Judge {judge_user_id} has not been invited to race {race_id}"
                    )
                if invitation["status"] != "accepted":
                    raise InvalidStateError(
                        f"该用户尚未接受评审邀请 (status: {invitation['status']})"
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

        # 通知被分配的评委
        try:
            from app.services.notification_service import NotificationService
            ns = NotificationService()
            race_name = race["name"] if race else f"Race #{race_id}"
            for item in assignments:
                ns.send(
                    item["judge_user_id"],
                    "New judging assignment",
                    f"You have been assigned to judge a work in '{race_name}'.",
                    "/judge/assignments",
                )
        except Exception:
            pass

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
        """评委查看自己的评审清单，包含 Work 摘要 + Review Readiness 风险摘要"""
        from app.services.readiness_service import ReviewReadinessService
        readiness_svc = ReviewReadinessService()

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
            is_blind = race and race["judging_mode"] == "blind"
            if is_blind and work:
                rp = self.race_project_dao.find_by_id(work["race_project_id"])
                if rp:
                    reg = self.registration_dao.find_by_id(rp["registration_id"])
                    if reg:
                        entry["work"]["rider_user_id"] = None
                        entry["work"]["rider_name"] = None

            # 附带 Readiness 风险摘要
            try:
                if work:
                    rp = self.race_project_dao.find_by_id(work["race_project_id"])
                    if rp:
                        work_risks = readiness_svc._check_work(work, rp)
                        if is_blind:
                            # 盲审模式下不暴露 rider 特定风险中的敏感信息
                            filtered = []
                            for r in work_risks:
                                if r.get("risk_type") not in ("no_ca_data",):
                                    filtered.append(r)
                            entry["readiness_risks"] = filtered
                        else:
                            entry["readiness_risks"] = work_risks
                    else:
                        entry["readiness_risks"] = []
                else:
                    entry["readiness_risks"] = []
            except Exception:
                entry["readiness_risks"] = []

            result.append(entry)
        return result

    # ================================================================
    # 评分
    # ================================================================

    def submit_judgment(
        self, work_id: int, judge_user_id: int, scores: dict
    ) -> dict:
        """提交四维评分（事务：评分写入 + integrity_log + audit_log）。

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

        db = get_db()
        try:
            db.execute("BEGIN IMMEDIATE")
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
            db.commit()
        except Exception:
            db.rollback()
            raise
        return record

    def update_judgment(
        self, judgment_id: int, judge_user_id: int, scores: dict
    ) -> dict:
        """修改评分（事务安全）。

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

        db = get_db()
        try:
            db.execute("BEGIN IMMEDIATE")
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
            db.commit()
        except Exception:
            db.rollback()
            raise
        return updated

    # ================================================================
    # 评审结果汇总（Organizer 视角）
    # ================================================================

    def summarize_judgments(self, race_id: int, actor_user_id: int) -> dict:
        """Organizer 查看赛事评审汇总。

        返回每个作品的：judge_count / assigned_count / 四维均分 / total_avg / comments。
        """
        race = self.race_dao.find_by_id(race_id)
        if race is None:
            raise NotFoundError("Race not found")
        if race["created_by_user_id"] != actor_user_id:
            raise ForbiddenError("You can only manage your own races")

        submitted_works = self.work_dao.find_submitted_by_race(race_id)
        is_blind = race["judging_mode"] == "blind"
        works_data = []

        for work in submitted_works:
            judgments = self.judgment_dao.find_by_work(work["id"])
            assignments = self.assignment_dao.find_by_work(work["id"])
            assigned_count = len(assignments)
            judge_count = len(judgments)

            # 四维均分
            if judgments:
                tech_avg = round(sum(j["technical_score"] or 0 for j in judgments) / len(judgments), 2)
                innov_avg = round(sum(j["innovation_score"] or 0 for j in judgments) / len(judgments), 2)
                pres_avg = round(sum(j["presentation_score"] or 0 for j in judgments) / len(judgments), 2)
                comp_avg = round(sum(j["completeness_score"] or 0 for j in judgments) / len(judgments), 2)
                total_avg = round((tech_avg + innov_avg + pres_avg + comp_avg) / 4, 2)
            else:
                tech_avg = innov_avg = pres_avg = comp_avg = total_avg = None

            # 获取 owner 信息
            rp = self.race_project_dao.find_by_id(work["race_project_id"])
            owner_name = None
            owner_user_id = None
            if rp:
                reg = self.registration_dao.find_by_id(rp["registration_id"])
                if reg:
                    owner_user_id = reg["user_id"]
                    user = get_db().execute(
                        "SELECT username FROM users WHERE id = ?",
                        (reg["user_id"],),
                    ).fetchone()
                    owner_name = user["username"] if user else None

            # 盲审模式下隐藏 owner
            if is_blind:
                owner_name = None
                owner_user_id = None

            # comments 列表，含 judge_name 和 total
            comments = []
            for j in judgments:
                judge = get_db().execute(
                    "SELECT username FROM users WHERE id = ?",
                    (j["judge_user_id"],),
                ).fetchone()
                comments.append({
                    "judge_name": (judge["username"] if judge else None) if not is_blind else None,
                    "comment": j.get("comment", ""),
                    "total": self.judgment_dao.compute_score(j),
                })

            works_data.append({
                "work_id": work["id"],
                "work_title": work["title"],
                "owner_name": owner_name,
                "owner_user_id": owner_user_id,
                "judge_count": judge_count,
                "assigned_count": assigned_count,
                "dimension_averages": {
                    "technical": tech_avg,
                    "innovation": innov_avg,
                    "presentation": pres_avg,
                    "completeness": comp_avg,
                },
                "total_avg": total_avg,
                "comments": comments,
                "disqualified": work["disqualified"],
                "disqualify_reason": work.get("disqualify_reason", ""),
            })

        # 按 total_avg 降序排列
        works_data.sort(
            key=lambda s: s["total_avg"] if s["total_avg"] is not None else -1,
            reverse=True,
        )

        return {
            "race_id": race_id,
            "race_name": race["name"],
            "race_status": race["status"],
            "judging_mode": race["judging_mode"],
            "tiebreaker": race.get("judging_tiebreaker", "avg"),
            "total_works": len(works_data),
            "works": works_data,
        }

    # ================================================================
    # 辅助
    # ================================================================

    def _check_race_allows_judging(
        self, work_id: int, allow_ended: bool = True
    ) -> None:
        """检查 Work 所属 Race 的状态和 judging_deadline 是否允许评审操作。

        使用明确的 datetime parser，统一处理时区/naive datetime。
        deadline 格式错误时记录日志并抛配置错误，不静默放行。
        """
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

        # judging_deadline 检查：使用 _parse_deadline 解析
        deadline_str = race.get("judging_deadline")
        if deadline_str:
            deadline = _parse_deadline(deadline_str)
            if deadline is not None:
                now = datetime.now(timezone.utc)
                if now > deadline:
                    raise InvalidStateError(
                        "Judging deadline has passed"
                    )

    def _write_integrity_log(
        self,
        event_type: str,
        resource_type: str,
        resource_id: int,
        actor_user_id: int,
        record: dict,
    ) -> None:
        """写入完整性日志，使用 HMAC-SHA-256 commitment。

        注意：此方法在调用方的事务内执行，不自行 commit。
        """
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
            # NOTE: commit 由调用方的事务统一管理
        except Exception:
            pass  # 完整性日志写入失败不阻断主流程

    # ================================================================
    # Disqualify / Restore
    # ================================================================

    def disqualify_work(self, work_id: int, actor_user_id: int, reason: str = "") -> dict:
        """取消作品资格。Organizer 只能操作自己赛事的作品。"""
        work = self.work_dao.find_by_id(work_id)
        if work is None:
            raise NotFoundError("Work not found")

        # 校验赛事归属
        rp = self.race_project_dao.find_by_id(work["race_project_id"])
        if rp is None:
            raise NotFoundError("RaceProject not found")
        reg = self.registration_dao.find_by_id(rp["registration_id"])
        if reg is None:
            raise NotFoundError("Registration not found")
        race = self.race_dao.find_by_id(reg["race_id"])
        if race is None or race["created_by_user_id"] != actor_user_id:
            raise ForbiddenError("You can only manage your own races")

        db = get_db()
        db.execute(
            "UPDATE works SET disqualified = 1, disqualify_reason = ?, updated_at = datetime('now') WHERE id = ?",
            (reason, work_id),
        )
        db.commit()

        audit_log(
            "work.disqualify", actor_user_id, "work", work_id,
            f"Disqualified work {work_id}: {reason}",
        )
        return self.work_dao.find_by_id(work_id)

    def restore_work(self, work_id: int, actor_user_id: int) -> dict:
        """恢复作品资格。"""
        work = self.work_dao.find_by_id(work_id)
        if work is None:
            raise NotFoundError("Work not found")

        # 校验赛事归属
        rp = self.race_project_dao.find_by_id(work["race_project_id"])
        if rp is None:
            raise NotFoundError("RaceProject not found")
        reg = self.registration_dao.find_by_id(rp["registration_id"])
        if reg is None:
            raise NotFoundError("Registration not found")
        race = self.race_dao.find_by_id(reg["race_id"])
        if race is None or race["created_by_user_id"] != actor_user_id:
            raise ForbiddenError("You can only manage your own races")

        db = get_db()
        db.execute(
            "UPDATE works SET disqualified = 0, disqualify_reason = '', updated_at = datetime('now') WHERE id = ?",
            (work_id,),
        )
        db.commit()

        audit_log(
            "work.restore", actor_user_id, "work", work_id,
            f"Restored work {work_id}",
        )
        return self.work_dao.find_by_id(work_id)

    # ================================================================
    # 评委搜索
    # ================================================================

    def search_accounts(self, q: str = "", page: int = 1, per_page: int = 20) -> dict:
        """平台账号搜索，用于选择评委。返回 id, username, github_login。"""
        db = get_db()
        if q:
            total = db.execute(
                "SELECT COUNT(*) AS cnt FROM users WHERE username LIKE ? OR github_login LIKE ?",
                (f"%{q}%", f"%{q}%"),
            ).fetchone()["cnt"]
            rows = db.execute(
                """SELECT id, username, github_login FROM users
                   WHERE username LIKE ? OR github_login LIKE ?
                   ORDER BY username ASC LIMIT ? OFFSET ?""",
                (f"%{q}%", f"%{q}%", per_page, (page - 1) * per_page),
            ).fetchall()
        else:
            total = db.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()["cnt"]
            rows = db.execute(
                "SELECT id, username, github_login FROM users ORDER BY username ASC LIMIT ? OFFSET ?",
                (per_page, (page - 1) * per_page),
            ).fetchall()
        return {
            "items": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "per_page": per_page,
        }
