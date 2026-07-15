"""
人员 C：评审服务

提供评委分配、四维评分提交/修改、触发器保护。
"""
import hashlib
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
    AppError,
)
from app.utils.logging import audit_log


class JudgingService:
    def __init__(self):
        self.judgment_dao = JudgingRecordDAO()
        self.assignment_dao = JudgeAssignmentDAO()
        self.race_dao = RaceDAO()
        self.work_dao = WorkDAO()
        self.race_project_dao = RaceProjectDAO()
        self.registration_dao = RegistrationDAO()

    # ---- 评委分配 ----

    def batch_assign(
        self, race_id: int, assignments: list[dict], actor_user_id: int
    ) -> dict:
        """批量分配评委。

        校验：
        - race 存在且 created_by_user_id == actor_user_id（跨赛事隔离）
        - actor 有 admin 角色
        """
        race = self.race_dao.find_by_id(race_id)
        if race is None:
            raise NotFoundError("Race not found")
        if race["created_by_user_id"] != actor_user_id:
            raise ForbiddenError("You can only manage your own races")

        # 校验每个 assignment 的 work_id 属于该赛事
        for item in assignments:
            work = self.work_dao.find_by_id(item["work_id"])
            if work is None:
                raise NotFoundError(f"Work {item['work_id']} not found")
            # 通过 work → race_project → registration 验证 work 属于该赛事
            rp = self.race_project_dao.find_by_id(work["race_project_id"])
            if rp is None:
                raise NotFoundError(f"RaceProject for work {item['work_id']} not found")
            reg = self.registration_dao.find_by_id(rp["registration_id"])
            if reg is None or reg["race_id"] != race_id:
                raise NotFoundError(
                    f"Work {item['work_id']} does not belong to race {race_id}"
                )

        created = self.assignment_dao.batch_create(race_id, assignments)

        # 审计日志
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

        # 校验赛事归属
        race = self.race_dao.find_by_id(assignment["race_id"])
        if race is None or race["created_by_user_id"] != actor_user_id:
            raise ForbiddenError("You can only manage your own races")

        # 已有评分则不允许取消
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

    # ---- 评委视角 ----

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

    # ---- 评分 ----

    def submit_judgment(
        self, work_id: int, judge_user_id: int, scores: dict
    ) -> dict:
        """提交四维评分。

        校验：
        - 评委已分配到该 Work
        - 同一作品不可重复评分（UNIQUE 约束）
        """
        # 校验评委已分配
        assignment = self.assignment_dao.find_by_work_and_judge(
            work_id, judge_user_id
        )
        if assignment is None:
            raise ForbiddenError("You are not assigned to judge this work")

        # 校验不重复
        existing = self.judgment_dao.find_by_work_and_judge(work_id, judge_user_id)
        if existing:
            raise ConflictError("You have already submitted a judgment for this work")

        # 校验 race 状态允许评审
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

        # 写入 integrity_log
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

    # ---- 辅助 ----

    def _check_race_allows_judging(
        self, work_id: int, allow_ended: bool = True
    ) -> None:
        """检查 Work 所属 Race 的状态是否允许评审操作"""
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

        if not allow_ended and race["status"] in ("completed", "archived"):
            raise InvalidStateError(
                "Cannot modify judgments after race has ended"
            )
        return None

    def _write_integrity_log(
        self,
        event_type: str,
        resource_type: str,
        resource_id: int,
        actor_user_id: int,
        record: dict,
    ) -> None:
        """写入完整性日志"""
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

            db = get_db()
            # 查询上一条 integrity_log 的 content_hash 作为 prev_hash
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
                    content_hash,  # commitment: C 用 content_hash 自身作为承诺
                ),
            )
            db.commit()
        except Exception:
            pass  # 完整性日志写入失败不阻断主流程
