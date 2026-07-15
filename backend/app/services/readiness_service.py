"""
人员 C：Review Readiness 评审准备度服务

检测规则（不依赖 AI）：
- 无 Work → "作品未提交"
- Work title/description/readme_body 为空 → "作品信息不完整"
- repo_url 和 demo_url 都为空 → "缺少代码仓库或演示链接"
- CA 数据全部缺失 → "缺少骑行过程数据"
- CA 有 failed 连接 → "CA 接入异常"
- 当前评分不足（已评作品均分 < 5）→ "评审得分偏低"

只提示风险，不自动取消资格、不自动 withdraw、不自动隐藏作品。
"""
from app.dao.race_project_dao import RaceProjectDAO
from app.dao.registration_dao import RegistrationDAO
from app.dao.work_dao import WorkDAO
from app.dao.race_dao import RaceDAO
from app.dao.judging_dao import JudgingRecordDAO
from app.database import get_db
from app.utils.errors import NotFoundError, ForbiddenError
from app.utils.permissions import check_own_race_project, check_managed_race


class ReviewReadinessService:
    def __init__(self):
        self.race_project_dao = RaceProjectDAO()
        self.registration_dao = RegistrationDAO()
        self.work_dao = WorkDAO()
        self.race_dao = RaceDAO()
        self.judgment_dao = JudgingRecordDAO()

    def check_for_rider(
        self, race_project_id: int, user_id: int
    ) -> dict:
        """Rider 查看自己 RaceProject 的准备度。

        返回 {"works": [...], "overall_ready": bool, "risks": [...]}
        """
        rp = check_own_race_project(race_project_id, user_id)
        reg = self.registration_dao.find_by_id(rp["registration_id"])
        race = self.race_dao.find_by_id(reg["race_id"])

        works = self.work_dao.find_by_race_project(race_project_id)
        work_results = []
        all_risks = []

        if not works:
            all_risks.append({
                "risk_type": "no_work",
                "severity": "high",
                "message": "作品未提交",
                "action": "请提交你的作品",
            })
        else:
            for work in works:
                risks = self._check_work(work, rp)
                work_results.append({
                    "work_id": work["id"],
                    "title": work["title"],
                    "work_status": work["work_status"],
                    "risks": risks,
                    "ready": len(risks) == 0,
                })
                all_risks.extend(risks)

        overall_ready = len(all_risks) == 0

        return {
            "race_project_id": race_project_id,
            "race_name": race["name"] if race else None,
            "race_status": race["status"] if race else None,
            "works": work_results,
            "overall_ready": overall_ready,
            "risk_count": len(all_risks),
        }

    def check_for_organizer(
        self, race_id: int, user_id: int
    ) -> dict:
        """Organizer 查看全场准备度摘要。

        返回每个 RaceProject 的准备度概览。
        """
        check_managed_race(race_id, user_id)
        race_projects = self.race_project_dao.find_by_race(race_id)

        summaries = []
        total_works = 0
        ready_count = 0
        risk_distribution = {}

        for rp in race_projects:
            reg = self.registration_dao.find_by_id(rp["registration_id"])
            works = self.work_dao.find_by_race_project(rp["id"])

            rp_risks = []
            if not works:
                rp_risks.append("no_work")
            else:
                for work in works:
                    risks = self._check_work(work, rp)
                    for r in risks:
                        risk_type = r["risk_type"]
                        rp_risks.append(risk_type)
                        risk_distribution[risk_type] = (
                            risk_distribution.get(risk_type, 0) + 1
                        )
                    if work["work_status"] == "submitted":
                        total_works += 1
                        if len(risks) == 0:
                            ready_count += 1

            summaries.append({
                "race_project_id": rp["id"],
                "user_id": reg["user_id"] if reg else None,
                "username": None,  # 由路由层填充
                "work_count": len(works),
                "risks": list(set(rp_risks)),
                "ready": len(rp_risks) == 0 and len(works) > 0,
            })

        return {
            "race_id": race_id,
            "total_race_projects": len(race_projects),
            "total_works": total_works,
            "ready_works": ready_count,
            "ready_rate": round(ready_count / total_works, 2) if total_works > 0 else 0,
            "risk_distribution": risk_distribution,
            "summaries": summaries,
        }

    def _check_work(self, work: dict, rp: dict) -> list[dict]:
        """对单个 Work 执行检测规则，返回风险列表"""
        risks = []

        # 1. 作品未提交
        if work["work_status"] != "submitted":
            risks.append({
                "risk_type": "not_submitted",
                "severity": "high",
                "message": "作品未提交",
            })

        # 2. 作品信息不完整
        incomplete_fields = []
        if not work.get("title", "").strip():
            incomplete_fields.append("title")
        if not work.get("description", "").strip():
            incomplete_fields.append("description")
        if not work.get("readme_body", "").strip():
            incomplete_fields.append("readme_body")
        if incomplete_fields:
            risks.append({
                "risk_type": "incomplete_info",
                "severity": "medium",
                "message": f"作品信息不完整：缺少 {', '.join(incomplete_fields)}",
            })

        # 3. 缺少代码仓库或演示链接
        repo_url = work.get("repo_url", "").strip()
        demo_url = work.get("demo_url", "").strip()
        if not repo_url and not demo_url:
            risks.append({
                "risk_type": "missing_links",
                "severity": "medium",
                "message": "缺少代码仓库或演示链接",
            })

        # 4. CA 数据全部缺失
        ca_status = rp.get("aggregate_ingestion_status", "not_configured")
        if ca_status == "not_configured":
            risks.append({
                "risk_type": "no_ca_data",
                "severity": "low",
                "message": "缺少骑行过程数据",
            })

        # 5. CA 接入异常
        if ca_status == "failed" or rp.get("connection_health") in (
            "partial_failed",
            "all_failed",
        ):
            risks.append({
                "risk_type": "ca_error",
                "severity": "medium",
                "message": "CA 接入异常",
            })

        # 6. 评审得分偏低（已提交且有评分时）
        if work["work_status"] == "submitted":
            judgments = self.judgment_dao.find_by_work(work["id"])
            if judgments:
                avg = sum(
                    self.judgment_dao.compute_score(j) for j in judgments
                ) / len(judgments)
                if avg < 5:
                    risks.append({
                        "risk_type": "low_score",
                        "severity": "medium",
                        "message": f"评审得分偏低（均分 {avg:.1f}/10）",
                    })

        return risks
