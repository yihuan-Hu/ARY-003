"""
人员 C：评审系统 DAO 层

提供 JudgingRecordDAO 和 JudgeAssignmentDAO，
均继承 BaseDAO 获得 find_by_id / create / update / delete / paginate 方法。
"""
from app.dao.base import BaseDAO
from app.database import get_db


class JudgingRecordDAO(BaseDAO):
    table = "judging_records"

    def find_by_work_and_judge(self, work_id: int, judge_user_id: int) -> dict | None:
        """按作品和评委查找已有评分（用于冲突检测）"""
        db = get_db()
        row = db.execute(
            "SELECT * FROM judging_records WHERE work_id = ? AND judge_user_id = ?",
            (work_id, judge_user_id),
        ).fetchone()
        return dict(row) if row else None

    def find_by_work(self, work_id: int) -> list[dict]:
        """查看某作品的所有评分"""
        db = get_db()
        rows = db.execute(
            "SELECT * FROM judging_records WHERE work_id = ? ORDER BY submitted_at DESC",
            (work_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def find_by_race(self, race_id: int) -> list[dict]:
        """查看某赛事下所有作品的评分（JOIN works → race_projects → registrations）"""
        db = get_db()
        rows = db.execute(
            """SELECT jr.* FROM judging_records jr
               JOIN works w ON jr.work_id = w.id
               JOIN race_projects rp ON w.race_project_id = rp.id
               JOIN registrations reg ON rp.registration_id = reg.id
               WHERE reg.race_id = ?
               ORDER BY jr.submitted_at DESC""",
            (race_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def find_by_judge(self, judge_user_id: int) -> list[dict]:
        """评委查看自己提交的所有评分"""
        db = get_db()
        rows = db.execute(
            "SELECT * FROM judging_records WHERE judge_user_id = ? ORDER BY submitted_at DESC",
            (judge_user_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def compute_score(self, record: dict) -> float:
        """计算单条评分的综合得分（四维算术平均）"""
        scores = [
            record.get("technical_score"),
            record.get("innovation_score"),
            record.get("presentation_score"),
            record.get("completeness_score"),
        ]
        valid = [s for s in scores if s is not None]
        return sum(valid) / len(valid) if valid else 0.0


class JudgeAssignmentDAO(BaseDAO):
    table = "judge_assignments"

    def find_by_race(self, race_id: int) -> list[dict]:
        """查看某赛事的所有评委分配"""
        db = get_db()
        rows = db.execute(
            "SELECT * FROM judge_assignments WHERE race_id = ? ORDER BY assigned_at DESC",
            (race_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def find_by_judge(self, judge_user_id: int) -> list[dict]:
        """评委查看自己被分配的作品列表"""
        db = get_db()
        rows = db.execute(
            "SELECT * FROM judge_assignments WHERE judge_user_id = ? ORDER BY assigned_at DESC",
            (judge_user_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def find_by_work_and_judge(self, work_id: int, judge_user_id: int) -> dict | None:
        """检查是否已分配"""
        db = get_db()
        row = db.execute(
            "SELECT * FROM judge_assignments WHERE work_id = ? AND judge_user_id = ?",
            (work_id, judge_user_id),
        ).fetchone()
        return dict(row) if row else None

    def find_by_work(self, work_id: int) -> list[dict]:
        """查看某作品被分配给了哪些评委"""
        db = get_db()
        rows = db.execute(
            "SELECT * FROM judge_assignments WHERE work_id = ? ORDER BY assigned_at",
            (work_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def batch_create(
        self, race_id: int, assignments: list[dict]
    ) -> list[dict]:
        """批量分配评委。

        assignments: [{"work_id": 1, "judge_user_id": 5}, ...]
        返回成功创建的 assignment dict 列表。
        """
        db = get_db()
        created_assignments = []
        for item in assignments:
            work_id = item["work_id"]
            judge_user_id = item["judge_user_id"]
            # 检查是否已存在
            existing = self.find_by_work_and_judge(work_id, judge_user_id)
            if existing:
                created_assignments.append(existing)
                continue
            cursor = db.execute(
                """INSERT INTO judge_assignments (race_id, work_id, judge_user_id, assigned_at)
                   VALUES (?, ?, ?, datetime('now'))""",
                (race_id, work_id, judge_user_id),
            )
            created_assignments.append(self.find_by_id(cursor.lastrowid))
        return created_assignments
