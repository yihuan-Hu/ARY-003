"""
人员 C：Report 模块

提供三类报告：
- rider_report: 骑手个人参赛报告（绑定 subject_registration_id）
- race_report: 赛事整体报告
- review_summary: 评审汇总报告

可见性流程：draft → private → public（单向）
"""
import json

from app.database import get_db
from app.dao.race_dao import RaceDAO
from app.dao.work_dao import WorkDAO
from app.dao.registration_dao import RegistrationDAO
from app.dao.race_project_dao import RaceProjectDAO
from app.dao.judging_dao import JudgingRecordDAO, JudgeAssignmentDAO
from app.dao.award_dao import AwardDAO
from app.utils.errors import NotFoundError, ForbiddenError, InvalidStateError


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
        """为骑手生成个人参赛报告。"""
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
        race = self.race_dao.find_by_id(race_id)
        if race is None:
            raise NotFoundError("Race not found")
        if race["created_by_user_id"] != actor_user_id:
            raise ForbiddenError("You can only manage your own races")

        registrations = self.registration_dao.find_by_race(race_id)
        approved = [r for r in registrations if r["status"] == "approved"]
        submitted_works = self.work_dao.find_submitted_by_race(race_id)

        total_possible_judgments = 0
        total_actual_judgments = 0
        for w in submitted_works:
            assignments = self.assignment_dao.find_by_work(w["id"])
            total_possible_judgments += len(assignments)
            total_actual_judgments += len(self.judgment_dao.find_by_work(w["id"]))

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

        awards = self.award_dao.find_by_race(race_id)

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
        race = self.race_dao.find_by_id(race_id)
        if race is None:
            raise NotFoundError("Race not found")
        if race["created_by_user_id"] != actor_user_id:
            raise ForbiddenError("You can only manage your own races")

        judgments = self.judgment_dao.find_by_race(race_id)
        assignments = self.assignment_dao.find_by_race(race_id)

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
    # 报告持久化（含可见性流：draft/private/public）
    # ================================================================

    def generate(
        self, race_id: int, actor_user_id: int, report_type: str,
        auto_fill: bool = True, title: str = None,
        subject_registration_id: int = None,
    ) -> dict:
        """生成报告（draft 状态保存）。

        auto_fill=True 时填充赛事数据、报名数、作品数、评审完成率等。
        rider_report 必须绑定 subject_registration_id。
        """
        race = self.race_dao.find_by_id(race_id)
        if race is None:
            raise NotFoundError("Race not found")
        if race["created_by_user_id"] != actor_user_id:
            raise ForbiddenError("You can only manage your own races")

        if report_type == "rider_report" and not subject_registration_id:
            raise InvalidStateError("rider_report requires subject_registration_id")

        if auto_fill:
            if report_type == "race_report":
                body = self.generate_race_report(race_id, actor_user_id)
            elif report_type == "review_summary":
                body = self.generate_review_summary(race_id, actor_user_id)
            elif report_type == "rider_report":
                reg = self.registration_dao.find_by_id(subject_registration_id)
                if reg is None:
                    raise NotFoundError("Registration not found")
                body = self.generate_rider_report(reg["user_id"])
            else:
                body = {}
        else:
            body = {}

        if not title:
            race_name = race["name"] if race else f"Race #{race_id}"
            type_labels = {
                "race_report": f"Race Report - {race_name}",
                "review_summary": f"Review Summary - {race_name}",
                "rider_report": f"Rider Report - Registration #{subject_registration_id}",
            }
            title = type_labels.get(report_type, f"Report - {race_name}")

        return self.save_report(
            report_type, actor_user_id, race_id, title, body,
            subject_registration_id=subject_registration_id,
            visibility="draft",
            auto_fill=1 if auto_fill else 0,
        )

    def save_report(
        self,
        report_type: str,
        owner_user_id: int,
        race_id: int | None,
        title: str,
        body: dict,
        summary: str = "",
        subject_registration_id: int = None,
        visibility: str = "draft",
        auto_fill: int = 1,
    ) -> dict:
        """保存报告到 reports 表"""
        db = get_db()
        cursor = db.execute(
            """INSERT INTO reports
               (report_type, owner_user_id, race_id, title, summary, body_json,
                subject_registration_id, visibility, auto_fill)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                report_type, owner_user_id, race_id, title, summary,
                json.dumps(body), subject_registration_id, visibility, auto_fill,
            ),
        )
        db.commit()
        row = db.execute("SELECT * FROM reports WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return dict(row)

    def edit(self, report_id: int, user_id: int, data: dict) -> dict:
        """编辑报告内容（仅 owner 可编辑 draft/private 报告）"""
        db = get_db()
        report = db.execute(
            "SELECT * FROM reports WHERE id = ?", (report_id,)
        ).fetchone()
        if report is None:
            raise NotFoundError("Report not found")
        if report["owner_user_id"] != user_id:
            raise ForbiddenError("You can only edit your own reports")
        if report["visibility"] == "public":
            raise InvalidStateError("Cannot edit a published report; hide it first")

        updates = {}
        for key in ("title", "summary", "body_json"):
            if key in data:
                updates[key] = data[key] if key != "body_json" else json.dumps(data[key])
        if "subject_registration_id" in data:
            updates["subject_registration_id"] = data["subject_registration_id"]

        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            db.execute(
                f"UPDATE reports SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                tuple(updates.values()) + (report_id,),
            )
            db.commit()

        return dict(db.execute(
            "SELECT * FROM reports WHERE id = ?", (report_id,)
        ).fetchone())

    def publish(self, report_id: int, user_id: int) -> dict:
        """发布报告（draft/private → public），记录 published_at"""
        db = get_db()
        report = db.execute(
            "SELECT * FROM reports WHERE id = ?", (report_id,)
        ).fetchone()
        if report is None:
            raise NotFoundError("Report not found")
        if report["owner_user_id"] != user_id:
            raise ForbiddenError("You can only publish your own reports")

        db.execute(
            """UPDATE reports
               SET visibility = 'public', published_at = datetime('now'),
                   updated_at = datetime('now')
               WHERE id = ?""",
            (report_id,),
        )
        db.commit()
        return dict(db.execute(
            "SELECT * FROM reports WHERE id = ?", (report_id,)
        ).fetchone())

    def hide(self, report_id: int, user_id: int) -> dict:
        """隐藏报告（draft/public/private → private），清除 published_at"""
        db = get_db()
        report = db.execute(
            "SELECT * FROM reports WHERE id = ?", (report_id,)
        ).fetchone()
        if report is None:
            raise NotFoundError("Report not found")
        if report["owner_user_id"] != user_id:
            raise ForbiddenError("You can only hide your own reports")

        db.execute(
            """UPDATE reports
               SET visibility = 'private', published_at = NULL,
                   updated_at = datetime('now')
               WHERE id = ?""",
            (report_id,),
        )
        db.commit()
        return dict(db.execute(
            "SELECT * FROM reports WHERE id = ?", (report_id,)
        ).fetchone())

    def get_reports_by_user(self, user_id: int) -> list[dict]:
        """获取用户的所有报告"""
        db = get_db()
        rows = db.execute(
            "SELECT * FROM reports WHERE owner_user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_report(self, report_id: int, user_id: int) -> dict:
        """获取单个报告（owner 可查看自己的所有报告）"""
        db = get_db()
        row = db.execute(
            "SELECT * FROM reports WHERE id = ? AND owner_user_id = ?",
            (report_id, user_id),
        ).fetchone()
        if row is None:
            raise NotFoundError("Report not found")
        return dict(row)

    def list_for_race(self, race_id: int, user_id: int) -> list[dict]:
        """Organizer 查看赛事的所有报告（含 draft/private/public）"""
        race = self.race_dao.find_by_id(race_id)
        if race is None:
            raise NotFoundError("Race not found")
        if race["created_by_user_id"] != user_id:
            raise ForbiddenError("You can only manage your own races")
        db = get_db()
        rows = db.execute(
            "SELECT * FROM reports WHERE race_id = ? ORDER BY created_at DESC",
            (race_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def list_public_for_race(self, race_id: int) -> list[dict]:
        """Public 查看赛事的公开报告（只返回 visibility='public' 的 race_report / review_summary）"""
        race = self.race_dao.find_by_id(race_id)
        if race is None or race["status"] == "draft":
            raise NotFoundError("Race not found")
        db = get_db()
        rows = db.execute(
            """SELECT * FROM reports
               WHERE race_id = ? AND visibility = 'public'
                 AND report_type IN ('race_report', 'review_summary')
               ORDER BY created_at DESC""",
            (race_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_rider_report(self, registration_id: int, user_id: int) -> dict:
        """Rider 查看自己 registration 的已发布 rider_report"""
        reg = self.registration_dao.find_by_id(registration_id)
        if reg is None:
            raise NotFoundError("Registration not found")
        if reg["user_id"] != user_id:
            raise ForbiddenError("You can only view your own rider reports")

        db = get_db()
        row = db.execute(
            """SELECT * FROM reports
               WHERE subject_registration_id = ? AND report_type = 'rider_report'
                 AND visibility = 'public'
               ORDER BY created_at DESC LIMIT 1""",
            (registration_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError("Report not found")
        return dict(row)
