"""
人员 C：奖项榜单 DAO 层

AwardDAO 继承 BaseDAO 获得基础 CRUD 方法。
"""
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

    def find_leaderboard(self, race_id: int) -> list[dict]:
        """公开榜单：奖项 + 获奖者信息 + 作品标题 + 总分。

        返回按 position ASC 排列的榜单条目，包含：
        - award 字段
        - winner_username
        - work_title
        - total_score（该作品所有评分的平均分）
        """
        db = get_db()
        rows = db.execute(
            """SELECT
                   a.id AS award_id,
                   a.title AS award_title,
                   a.position,
                   a.description AS award_description,
                   a.work_id,
                   a.registration_id,
                   w.title AS work_title,
                   u.username AS winner_username,
                   u.id AS winner_user_id
               FROM awards a
               LEFT JOIN works w ON a.work_id = w.id
               LEFT JOIN registrations reg ON a.registration_id = reg.id
               LEFT JOIN users u ON reg.user_id = u.id
               WHERE a.race_id = ?
               ORDER BY a.position ASC""",
            (race_id,),
        ).fetchall()

        result = []
        for row in rows:
            entry = dict(row)
            # 计算该作品的总分
            if entry["work_id"]:
                scores_row = db.execute(
                    """SELECT
                           AVG(technical_score) AS avg_tech,
                           AVG(innovation_score) AS avg_innov,
                           AVG(presentation_score) AS avg_pres,
                           AVG(completeness_score) AS avg_comp
                       FROM judging_records
                       WHERE work_id = ?""",
                    (entry["work_id"],),
                ).fetchone()
                if scores_row:
                    scores = [
                        scores_row["avg_tech"],
                        scores_row["avg_innov"],
                        scores_row["avg_pres"],
                        scores_row["avg_comp"],
                    ]
                    valid = [s for s in scores if s is not None]
                    entry["total_score"] = round(sum(valid) / len(valid), 2) if valid else None
                else:
                    entry["total_score"] = None
            else:
                entry["total_score"] = None
            result.append(entry)
        return result
