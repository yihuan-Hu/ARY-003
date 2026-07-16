from flask import Blueprint, request, g, Response

from app.services.registration_service import RegistrationService
from app.services.race_project_service import RaceProjectService
from app.services.race_service import RaceService
from app.services.announcement_service import AnnouncementService
from app.services.award_service import AwardService
from app.services.readiness_service import ReviewReadinessService
from app.services.report_service import ReportService
from app.services.judging_service import JudgingService
from app.dao.race_dao import RaceDAO
from app.dao.work_dao import WorkDAO
from app.dao.judging_dao import JudgingRecordDAO, JudgeAssignmentDAO
from app.dao.registration_dao import RegistrationDAO
from app.dao.race_project_dao import RaceProjectDAO
from app.database import get_db
from app.services.integrity_service import verify_resource_integrity
from app.utils.auth import require_auth, require_role
from app.utils.permissions import (
    require_managed_race,
    require_readonly,
    check_managed_race,
)
from app.utils.errors import ValidationError, NotFoundError, ForbiddenError
from app.utils.response import success, created
from app.utils.validation import validate
from app.schemas import (
    RaceCreateSchema,
    RaceEditSchema,
    AnnouncementCreateSchema,
    AnnouncementEditSchema,
    AwardCreateSchema,
    AwardEditSchema,
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
award_service = AwardService()
readiness_service = ReviewReadinessService()
report_service = ReportService()
judging_service = JudgingService()
judgment_dao = JudgingRecordDAO()
assignment_dao = JudgeAssignmentDAO()
registration_dao = RegistrationDAO()
race_project_dao = RaceProjectDAO()


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


# =============================================
# 人员 C：奖项管理
# =============================================


@organizer_bp.route(
    "/api/v1/organizer/races/<int:race_id>/awards", methods=["POST"]
)
@require_auth
@require_role("organizer")
@require_managed_race()
@validate(AwardCreateSchema())
def create_award(race_id):
    award = award_service.create(race_id, g.current_user_id, g.validated_body)
    return created(award)


@organizer_bp.route(
    "/api/v1/organizer/races/<int:race_id>/awards", methods=["GET"]
)
@require_auth
@require_role("organizer")
@require_managed_race()
def list_awards(race_id):
    return success(award_service.list_for_race(race_id, g.current_user_id))


@organizer_bp.route(
    "/api/v1/organizer/awards/<int:award_id>", methods=["PUT"]
)
@require_auth
@require_role("organizer")
@validate(AwardEditSchema())
def update_award(award_id):
    return success(award_service.update(award_id, g.current_user_id, g.validated_body))


@organizer_bp.route(
    "/api/v1/organizer/awards/<int:award_id>", methods=["DELETE"]
)
@require_auth
@require_role("organizer")
def delete_award(award_id):
    return success(award_service.delete(award_id, g.current_user_id))


# =============================================
# 人员 C：CSV 数据导出
# =============================================


def _sanitize_csv_cell(value: str) -> str:
    """CSV 注入防护：以 =/+/-/@ 开头的单元格值加单引号前缀"""
    if value is None:
        return ""
    s = str(value)
    if s and s[0] in "=+-@":
        return "'" + s
    return s


def _csv_response(rows: list[dict], columns: list[str], filename: str) -> Response:
    """构建 CSV 响应"""
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)
    # 写表头
    writer.writerow(columns)
    # 写数据行
    for row in rows:
        writer.writerow([_sanitize_csv_cell(row.get(col, "")) for col in columns])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@organizer_bp.route(
    "/api/v1/organizer/races/<int:race_id>/export/registrations",
    methods=["GET"],
)
@require_auth
@require_role("organizer")
@require_managed_race()
def export_registrations(race_id):
    """导出报名数据 CSV"""
    from app.utils.logging import audit_log

    registrations = registration_dao.find_by_race(race_id)
    # 扩展用户信息
    rows = []
    for reg in registrations:
        user = get_db().execute(
            "SELECT username, display_name, school_org FROM users WHERE id = ?",
            (reg["user_id"],),
        ).fetchone()
        row = dict(reg)
        if user:
            row["username"] = user["username"]
            row["display_name"] = user["display_name"]
            row["school_org"] = user["school_org"]
        rows.append(row)

    audit_log("export.registrations", g.current_user_id, "race", race_id)
    columns = [
        "id", "username", "display_name", "school_org",
        "status", "submitted_at", "reviewed_at",
    ]
    return _csv_response(rows, columns, f"race_{race_id}_registrations.csv")


@organizer_bp.route(
    "/api/v1/organizer/races/<int:race_id>/export/judgments",
    methods=["GET"],
)
@require_auth
@require_role("organizer")
@require_managed_race()
def export_judgments(race_id):
    """导出评审结果 CSV"""
    from app.utils.logging import audit_log

    judgments = judgment_dao.find_by_race(race_id)
    rows = []
    for j in judgments:
        row = dict(j)
        # 不导出明文 comment 中的敏感信息，这里 comment 是评语，可以导出
        # 计算综合分
        row["total_score"] = round(judgment_dao.compute_score(j), 2)
        # 获取作品标题
        work = work_dao.find_by_id(j["work_id"])
        row["work_title"] = work["title"] if work else ""
        # 获取评委名
        judge = get_db().execute(
            "SELECT username FROM users WHERE id = ?", (j["judge_user_id"],)
        ).fetchone()
        row["judge_username"] = judge["username"] if judge else ""
        rows.append(row)

    audit_log("export.judgments", g.current_user_id, "race", race_id)
    columns = [
        "id", "work_id", "work_title", "judge_username",
        "technical_score", "innovation_score", "presentation_score",
        "completeness_score", "total_score", "comment",
        "submitted_at",
    ]
    return _csv_response(rows, columns, f"race_{race_id}_judgments.csv")


@organizer_bp.route(
    "/api/v1/organizer/races/<int:race_id>/export/works",
    methods=["GET"],
)
@require_auth
@require_role("organizer")
@require_managed_race()
def export_works(race_id):
    """导出作品列表 CSV（不导出明文 content）"""
    from app.utils.logging import audit_log

    works = work_dao.find_submitted_by_race(race_id)
    rows = []
    for w in works:
        row = {
            "id": w["id"],
            "title": w["title"],
            "description": w["description"],
            "repo_url": w["repo_url"],
            "demo_url": w["demo_url"],
            "work_status": w["work_status"],
            "visibility": w["visibility"],
            # 只导出 commitment，不导出明文 content
            "content_commitment": w.get("content_commitment", ""),
            "version": w["version"],
            "submitted_at": w["submitted_at"],
            "disqualified": w["disqualified"],
            "disqualify_reason": w.get("disqualify_reason", ""),
        }
        # 获取所属用户
        rp = race_project_dao.find_by_id(w["race_project_id"])
        if rp:
            reg = registration_dao.find_by_id(rp["registration_id"])
            if reg:
                user = get_db().execute(
                    "SELECT username FROM users WHERE id = ?",
                    (reg["user_id"],),
                ).fetchone()
                row["username"] = user["username"] if user else ""
        rows.append(row)

    audit_log("export.works", g.current_user_id, "race", race_id)
    columns = [
        "id", "title", "description", "repo_url", "demo_url",
        "work_status", "visibility", "content_commitment", "version",
        "submitted_at", "disqualified", "disqualify_reason", "username",
    ]
    return _csv_response(rows, columns, f"race_{race_id}_works.csv")


# =============================================
# 人员 C：Review Readiness（Organizer 视角）
# =============================================


@organizer_bp.route(
    "/api/v1/organizer/races/<int:race_id>/review-readiness",
    methods=["GET"],
)
@require_auth
@require_role("organizer")
@require_managed_race()
def get_organizer_readiness(race_id):
    """Organizer 查看全场准备度摘要"""
    result = readiness_service.check_for_organizer(race_id, g.current_user_id)
    # 填充 username
    for summary in result["summaries"]:
        if summary["user_id"]:
            user = get_db().execute(
                "SELECT username FROM users WHERE id = ?",
                (summary["user_id"],),
            ).fetchone()
            summary["username"] = user["username"] if user else None
    return success(result)


# =============================================
# 人员 C：评审结果汇总
# =============================================


@organizer_bp.route(
    "/api/v1/organizer/races/<int:race_id>/judgments",
    methods=["GET"],
)
@require_auth
@require_role("organizer")
@require_managed_race()
def summarize_judgments(race_id):
    """Organizer 查看赛事评审汇总（排名 + 评分详情）"""
    result = judging_service.summarize_judgments(race_id, g.current_user_id)
    return success(result)


# =============================================
# 人员 C：Report 模块
# =============================================


@organizer_bp.route(
    "/api/v1/organizer/races/<int:race_id>/report",
    methods=["GET"],
)
@require_auth
@require_role("organizer")
@require_managed_race()
def get_race_report(race_id):
    """赛事整体报告"""
    body = report_service.generate_race_report(race_id, g.current_user_id)
    saved = report_service.save_report(
        "race_report", g.current_user_id, race_id,
        f"Race Report - {body['race_name']}", body,
    )
    return success({"report": body, "saved_id": saved["id"]})


@organizer_bp.route(
    "/api/v1/organizer/races/<int:race_id>/review-summary",
    methods=["GET"],
)
@require_auth
@require_role("organizer")
@require_managed_race()
def get_review_summary(race_id):
    """评审汇总快照"""
    body = report_service.generate_review_summary(race_id, g.current_user_id)
    saved = report_service.save_report(
        "review_summary", g.current_user_id, race_id,
        f"Review Summary - {body['race_name']}", body,
    )
    return success({"report": body, "saved_id": saved["id"]})


@organizer_bp.route(
    "/api/v1/organizer/reports",
    methods=["GET"],
)
@require_auth
@require_role("organizer")
def list_my_reports():
    """查看自己生成的报告列表"""
    return success(report_service.get_reports_by_user(g.current_user_id))


@organizer_bp.route(
    "/api/v1/organizer/reports/<int:report_id>",
    methods=["GET"],
)
@require_auth
@require_role("organizer")
def get_report(report_id):
    """获取单个报告详情"""
    return success(report_service.get_report(report_id, g.current_user_id))
