"""
CA 蓝图（人员 D 交付）

提供：
- CA Policy 查询
- CA 连接 CRUD（登记/查看/更新/删除）
- CA 握手验证
- CA Session Ingestion（API Key 鉴权）
- CA 接入向导
- Rider/Organizer Session 查询
"""
from flask import Blueprint, request, g

from app.services.ca_service import CAService
from app.services.ca_ingestion_service import CAIngestionService
from app.utils.auth import require_auth
from app.utils.permissions import require_own_race_project
from app.utils.validation import validate
from app.utils.response import success, created
from app.utils.errors import NotFoundError
from app.schemas import (
    CAConnectionCreateSchema,
    CAConnectionEditSchema,
    CAWizardStepSchema,
    CASessionIngestSchema,
)

ca_bp = Blueprint("ca", __name__)
ca_service = CAService()
ingestion_service = CAIngestionService()


# ---- CA Policy 查询 ----

@ca_bp.route("/api/v1/rider/race-projects/<int:race_project_id>/ca-policy", methods=["GET"])
@require_auth
def get_ca_policy(race_project_id):
    """查询该赛事当前的 CA 策略"""
    policy = ca_service.get_ca_policy(race_project_id, g.current_user_id)
    return success(policy)


# ---- CA 连接 CRUD ----

@ca_bp.route("/api/v1/rider/race-projects/<int:race_project_id>/ca-connections", methods=["POST"])
@require_auth
@validate(CAConnectionCreateSchema())
def create_connection(race_project_id):
    """登记 CA 接入"""
    body = g.validated_body
    api_key = body.pop("api_key", "")
    config_json = body.pop("config_json", None)
    conn = ca_service.create_connection(
        race_project_id, g.current_user_id,
        ca_type=body["ca_type"],
        provider_name=body["provider_name"],
        api_key=api_key,
        config_json=config_json,
    )
    return created(conn)


@ca_bp.route("/api/v1/rider/race-projects/<int:race_project_id>/ca-connections", methods=["GET"])
@require_auth
def list_connections(race_project_id):
    """查看已登记的 CA 连接列表"""
    return success(ca_service.list_connections(race_project_id, g.current_user_id))


@ca_bp.route("/api/v1/rider/ca-connections/<int:connection_id>", methods=["GET"])
@require_auth
def get_connection(connection_id):
    """查看单个 CA 连接详情"""
    return success(ca_service.get_connection(connection_id, g.current_user_id))


@ca_bp.route("/api/v1/rider/ca-connections/<int:connection_id>", methods=["PUT"])
@require_auth
@validate(CAConnectionEditSchema())
def update_connection(connection_id):
    """更新 CA 配置"""
    body = g.validated_body
    api_key = body.pop("api_key", None)
    config_json = body.pop("config_json", None)
    provider_name = body.get("provider_name")
    conn = ca_service.update_connection(
        connection_id, g.current_user_id,
        provider_name=provider_name,
        api_key=api_key,
        config_json=config_json,
    )
    return success(conn)


@ca_bp.route("/api/v1/rider/ca-connections/<int:connection_id>", methods=["DELETE"])
@require_auth
def delete_connection(connection_id):
    """移除 CA 连接"""
    ca_service.delete_connection(connection_id, g.current_user_id)
    return success(None, "CA connection deleted")


# ---- CA 握手 ----

@ca_bp.route("/api/v1/ca-connections/<int:connection_id>/handshake", methods=["POST"])
@require_auth
def handshake(connection_id):
    """CA 握手验证"""
    conn = ca_service.handshake(connection_id, g.current_user_id)
    return success(conn)


# ---- CA Session Ingestion（API Key 鉴权，CSRF 已豁免） ----

@ca_bp.route("/api/v1/ca-connections/<int:connection_id>/ingest", methods=["POST"])
def ingest_session(connection_id):
    """接收 CA Session 数据。鉴权：请求头 X-API-Key。CSRF 已豁免。"""
    api_key = request.headers.get("X-API-Key", "")
    if not api_key:
        from app.utils.errors import UnauthorizedError
        raise UnauthorizedError("X-API-Key header required")

    body = request.get_json(silent=True) or {}
    session = ingestion_service.ingest(connection_id, api_key, body)
    return created(session)


# ---- Session 查询 ----

@ca_bp.route("/api/v1/rider/ca-connections/<int:connection_id>/sessions", methods=["GET"])
@require_auth
def list_sessions(connection_id):
    """Rider 查看自己的 CA Session 历史"""
    ca_service.get_connection(connection_id, g.current_user_id)  # 归属校验
    return success(ingestion_service.list_sessions(connection_id))


@ca_bp.route("/api/v1/organizer/races/<int:race_id>/ca-sessions", methods=["GET"])
@require_auth
def organizer_ca_sessions(race_id):
    """Organizer 查看全场 CA Session 摘要"""
    from app.utils.permissions import require_managed_race
    # 校验 managed race（内联，避免装饰器嵌套问题）
    from app.dao.race_dao import RaceDAO
    from app.utils.errors import ForbiddenError
    race = RaceDAO().find_by_id(race_id)
    if race is None:
        raise NotFoundError("Race not found")
    if race["created_by_user_id"] != g.current_user_id:
        raise ForbiddenError("You can only manage your own races")
    return success(ingestion_service.summarize_sessions_by_race(race_id))


# ---- CA 向导 ----

@ca_bp.route("/api/v1/rider/race-projects/<int:race_project_id>/ca-wizard", methods=["GET"])
@require_auth
def get_wizard(race_project_id):
    """获取 CA 接入向导状态"""
    wizard = ca_service.get_wizard(race_project_id, g.current_user_id)
    return success(wizard)


@ca_bp.route("/api/v1/rider/race-projects/<int:race_project_id>/ca-wizard/step/<int:step>", methods=["POST"])
@require_auth
def submit_wizard_step(race_project_id, step):
    """提交 CA 向导每步数据"""
    body = request.get_json(silent=True) or {}
    result = ca_service.submit_wizard_step(
        race_project_id, g.current_user_id, step, body
    )
    return success(result)
