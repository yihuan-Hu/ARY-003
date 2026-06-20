from flask import Blueprint, request, g

from app.services.registration_service import RegistrationService
from app.dao.race_project_dao import RaceProjectDAO
from app.utils.auth import require_role
from app.utils.errors import ForbiddenError, NotFoundError
from app.utils.response import success, created

rider_bp = Blueprint("rider", __name__)

reg_service = RegistrationService()
race_project_dao = RaceProjectDAO()


@rider_bp.route("/api/v1/rider/races/<int:race_id>/registrations", methods=["POST"])
@require_role("contestant")
def submit_registration(race_id):
    registration = reg_service.submit(race_id, g.current_user_id)
    return created(registration)


@rider_bp.route("/api/v1/rider/registrations", methods=["GET"])
@require_role("contestant")
def list_my_registrations():
    registrations = reg_service.dao.find_by_user(g.current_user_id)
    return success(registrations)


@rider_bp.route("/api/v1/rider/registrations/<int:registration_id>", methods=["GET"])
@require_role("contestant")
def get_my_registration(registration_id):
    reg = reg_service.dao.find_by_id(registration_id)
    if reg is None:
        raise NotFoundError("Registration not found")
    if reg["user_id"] != g.current_user_id:
        raise ForbiddenError("You can only view your own registration")
    return success(reg)


@rider_bp.route("/api/v1/rider/race-projects/<int:race_project_id>", methods=["GET"])
@require_role("contestant")
def get_my_race_project(race_project_id):
    rp = race_project_dao.find_by_id(race_project_id)
    if rp is None:
        raise NotFoundError("RaceProject not found")

    # 验证归属：RaceProject → Registration → User
    reg = reg_service.dao.find_by_id(rp["registration_id"])
    if reg is None or reg["user_id"] != g.current_user_id:
        raise ForbiddenError("You can only view your own RaceProject")

    return success({
        "id": rp["id"],
        "registration_id": rp["registration_id"],
        "aggregate_ingestion_status": rp["aggregate_ingestion_status"],
        "connection_health": rp["connection_health"],
        "created_at": rp["created_at"],
    })
