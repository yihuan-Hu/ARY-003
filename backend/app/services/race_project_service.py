"""
RaceProject 业务服务（角色 4 交付 + 人员 D 扩展）

提供：
- Rider 查看自己的 RaceProject（含归属校验）
- Organizer 查看 managed race 的 RaceProject 列表（含管理范围校验）
- 统一响应格式，含真实 CAConnection[] 和 Work 占位字段

RaceProject 不得由 Rider 手动创建——只由 RegistrationService.approve_registration()
在 Registration approved 后原子生成。
"""
from app.dao.race_project_dao import RaceProjectDAO
from app.dao.registration_dao import RegistrationDAO
from app.dao.race_dao import RaceDAO
from app.dao.ca_connection_dao import CAConnectionDAO
from app.utils.errors import ForbiddenError, NotFoundError


class RaceProjectService:
    def __init__(self):
        self.dao = RaceProjectDAO()
        self.registration_dao = RegistrationDAO()
        self.race_dao = RaceDAO()
        self.ca_connection_dao = CAConnectionDAO()

    # ---- 响应格式化（统一字段，CA 连接为真实数据） ----

    @staticmethod
    def _sanitize_ca_connection(conn: dict) -> dict:
        """去除 CA 连接中的敏感字段"""
        result = dict(conn)
        result.pop("api_key_hash", None)
        return result

    def _format(self, rp: dict) -> dict:
        """将 DAO 返回的 race_projects 行格式化为 API 响应。

        ca_connections 现在查询真实数据（人员 D 实现）。
        """
        project_id = rp["id"]
        ca_connections = [
            self._sanitize_ca_connection(c)
            for c in self.ca_connection_dao.find_by_race_project(project_id)
        ]
        return {
            "id": rp["id"],
            "registration_id": rp["registration_id"],
            "aggregate_ingestion_status": rp.get(
                "aggregate_ingestion_status", "not_configured"
            ),
            "connection_health": rp.get("connection_health", "no_signal"),
            "created_at": rp["created_at"],
            "ca_connections": ca_connections,
            "work": None,
        }

    # ---- Rider 查询 ----

    def get_for_rider(self, race_project_id: int, user_id: int) -> dict:
        """Rider 查看自己的 RaceProject。

        归属链校验：RaceProject → Registration → User
        """
        rp = self.dao.find_by_id(race_project_id)
        if rp is None:
            raise NotFoundError("RaceProject not found")

        # 验证归属链
        reg = self.registration_dao.find_by_id(rp["registration_id"])
        if reg is None or reg["user_id"] != user_id:
            raise NotFoundError("RaceProject not found")

        return self._format(rp)

    def list_for_rider(self, user_id: int) -> list[dict]:
        """Rider 查看自己的全部 RaceProject 列表"""
        projects = self.dao.find_by_user(user_id)
        return [self._format(rp) for rp in projects]

    # ---- Organizer 查询 ----

    def list_for_organizer(self, race_id: int, user_id: int) -> list[dict]:
        """Organizer 查看自己管理的赛事的 RaceProject 列表。

        校验 managed race 范围。
        """
        race = self.race_dao.find_by_id(race_id)
        if race is None:
            raise NotFoundError("Race not found")
        if race["created_by_user_id"] != user_id:
            raise ForbiddenError("You can only manage your own races")

        projects = self.dao.find_by_race(race_id)
        return [self._format(rp) for rp in projects]
