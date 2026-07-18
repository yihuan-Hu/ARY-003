"""
TimelineService（人员 D 交付）

提供：
- Rider 自己的 Evidence Timeline
- Organizer 查看选手的 Timeline
- 公开端 Timeline（仅摘要事件）
"""
from app.database import get_db
from app.dao.race_project_dao import RaceProjectDAO
from app.dao.registration_dao import RegistrationDAO
from app.dao.race_dao import RaceDAO
from app.utils.errors import NotFoundError


class TimelineService:
    def __init__(self):
        self.race_project_dao = RaceProjectDAO()
        self.registration_dao = RegistrationDAO()
        self.race_dao = RaceDAO()

    def get_timeline(self, race_project_id: int, user_id: int = None,
                     public: bool = False) -> list[dict]:
        """获取 RaceProject 的全部时间线事件。
        user_id: 用于归属校验（Rider/Organizer 视角）
        public: 是否公开视角（只展示可公开摘要事件）
        """
        rp = self.race_project_dao.find_by_id(race_project_id)
        if rp is None:
            raise NotFoundError("RaceProject not found")
        reg = self.registration_dao.find_by_id(rp["registration_id"])
        if reg is None:
            raise NotFoundError("Registration not found")

        events = []

        # 1. Registration 事件
        if reg["submitted_at"]:
            events.append({
                "event_type": "registration.submitted",
                "label": "报名提交",
                "timestamp": reg["submitted_at"],
                "detail": f"报名已提交" if not public else "选手报名参赛",
            })
        if reg["reviewed_at"] and reg["status"] in ("approved", "rejected"):
            events.append({
                "event_type": f"registration.{reg['status']}",
                "label": "报名审批通过" if reg["status"] == "approved" else "报名被拒绝",
                "timestamp": reg["reviewed_at"],
                "detail": "" if public else f"状态: {reg['status']}",
            })

        # 2. CA 连接事件（从 ca_connections + ca_sessions 表读取）
        db = get_db()
        ca_rows = db.execute(
            """SELECT cc.*, cs.created_at AS session_at,
                      cs.overall_progress, cs.round_progress, cs.cost_tokens,
                      cs.risk_level, cs.current_phase
               FROM ca_connections cc
               LEFT JOIN ca_sessions cs ON cs.ca_connection_id = cc.id
               WHERE cc.race_project_id = ?
               ORDER BY cc.created_at, cs.created_at""",
            (race_project_id,),
        ).fetchall()

        seen_connections = set()
        for row in ca_rows:
            cid = row["id"]  # ca_connection id
            if cid not in seen_connections:
                seen_connections.add(cid)
                handler = "CA 握手" if row["handshake_at"] else "CA 连接创建"
                events.append({
                    "event_type": "ca_connection.create",
                    "label": handler,
                    "timestamp": row["handshake_at"] or row["created_at"],
                    "detail": f"类型: {row['ca_type']}, Provider: {row['provider_name']}"
                    if not public else "编码助手已接入",
                })

            if row["session_at"] and not public:
                events.append({
                    "event_type": "ca_session.ingest",
                    "label": "CA Session 数据",
                    "timestamp": row["session_at"],
                    "detail": (
                        f"进度: {row['round_progress']:.0%}, "
                        f"Tokens: {row['cost_tokens']}, "
                        f"阶段: {row['current_phase']}"
                    ),
                    "data": {
                        "overall_progress": row["overall_progress"],
                        "round_progress": row["round_progress"],
                        "cost_tokens": row["cost_tokens"],
                        "risk_level": row["risk_level"],
                        "current_phase": row["current_phase"],
                    },
                })

        # 3. Work 事件
        work_rows = db.execute(
            """SELECT * FROM works
               WHERE race_project_id = ?
               ORDER BY created_at""",
            (race_project_id,),
        ).fetchall()
        for w in work_rows:
            events.append({
                "event_type": "work.created",
                "label": "作品创建",
                "timestamp": w["created_at"],
                "detail": f"《{w['title']}》" if not public else "提交了参赛作品",
            })
            if w["submitted_at"]:
                events.append({
                    "event_type": "work.submitted",
                    "label": "作品提交",
                    "timestamp": w["submitted_at"],
                    "detail": f"版本 v{w['version']}" if not public else "作品已提交",
                })

        # 4. Judging 事件
        judge_rows = db.execute(
            """SELECT jr.* FROM judging_records jr
               JOIN works w ON jr.work_id = w.id
               WHERE w.race_project_id = ?
               ORDER BY jr.submitted_at""",
            (race_project_id,),
        ).fetchall()
        for jr in judge_rows:
            total = sum(jr[k] or 0 for k in
                        ("technical_score", "innovation_score",
                         "presentation_score", "completeness_score"))
            if not public:
                detail = (
                    f"技术:{jr['technical_score']} 创新:{jr['innovation_score']} "
                    f"展示:{jr['presentation_score']} 完整度:{jr['completeness_score']} "
                    f"总分:{total}"
                )
            else:
                detail = f"总分: {total}"
            events.append({
                "event_type": "judgment.submitted",
                "label": "评审评分",
                "timestamp": jr["submitted_at"],
                "detail": detail,
            })

        # 5. Award 事件
        award_rows = db.execute(
            """SELECT a.* FROM awards a
               JOIN registrations r ON a.registration_id = r.id
               WHERE r.id = ? AND a.work_id IS NOT NULL
               ORDER BY a.created_at""",
            (reg["id"],),
        ).fetchall()
        for a in award_rows:
            events.append({
                "event_type": "award.created",
                "label": f"获奖: {a['title']}",
                "timestamp": a["created_at"],
                "detail": a.get("description", ""),
            })

        # 按时间排序
        events.sort(key=lambda e: e["timestamp"] or "")
        return events
