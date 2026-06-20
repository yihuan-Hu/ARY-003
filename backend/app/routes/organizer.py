from flask import Blueprint, request, g

from app.services.registration_service import RegistrationService
from app.dao.race_dao import RaceDAO
from app.dao.race_project_dao import RaceProjectDAO
from app.utils.auth import require_role
from app.utils.errors import ForbiddenError, NotFoundError, ValidationError
from app.utils.response import success, created

organizer_bp = Blueprint("organizer", __name__)

reg_service = RegistrationService()
race_dao = RaceDAO()
race_project_dao = RaceProjectDAO()


def _require_managed_race(race_id: int):
    """检查当前用户是否是 race 的 organizer"""
    race = race_dao.find_by_id(race_id)
    if race is None:
        raise NotFoundError("Race not found")
    if race["created_by_user_id"] != g.current_user_id:
        raise ForbiddenError("You can only manage your own races")
    return race


# =============================================
# Race 管理
# =============================================

@organizer_bp.route("/api/v1/organizer/races", methods=["POST"])
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
@require_role("organizer")
def list_my_races():
    races = race_dao.find_by_organizer(g.current_user_id)
    return success(races)


# =============================================
# Registration 管理
# =============================================

@organizer_bp.route("/api/v1/organizer/races/<int:race_id>/registrations", methods=["GET"])
@require_role("organizer")
def list_race_registrations(race_id):
    _require_managed_race(race_id)
    registrations = reg_service.dao.find_by_race(race_id)
    return success(registrations)


@organizer_bp.route("/api/v1/organizer/registrations/<int:registration_id>/approve", methods=["POST"])
@require_role("organizer")
def approve_registration(registration_id):
    # Service 内部会做 managed race 校验
    result = reg_service.approve_registration(registration_id, g.current_user_id)
    return success(result)


@organizer_bp.route("/api/v1/organizer/registrations/<int:registration_id>/reject", methods=["POST"])
@require_role("organizer")
def reject_registration(registration_id):
    result = reg_service.reject_registration(registration_id, g.current_user_id)
    return success(result)


@organizer_bp.route("/api/v1/organizer/races/<int:race_id>/race-projects", methods=["GET"])
@require_role("organizer")
def list_race_race_projects(race_id):
    _require_managed_race(race_id)
    projects = race_project_dao.find_by_race(race_id)
    return success(projects)
