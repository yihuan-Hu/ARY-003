from flask import Blueprint, request, g

from app.services.registration_service import RegistrationService
from app.dao.race_project_dao import RaceProjectDAO
from app.utils.auth import require_auth, require_role
from app.utils.permissions import require_own_registration, require_own_race_project
from app.utils.errors import ForbiddenError
from app.utils.response import success, created

rider_bp = Blueprint("rider", __name__)

reg_service = RegistrationService()
race_project_dao = RaceProjectDAO()


# =============================================
# Registration（报名）
# =============================================

@rider_bp.route("/api/v1/rider/races/<int:race_id>/registrations", methods=["POST"])
@require_auth
@require_role("contestant")
def submit_registration(race_id):
    registration = reg_service.submit(race_id, g.current_user_id)
    return created(registration)


@rider_bp.route("/api/v1/rider/registrations", methods=["GET"])
@require_auth
@require_role("contestant")
def list_my_registrations():
    registrations = reg_service.dao.find_by_user(g.current_user_id)
    return success(registrations)


@rider_bp.route("/api/v1/rider/registrations/<int:registration_id>", methods=["GET"])
@require_auth
@require_role("contestant")
@require_own_registration()
def get_my_registration(registration_id):
    """Rider 查看自己的报名（装饰器已校验归属，存入 g.current_registration）"""
    return success(g.current_registration)


@rider_bp.route("/api/v1/rider/registrations/<int:registration_id>/withdraw", methods=["POST"])
@require_auth
@require_role("contestant")
@require_own_registration()
def withdraw_registration(registration_id):
    """Rider 退赛（装饰器已校验归属）"""
    result = reg_service.withdraw(registration_id, g.current_user_id)
    return success(result)


# =============================================
# RaceProject（参赛工作区）
# =============================================

@rider_bp.route("/api/v1/rider/race-projects/<int:race_project_id>", methods=["GET"])
@require_auth
@require_role("contestant")
@require_own_race_project()
def get_my_race_project(race_project_id):
    """Rider 查看自己的 RaceProject（装饰器已校验归属链）"""
    rp = g.current_race_project
    return success({
        "id": rp["id"],
        "registration_id": rp["registration_id"],
        "aggregate_ingestion_status": rp["aggregate_ingestion_status"],
        "connection_health": rp["connection_health"],
        "created_at": rp["created_at"],
    })
