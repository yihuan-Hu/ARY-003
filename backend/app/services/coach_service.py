from app.dao.race_dao import RaceDAO
from app.dao.race_project_dao import RaceProjectDAO
from app.dao.registration_dao import RegistrationDAO
from app.dao.work_dao import WorkDAO
from app.database import get_db
from app.utils.errors import NotFoundError


class RidingCoachService:
    def __init__(self):
        self.registration_dao = RegistrationDAO()
        self.race_project_dao = RaceProjectDAO()
        self.work_dao = WorkDAO()
        self.race_dao = RaceDAO()

    def get_next_actions(self, race_project_id: int, user_id: int) -> list[dict]:
        project = self.race_project_dao.find_by_id(race_project_id)
        if project is None:
            raise NotFoundError("RaceProject not found")
        registration = self.registration_dao.find_by_id(project["registration_id"])
        if registration is None or registration["user_id"] != user_id:
            raise NotFoundError("RaceProject not found")
        race = self.race_dao.find_by_id(registration["race_id"])
        if race is None:
            raise NotFoundError("Race not found")

        if registration["status"] == "submitted":
            return [{
                "action_label": "等待审批",
                "description": "报名已提交，等待主办方审批",
                "target_url": f"/rider/registrations/{registration['id']}",
            }]

        if race["status"] in {"completed", "archived"}:
            if self._has_award(registration["id"]):
                return [{
                    "action_label": "查看获奖",
                    "description": "恭喜获奖！查看榜单",
                    "target_url": f"/public/races/{race['id']}/leaderboard",
                }]
            return [{
                "action_label": "赛事已结束",
                "description": "查看你的骑手档案，积累的能力已沉淀",
                "target_url": f"/public/riders/{user_id}",
            }]

        actions = []
        if registration["status"] == "approved":
            ca_statuses = self._ca_statuses(race_project_id)
            if not ca_statuses:
                actions.append({
                    "action_label": "接入编码助手",
                    "description": "接入你的 Coding Agent，开始骑行",
                    "target_url": f"/rider/race-projects/{race_project_id}/ca-wizard",
                })
            elif all(status == "pending" for status in ca_statuses):
                actions.append({
                    "action_label": "完成 CA 握手",
                    "description": "所有 CA 连接仍在等待握手，请完成握手以激活连接",
                    "target_url": f"/rider/race-projects/{race_project_id}",
                })

            works = self.work_dao.find_by_race_project(race_project_id)
            submitted = [work for work in works if work["work_status"] == "submitted"]
            if not submitted:
                actions.append({
                    "action_label": "提交作品",
                    "description": "你还没有提交作品，请完成并提交",
                    "target_url": f"/rider/race-projects/{race_project_id}/works",
                })
            else:
                issues = self._check_readiness(submitted[0])
                if issues:
                    actions.append({
                        "action_label": "检查作品准备度",
                        "description": f"修复以下问题：{'; '.join(issues)}",
                        "target_url": (
                            f"/rider/race-projects/{race_project_id}/review-readiness"
                        ),
                    })
        return actions

    @staticmethod
    def _table_columns(table: str) -> set[str]:
        if table not in {"ca_connections", "awards"}:
            return set()
        db = get_db()
        exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if not exists:
            return set()
        return {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}

    def _ca_statuses(self, race_project_id: int) -> list[str]:
        columns = self._table_columns("ca_connections")
        if "race_project_id" not in columns:
            return []
        status_column = next(
            (name for name in ("ingestion_status", "status") if name in columns),
            None,
        )
        if status_column is None:
            return []
        rows = get_db().execute(
            f"SELECT {status_column} AS status FROM ca_connections WHERE race_project_id=?",
            (race_project_id,),
        ).fetchall()
        return [row["status"] for row in rows]

    def _has_award(self, registration_id: int) -> bool:
        columns = self._table_columns("awards")
        if "registration_id" not in columns:
            return False
        row = get_db().execute(
            "SELECT 1 FROM awards WHERE registration_id=? LIMIT 1",
            (registration_id,),
        ).fetchone()
        return row is not None

    @staticmethod
    def _check_readiness(work: dict) -> list[str]:
        issues = []
        if not work.get("title"):
            issues.append("作品名称为空")
        if not work.get("description"):
            issues.append("作品简介缺失")
        if not work.get("readme_body"):
            issues.append("README 缺失")
        if not work.get("repo_url"):
            issues.append("缺少代码仓库")
        if not work.get("demo_url"):
            issues.append("缺少演示链接")
        return issues
