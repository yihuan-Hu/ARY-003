from flask import Blueprint, g, request

from app.services.registration_service import RegistrationService
from app.services.race_project_service import RaceProjectService
from app.services.work_service import WorkService
from app.services.coach_service import RidingCoachService
from app.services.readiness_service import ReviewReadinessService
from app.services.rider_profile_service import RiderProfileService
from app.services.report_service import ReportService
from app.dao.race_dao import RaceDAO
from app.dao.work_dao import WorkDAO
from app.utils.auth import require_auth, require_role
from app.utils.permissions import (
    require_own_registration,
    require_own_race_project,
    require_own_work,
)
from app.utils.response import success, created
from app.utils.errors import ValidationError
from app.utils.validation import validate
from app.schemas import WorkCreateSchema

rider_bp = Blueprint("rider", __name__)

reg_service = RegistrationService()
race_project_service = RaceProjectService()
race_dao = RaceDAO()
work_service = WorkService()
work_dao = WorkDAO()
coach_service = RidingCoachService()
readiness_service = ReviewReadinessService()
rider_profile_service = RiderProfileService()
report_service = ReportService()


def _pagination_args():
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(100, max(1, int(request.args.get("per_page", 20))))
    except ValueError as error:
        raise ValidationError("page and per_page must be integers") from error
    return page, per_page


# =============================================
# Registration（报名）
# =============================================

@rider_bp.route("/api/v1/rider/races/<int:race_id>/registrations", methods=["POST"])
@require_auth
@require_role("rider")
def submit_registration(race_id):
    registration = reg_service.submit(race_id, g.current_user_id)
    return created(registration)


@rider_bp.route("/api/v1/rider/registrations", methods=["GET"])
@require_auth
@require_role("rider")
def list_my_registrations():
    page, per_page = _pagination_args()
    registrations = reg_service.list_for_rider(
        g.current_user_id, page, per_page, request.args.get("status")
    )
    return success(registrations)


@rider_bp.route("/api/v1/rider/races", methods=["GET"])
@require_auth
@require_role("rider")
def list_my_races():
    registrations = reg_service.dao.find_by_user(g.current_user_id)
    races = []
    for race_id in dict.fromkeys(reg["race_id"] for reg in registrations):
        race = race_dao.find_by_id(race_id)
        if race:
            races.append({
                "race_id": race["id"],
                "name": race["name"],
                "status": race["status"],
            })
    return success(races)


@rider_bp.route("/api/v1/rider/registrations/<int:registration_id>", methods=["GET"])
@require_auth
@require_role("rider")
@require_own_registration()
def get_my_registration(registration_id):
    """Rider 查看自己的报名（装饰器已校验归属，存入 g.current_registration）"""
    return success(g.current_registration)


@rider_bp.route("/api/v1/rider/registrations/<int:registration_id>/withdraw", methods=["POST"])
@require_auth
@require_role("rider")
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
@require_role("rider")
@require_own_race_project()
def get_my_race_project(race_project_id):
    """Rider 查看自己的 RaceProject（装饰器已校验归属链，存入 g.current_race_project）

    返回最小字段 + 未来扩展占位：
    - ca_connections: []  → 未来 CAConnection 数组占位
    - work: null          → 未来主 Work 链接占位
    """
    return success(race_project_service._format(g.current_race_project))


@rider_bp.route(
    "/api/v1/rider/race-projects/<int:race_project_id>/next-actions",
    methods=["GET"],
)
@require_auth
@require_role("rider")
@require_own_race_project()
def next_actions(race_project_id):
    return success(
        coach_service.get_next_actions(race_project_id, g.current_user_id)
    )


@rider_bp.route(
    "/api/v1/rider/race-projects/<int:race_project_id>/works", methods=["POST"]
)
@require_auth
@require_role("rider")
@require_own_race_project()
@validate(WorkCreateSchema())
def create_work(race_project_id):
    work = work_service.create_draft(
        race_project_id, g.current_user_id, g.validated_body
    )
    return created(work)


@rider_bp.route(
    "/api/v1/rider/race-projects/<int:race_project_id>/works", methods=["GET"]
)
@require_auth
@require_role("rider")
@require_own_race_project()
def list_works(race_project_id):
    return success(work_dao.find_by_race_project(race_project_id))


@rider_bp.route("/api/v1/rider/works/<int:work_id>", methods=["PUT"])
@require_auth
@require_role("rider")
@require_own_work()
@validate(WorkCreateSchema())
def update_work(work_id):
    return success(work_service.update(work_id, g.current_user_id, g.validated_body))


@rider_bp.route("/api/v1/rider/works/<int:work_id>/submit", methods=["POST"])
@require_auth
@require_role("rider")
@require_own_work()
def submit_work(work_id):
    return success(work_service.submit(work_id, g.current_user_id))


@rider_bp.route("/api/v1/rider/works/<int:work_id>", methods=["DELETE"])
@require_auth
@require_role("rider")
@require_own_work()
def delete_work(work_id):
    work_service.delete(work_id, g.current_user_id)
    return success({"deleted": True})


# =============================================
# 人员 C：Review Readiness（Rider 视角）
# =============================================


@rider_bp.route(
    "/api/v1/rider/race-projects/<int:race_project_id>/review-readiness",
    methods=["GET"],
)
@require_auth
@require_role("rider")
@require_own_race_project()
def get_review_readiness(race_project_id):
    """Rider 查看自己 RaceProject 的评审准备度"""
    result = readiness_service.check_for_rider(race_project_id, g.current_user_id)
    return success(result)


# =============================================
# 人员 C：骑手档案（私有）
# =============================================


@rider_bp.route("/api/v1/rider/profile", methods=["GET"])
@require_auth
def get_my_profile():
    """Rider 查看自己的完整档案（含未公开 work）"""
    profile = rider_profile_service.get_private_profile(g.current_user_id)
    return success(profile)


# =============================================
# 人员 C：Rider Report
# =============================================


@rider_bp.route("/api/v1/rider/report", methods=["GET"])
@require_auth
def get_my_report():
    """Rider 查看自己的参赛报告"""
    body = report_service.generate_rider_report(g.current_user_id)
    saved = report_service.save_report(
        "rider_report", g.current_user_id, None,
        f"Rider Report - User {g.current_user_id}", body,
    )
    return success({"report": body, "saved_id": saved["id"]})
