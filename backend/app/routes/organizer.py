from flask import Blueprint, request, g

from app.services.registration_service import RegistrationService
from app.services.race_project_service import RaceProjectService
from app.services.race_service import RaceService
from app.services.announcement_service import AnnouncementService
from app.dao.race_dao import RaceDAO
from app.dao.work_dao import WorkDAO
from app.database import get_db
from app.services.integrity_service import verify_resource_integrity
from app.utils.auth import require_auth, require_role
from app.utils.permissions import (
    require_managed_race,
    require_readonly,
    check_managed_race,
)
from app.utils.errors import ValidationError
from app.utils.response import success, created
from app.utils.validation import validate
from app.schemas import (
    RaceCreateSchema,
    RaceEditSchema,
    AnnouncementCreateSchema,
    AnnouncementEditSchema,
)
from app.dao.announcement_dao import AnnouncementDAO

organizer_bp = Blueprint("organizer", __name__)

reg_service = RegistrationService()
race_dao = RaceDAO()
race_project_service = RaceProjectService()
race_service = RaceService()
work_dao = WorkDAO()
announcement_service = AnnouncementService()
announcement_dao = AnnouncementDAO()


# =============================================
# Race 管理
# =============================================

@organizer_bp.route("/api/v1/organizer/races", methods=["POST"])
@require_auth
@require_role("organizer")
@validate(RaceCreateSchema())
def create_race():
    race = race_service.create(g.current_user_id, g.validated_body)
    return created(race)


@organizer_bp.route("/api/v1/organizer/races", methods=["GET"])
@require_auth
@require_role("organizer")
def list_my_races():
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(100, max(1, int(request.args.get("per_page", 20))))
    except ValueError as error:
        raise ValidationError("page and per_page must be integers") from error
    races = race_dao.paginate_by_organizer(g.current_user_id, page, per_page)
    return success(races)


@organizer_bp.route("/api/v1/organizer/races/<int:race_id>", methods=["GET"])
@require_auth
@require_role("organizer")
@require_managed_race()
def get_race(race_id):
    return success(g.current_race)


@organizer_bp.route("/api/v1/organizer/races/<int:race_id>", methods=["PUT"])
@require_auth
@require_role("organizer")
@require_managed_race()
@validate(RaceEditSchema())
def edit_race(race_id):
    return success(race_service.edit(race_id, g.current_user_id, g.validated_body))


def _transition_race(race_id, target_status):
    return success(race_service.transition(race_id, target_status, g.current_user_id))


@organizer_bp.route("/api/v1/organizer/races/<int:race_id>/publish", methods=["POST"])
@require_auth
@require_role("organizer")
@require_managed_race()
def publish_race(race_id):
    return _transition_race(race_id, "published")


@organizer_bp.route("/api/v1/organizer/races/<int:race_id>/open-registration", methods=["POST"])
@require_auth
@require_role("organizer")
@require_managed_race()
def open_registration(race_id):
    return _transition_race(race_id, "registration")


@organizer_bp.route("/api/v1/organizer/races/<int:race_id>/start", methods=["POST"])
@require_auth
@require_role("organizer")
@require_managed_race()
def start_race(race_id):
    return _transition_race(race_id, "running")


@organizer_bp.route("/api/v1/organizer/races/<int:race_id>/open-submissions", methods=["POST"])
@require_auth
@require_role("organizer")
@require_managed_race()
def open_submissions(race_id):
    return _transition_race(race_id, "submitting")


@organizer_bp.route("/api/v1/organizer/races/<int:race_id>/start-judging", methods=["POST"])
@require_auth
@require_role("organizer")
@require_managed_race()
def start_judging(race_id):
    return _transition_race(race_id, "judging")


@organizer_bp.route("/api/v1/organizer/races/<int:race_id>/complete", methods=["POST"])
@require_auth
@require_role("organizer")
@require_managed_race()
def complete_race(race_id):
    return _transition_race(race_id, "completed")


@organizer_bp.route("/api/v1/organizer/races/<int:race_id>/archive", methods=["POST"])
@require_auth
@require_role("organizer")
@require_managed_race()
def archive_race(race_id):
    return _transition_race(race_id, "archived")


# =============================================
# Registration 管理（managed_race 装饰器统一校验赛事管理范围）
# =============================================

@organizer_bp.route("/api/v1/organizer/races/<int:race_id>/registrations", methods=["GET"])
@require_auth
@require_role("organizer")
@require_managed_race()
def list_race_registrations(race_id):
    """Organizer 查看自己管理的赛事的报名列表"""
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(100, max(1, int(request.args.get("per_page", 20))))
    except ValueError as error:
        raise ValidationError("page and per_page must be integers") from error
    registrations = reg_service.list_for_organizer(
        race_id, g.current_user_id, page, per_page, request.args.get("status")
    )
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
    """Organizer 查看自己管理的赛事的 RaceProjects 列表（含基础状态与占位字段）

    装饰器已校验 managed race 范围并存入 g.current_race；
    Service 层再次校验并格式化响应。
    """
    projects = race_project_service.list_for_organizer(race_id, g.current_user_id)
    return success(projects)


@organizer_bp.route(
    "/api/v1/organizer/races/<int:race_id>/works", methods=["GET"]
)
@require_auth
@require_role("organizer")
@require_managed_race()
@require_readonly("work")
def list_race_works(race_id):
    return success(work_dao.find_submitted_by_race(race_id))


@organizer_bp.route("/api/v1/organizer/works/<int:work_id>", methods=["GET"])
@require_auth
@require_role("organizer")
def get_work(work_id):
    row = get_db().execute(
        """SELECT w.*, reg.race_id FROM works w
           JOIN race_projects rp ON w.race_project_id = rp.id
           JOIN registrations reg ON rp.registration_id = reg.id
           WHERE w.id = ?""",
        (work_id,),
    ).fetchone()
    if row is None:
        from app.utils.errors import NotFoundError

        raise NotFoundError("Work not found")
    check_managed_race(row["race_id"], g.current_user_id)
    result = dict(row)
    result["integrity"] = verify_resource_integrity("work", work_id)
    return success(result)


@organizer_bp.route(
    "/api/v1/organizer/races/<int:race_id>/announcements", methods=["POST"]
)
@require_auth
@require_role("organizer")
@require_managed_race()
@validate(AnnouncementCreateSchema())
def create_announcement(race_id):
    announcement = announcement_service.create(
        race_id, g.current_user_id, g.validated_body
    )
    return created(announcement)


@organizer_bp.route(
    "/api/v1/organizer/races/<int:race_id>/announcements", methods=["GET"]
)
@require_auth
@require_role("organizer")
@require_managed_race()
def list_announcements(race_id):
    return success(announcement_dao.find_by_race(race_id))


@organizer_bp.route(
    "/api/v1/organizer/announcements/<int:announcement_id>", methods=["PUT"]
)
@require_auth
@require_role("organizer")
@validate(AnnouncementEditSchema())
def update_announcement(announcement_id):
    return success(announcement_service.update(
        announcement_id, g.current_user_id, g.validated_body
    ))


@organizer_bp.route(
    "/api/v1/organizer/announcements/<int:announcement_id>/publish",
    methods=["POST"],
)
@require_auth
@require_role("organizer")
def publish_announcement(announcement_id):
    return success(announcement_service.set_visibility(
        announcement_id, g.current_user_id, "public"
    ))


@organizer_bp.route(
    "/api/v1/organizer/announcements/<int:announcement_id>/hide",
    methods=["POST"],
)
@require_auth
@require_role("organizer")
def hide_announcement(announcement_id):
    return success(announcement_service.set_visibility(
        announcement_id, g.current_user_id, "private"
    ))


@organizer_bp.route(
    "/api/v1/organizer/announcements/<int:announcement_id>",
    methods=["DELETE"],
)
@require_auth
@require_role("organizer")
def delete_announcement(announcement_id):
    announcement_service.delete(announcement_id, g.current_user_id)
    return success({"deleted": True})
