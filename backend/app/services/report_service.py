"""
人员 C：Report 模块

提供三类报告：
- rider_report: 骑手个人参赛报告
- race_report: 赛事整体报告
- review_summary: 评审汇总报告
"""
import json

from app.database import get_db
from app.dao.race_dao import RaceDAO
from app.dao.work_dao import WorkDAO
from app.dao.registration_dao import RegistrationDAO
from app.dao.race_project_dao import RaceProjectDAO
from app.dao.judging_dao import JudgingRecordDAO, JudgeAssignmentDAO
from app.dao.award_dao import AwardDAO
from app.utils.errors import NotFoundError, ForbiddenError


class ReportService:
    def __init__(self):
        self.race_dao = RaceDAO()
        self.work_dao = WorkDAO()
        self.registration_dao = RegistrationDAO()
        self.race_project_dao = RaceProjectDAO()
        self.judgment_dao = JudgingRecordDAO()
        self.assignment_dao = JudgeAssignmentDAO()
        self.award_dao = AwardDAO()

    # ================================================================
    # Rider Report
    # ================================================================

    def generate_rider_report(self, user_id: int) -> dict:
        """为骑手生成个人参赛报告。

        包含：参赛统计、作品列表、评分汇总、获奖情况。
        """
        registrations = self.registration_dao.find_by_user(user_id)
        race_entries = []
        total_judgments = 0
        total_score_sum = 0.0

        for reg in registrations:
            race = self.race_dao.find_by_id(reg["race_id"])
            rp = self.race_project_dao.find_by_registration(reg["id"])
            works_data = []
            if rp:
                works = self.work_dao.find_by_race_project(rp["id"])
                for w in works:
                    judgments = self.judgment_dao.find_by_work(w["id"])
                    avg_score = (
                        round(
                            sum(self.judgment_dao.compute_score(j) for j in judgments)
                            / len(judgments),
                            2,
                        )
                        if judgments
                        else None
                    )
                    total_judgments += len(judgments)
                    if avg_score:
                        total_score_sum += avg_score

                    works_data.append({
                        "work_id": w["id"],
                        "title": w["title"],
                        "status": w["work_status"],
                        "submitted_at": w["submitted_at"],
                        "judgment_count": len(judgments),
                        "average_score": avg_score,
                        "disqualified": w["disqualified"],
                    })

            # 获奖
            awards = []
            db = get_db()
            award_rows = db.execute(
                "SELECT * FROM awards WHERE registration_id = ? ORDER BY position ASC",
                (reg["id"],),
            ).fetchall()
            for a in award_rows:
                awards.append(dict(a))

            race_entries.append({
                "race_id": race["id"] if race else None,
                "race_name": race["name"] if race else "Unknown",
                "race_status": race["status"] if race else None,
                "registration_status": reg["status"],
                "works": works_data,
                "awards": awards,
            })

        return {
            "user_id": user_id,
            "total_races": len(race_entries),
            "completed_races": sum(
                1 for e in race_entries
                if e["race_status"] in ("completed", "archived")
            ),
            "total_works": sum(len(e["works"]) for e in race_entries),
            "total_judgments_received": total_judgments,
            "average_score_overall": (
                round(total_score_sum / total_judgments, 2)
                if total_judgments > 0
                else None
            ),
            "race_entries": race_entries,
        }

    # ================================================================
    # Race Report
    # ================================================================

    def generate_race_report(self, race_id: int, actor_user_id: int) -> dict:
        """为赛事生成整体报告。

        校验：actor 是 race creator。
        包含：参赛人数、作品数、评审进度、评分分布、奖项。
        """
        race = self.race_dao.find_by_id(race_id)
        if race is None:
            raise NotFoundError("Race not found")
        if race["created_by_user_id"] != actor_user_id:
            raise ForbiddenError("You can only manage your own races")

        registrations = self.registration_dao.find_by_race(race_id)
        approved = [r for r in registrations if r["status"] == "approved"]
        submitted_works = self.work_dao.find_submitted_by_race(race_id)

        # 评审进度
        total_possible_judgments = 0
        total_actual_judgments = 0
        for w in submitted_works:
            assignments = self.assignment_dao.find_by_work(w["id"])
            total_possible_judgments += len(assignments)
            total_actual_judgments += len(self.judgment_dao.find_by_work(w["id"]))

        # 评分分布
        score_distribution = {"1-3": 0, "4-6": 0, "7-8": 0, "9-10": 0}
        all_scores = []
        for w in submitted_works:
            for j in self.judgment_dao.find_by_work(w["id"]):
                avg = self.judgment_dao.compute_score(j)
                all_scores.append(avg)
                if avg <= 3:
                    score_distribution["1-3"] += 1
                elif avg <= 6:
                    score_distribution["4-6"] += 1
                elif avg <= 8:
                    score_distribution["7-8"] += 1
                else:
                    score_distribution["9-10"] += 1

        # 奖项
        awards = self.award_dao.find_by_race(race_id)

        # 公告
        db = get_db()
        announcement_count = db.execute(
            "SELECT COUNT(*) AS cnt FROM announcements WHERE race_id = ?",
            (race_id,),
        ).fetchone()["cnt"]

        return {
            "race_id": race_id,
            "race_name": race["name"],
            "race_status": race["status"],
            "registration_summary": {
                "total": len(registrations),
                "approved": len(approved),
                "rejected": sum(1 for r in registrations if r["status"] == "rejected"),
                "withdrawn": sum(1 for r in registrations if r["status"] == "withdrawn"),
                "pending": sum(1 for r in registrations if r["status"] == "submitted"),
            },
            "work_summary": {
                "total_submitted": len(submitted_works),
                "disqualified": sum(1 for w in submitted_works if w["disqualified"]),
            },
            "judging_progress": {
                "expected_judgments": total_possible_judgments,
                "completed_judgments": total_actual_judgments,
                "completion_rate": (
                    round(total_actual_judgments / total_possible_judgments, 2)
                    if total_possible_judgments > 0
                    else 0
                ),
            },
            "score_distribution": score_distribution,
            "average_score": (
                round(sum(all_scores) / len(all_scores), 2)
                if all_scores
                else None
            ),
            "awards": awards,
            "announcement_count": announcement_count,
        }

    # ================================================================
    # Review Summary
    # ================================================================

    def generate_review_summary(self, race_id: int, actor_user_id: int) -> dict:
        """评审汇总快照。

        校验：actor 是 race creator。
        包含：每个评委的评审进度 + 每条评审记录的详细信息。
        """
        race = self.race_dao.find_by_id(race_id)
        if race is None:
            raise NotFoundError("Race not found")
        if race["created_by_user_id"] != actor_user_id:
            raise ForbiddenError("You can only manage your own races")

        judgments = self.judgment_dao.find_by_race(race_id)
        assignments = self.assignment_dao.find_by_race(race_id)

        # 按评委汇总
        judge_map = {}
        for a in assignments:
            jid = a["judge_user_id"]
            if jid not in judge_map:
                db = get_db()
                user = db.execute(
                    "SELECT username FROM users WHERE id = ?", (jid,)
                ).fetchone()
                judge_map[jid] = {
                    "judge_user_id": jid,
                    "judge_name": user["username"] if user else "Unknown",
                    "assigned_count": 0,
                    "completed_count": 0,
                }
            judge_map[jid]["assigned_count"] += 1

        for j in judgments:
            jid = j["judge_user_id"]
            if jid in judge_map:
                judge_map[jid]["completed_count"] += 1

        return {
            "race_id": race_id,
            "race_name": race["name"],
            "total_judgments": len(judgments),
            "total_assignments": len(assignments),
            "judge_summary": list(judge_map.values()),
            "judgments": judgments,
        }

    # ================================================================
    # 报告持久化
    # ================================================================

    def save_report(
        self,
        report_type: str,
        owner_user_id: int,
        race_id: int | None,
        title: str,
        body: dict,
        summary: str = "",
    ) -> dict:
        """保存报告到 reports 表"""
        db = get_db()
        cursor = db.execute(
            """INSERT INTO reports
               (report_type, owner_user_id, race_id, title, summary, body_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (report_type, owner_user_id, race_id, title, summary, json.dumps(body)),
        )
        db.commit()
        row = db.execute("SELECT * FROM reports WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return dict(row)

    def get_reports_by_user(self, user_id: int) -> list[dict]:
        """获取用户的所有报告"""
        db = get_db()
        rows = db.execute(
            "SELECT * FROM reports WHERE owner_user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_report(self, report_id: int, user_id: int) -> dict:
        """获取单个报告"""
        db = get_db()
        row = db.execute(
            "SELECT * FROM reports WHERE id = ? AND owner_user_id = ?",
            (report_id, user_id),
        ).fetchone()
        if row is None:
            raise NotFoundError("Report not found")
        return dict(row)
