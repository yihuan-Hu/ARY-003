"""
人员 C：骑手档案服务

提供公开骑手档案和私人完整档案。
"""
from app.dao.registration_dao import RegistrationDAO
from app.dao.race_project_dao import RaceProjectDAO
from app.dao.work_dao import WorkDAO
from app.dao.award_dao import AwardDAO
from app.dao.race_dao import RaceDAO
from app.database import get_db
from app.utils.errors import NotFoundError


class RiderProfileService:
    def __init__(self):
        self.registration_dao = RegistrationDAO()
        self.race_project_dao = RaceProjectDAO()
        self.work_dao = WorkDAO()
        self.award_dao = AwardDAO()
        self.race_dao = RaceDAO()

    def get_public_profile(self, user_id: int) -> dict:
        """公开骑手档案（无需认证）。

        聚合：
        - 用户基本信息
        - 参赛统计
        - 公开作品列表
        - 获奖列表
        """
        db = get_db()
        user = db.execute(
            "SELECT id, username, github_login, display_name, school_org, bio FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if user is None:
            raise NotFoundError("Rider not found")

        user_data = dict(user)

        # 统计数据
        registrations = self.registration_dao.find_by_user(user_id)
        approved_regs = [r for r in registrations if r["status"] == "approved"]
        total_races = len(registrations)

        # 完成的赛事数（race status 为 completed/archived）
        completed_races = 0
        for reg in registrations:
            race = self.race_dao.find_by_id(reg["race_id"])
            if race and race["status"] in ("completed", "archived"):
                completed_races += 1

        # 公开作品
        public_works = []
        for reg in approved_regs:
            rp = self.race_project_dao.find_by_registration(reg["id"])
            if rp:
                works = self.work_dao.find_by_race_project(rp["id"])
                for w in works:
                    if w["visibility"] == "public" and w["disqualified"] == 0:
                        race = self.race_dao.find_by_id(reg["race_id"])
                        public_works.append({
                            "id": w["id"],
                            "title": w["title"],
                            "description": w["description"],
                            "race_name": race["name"] if race else None,
                            "submitted_at": w["submitted_at"],
                        })

        # 获奖列表
        awards_list = []
        for reg in registrations:
            db_awards = db.execute(
                "SELECT * FROM awards WHERE registration_id = ? ORDER BY position ASC",
                (reg["id"],),
            ).fetchall()
            for a in db_awards:
                award = dict(a)
                race = self.race_dao.find_by_id(award["race_id"])
                award["race_name"] = race["name"] if race else None
                awards_list.append(award)

        return {
            "user": user_data,
            "stats": {
                "total_races": total_races,
                "completed_races": completed_races,
                "awards_count": len(awards_list),
                "works_count": len(public_works),
            },
            "recent_works": public_works[:5],
            "awards": awards_list,
        }

    def get_private_profile(self, user_id: int) -> dict:
        """Rider 自己的完整档案（含未公开 work）"""
        profile = self.get_public_profile(user_id)

        # 补充未公开的 works
        registrations = self.registration_dao.find_by_user(user_id)
        all_works = []
        for reg in registrations:
            rp = self.race_project_dao.find_by_registration(reg["id"])
            if rp:
                works = self.work_dao.find_by_race_project(rp["id"])
                for w in works:
                    race = self.race_dao.find_by_id(reg["race_id"])
                    all_works.append({
                        "id": w["id"],
                        "title": w["title"],
                        "description": w["description"],
                        "work_status": w["work_status"],
                        "visibility": w["visibility"],
                        "disqualified": w["disqualified"],
                        "race_name": race["name"] if race else None,
                        "submitted_at": w["submitted_at"],
                    })

        # 补充注册信息
        registrations_detail = []
        for reg in registrations:
            race = self.race_dao.find_by_id(reg["race_id"])
            registrations_detail.append({
                "registration_id": reg["id"],
                "race_id": reg["race_id"],
                "race_name": race["name"] if race else None,
                "status": reg["status"],
                "submitted_at": reg["submitted_at"],
            })

        profile["all_works"] = all_works
        profile["registrations"] = registrations_detail
        return profile
