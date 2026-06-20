from flask import Blueprint, request, g

from app.services.registration_service import RegistrationService
from app.dao.race_dao import RaceDAO
from app.dao.race_project_dao import RaceProjectDAO
from app.utils.auth import require_auth, require_role
from app.utils.permissions import require_managed_race
from app.utils.errors import ValidationError
from app.utils.response import success, created

organizer_bp = Blueprint("organizer", __name__)

reg_service = RegistrationService()
race_dao = RaceDAO()
race_project_dao = RaceProjectDAO()


# =============================================
# Race 管理
# =============================================

@organizer_bp.route("/api/v1/organizer/races", methods=["POST"])
@require_auth
@require_role("organizer")
def create_race():
    body = request.get_json(silent=True) or {}
    name = body.get("name", "").strip()
    if not name:
        raise ValidationError("Race name is required")
    race = race_dao.create(
        name=name,
        created_by_user_id=g.current_user_id,
        slug=body.get("slug", name.lower().replace(" ", "-")),
        status=body.get("status", "upcoming"),
        description=body.get("description", ""),
    )
    return created(race)


@organizer_bp.route("/api/v1/organizer/races", methods=["GET"])
@require_auth
@require_role("organizer")
def list_my_races():
    races = race_dao.find_by_organizer(g.current_user_id)
    return success(races)


# =============================================
# Registration 管理（managed_race 装饰器统一校验赛事管理范围）
# =============================================

@organizer_bp.route("/api/v1/organizer/races/<int:race_id>/registrations", methods=["GET"])
@require_auth
@require_role("organizer")
@require_managed_race()
def list_race_registrations(race_id):
    """Organizer 查看自己管理的赛事的报名列表"""
    registrations = reg_service.dao.find_by_race(race_id)
    return success(registrations)


@organizer_bp.route("/api/v1/organizer/registrations/<int:registration_id>/approve", methods=["POST"])
@require_auth
@require_role("organizer")
def approve_registration(registration_id):
    """审批报名；RegistrationService 内部做 managed race 校验"""
    result = reg_service.approve_registration(registration_id, g.current_user_id)
    return success(result)


@organizer_bp.route("/api/v1/organizer/registrations/<int:registration_id>/reject", methods=["POST"])
@require_auth
@require_role("organizer")
def reject_registration(registration_id):
    """拒绝报名；RegistrationService 内部做 managed race 校验"""
    result = reg_service.reject_registration(registration_id, g.current_user_id)
    return success(result)


# =============================================
# RaceProject 管理
# =============================================

@organizer_bp.route("/api/v1/organizer/races/<int:race_id>/race-projects", methods=["GET"])
@require_auth
@require_role("organizer")
@require_managed_race()
def list_race_race_projects(race_id):
    """Organizer 查看自己管理的赛事的 RaceProjects 列表"""
    projects = race_project_dao.find_by_race(race_id)
    return success(projects)
