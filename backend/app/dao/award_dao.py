"""
人员 C：奖项榜单 DAO 层

AwardDAO 继承 BaseDAO 获得基础 CRUD 方法。
"""
import statistics
from app.dao.base import BaseDAO
from app.database import get_db


class AwardDAO(BaseDAO):
    table = "awards"

    def find_by_race(self, race_id: int) -> list[dict]:
        """查询某赛事的所有奖项，按 position ASC 排列"""
        db = get_db()
        rows = db.execute(
            "SELECT * FROM awards WHERE race_id = ? ORDER BY position ASC",
            (race_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def find_leaderboard(self, race_id: int) -> dict:
        """公开榜单：从 submitted works + judging_records 实时聚合排名。

        支持 avg / median / trimmed_mean 三种 tiebreaker。
        返回 rankings 和 disqualified 两个列表。
        """
        db = get_db()

        # 获取 race 配置
        race = db.execute(
            "SELECT judging_tiebreaker FROM races WHERE id = ?", (race_id,)
        ).fetchone()
        tiebreaker = race["judging_tiebreaker"] if race else "avg"

        # 获取所有 submitted works（排除 disqualified）
        works = db.execute(
            """SELECT w.*, rp.id AS rp_id, reg.id AS registration_id,
                      reg.user_id AS owner_user_id
               FROM works w
               JOIN race_projects rp ON w.race_project_id = rp.id
               JOIN registrations reg ON rp.registration_id = reg.id
               WHERE reg.race_id = ? AND w.work_status = 'submitted'
               ORDER BY w.id""",
            (race_id,),
        ).fetchall()

        # 获取所有奖项（用于关联展示）
        awards = db.execute(
            "SELECT * FROM awards WHERE race_id = ? ORDER BY position ASC",
            (race_id,),
        ).fetchall()
        award_by_work = {}
        award_by_reg = {}
        for a in awards:
            a_dict = dict(a)
            if a["work_id"]:
                award_by_work[a["work_id"]] = a_dict
            if a["registration_id"]:
                award_by_reg[a["registration_id"]] = a_dict

        rankings = []
        disqualified_list = []

        for work in works:
            work_dict = dict(work)

            if work_dict["disqualified"]:
                disqualified_list.append({
                    "work_id": work_dict["id"],
                    "title": work_dict["title"],
                    "reason": work_dict.get("disqualify_reason", ""),
                })
                continue

            # 获取评分
            judgments = db.execute(
                "SELECT * FROM judging_records WHERE work_id = ?",
                (work_dict["id"],),
            ).fetchall()

            scores_list = []
            for j in judgments:
                jd = dict(j)
                scores = [
                    jd.get("technical_score"),
                    jd.get("innovation_score"),
                    jd.get("presentation_score"),
                    jd.get("completeness_score"),
                ]
                valid = [s for s in scores if s is not None]
                if valid:
                    scores_list.append(sum(valid) / len(valid))

            # 根据 tiebreaker 计算总分
            if scores_list:
                if tiebreaker == "median":
                    total_score = round(statistics.median(scores_list), 2)
                elif tiebreaker == "trimmed_mean":
                    total_score = round(statistics.mean(sorted(scores_list)[1:-1]) if len(scores_list) >= 3 else statistics.mean(scores_list), 2)
                else:  # avg
                    total_score = round(sum(scores_list) / len(scores_list), 2)
            else:
                total_score = None

            # 获取 owner 信息
            owner = db.execute(
                "SELECT username, github_login FROM users WHERE id = ?",
                (work_dict["owner_user_id"],),
            ).fetchone()

            # 关联奖项
            award_title = None
            award_position = None
            matching_award = award_by_work.get(work_dict["id"]) or award_by_reg.get(work_dict["registration_id"])
            if matching_award:
                award_title = matching_award["title"]
                award_position = matching_award["position"]

            rankings.append({
                "work_id": work_dict["id"],
                "title": work_dict["title"],
                "description": work_dict["description"],
                "owner_username": owner["username"] if owner else None,
                "owner_github_login": owner["github_login"] if owner else None,
                "total_score": total_score,
                "judge_count": len(judgments),
                "award_title": award_title,
                "award_position": award_position,
            })

        # 按总分降序排列
        rankings.sort(
            key=lambda r: r["total_score"] if r["total_score"] is not None else -1,
            reverse=True,
        )

        return {
            "race_id": race_id,
            "tiebreaker": tiebreaker,
            "rankings": rankings,
            "disqualified": disqualified_list,
        }
