"""
人员 C：评委路由（Judge 蓝图）

提供评委邀请接受/拒绝 + 评审清单查看 + 评分提交/修改。
"""
from flask import Blueprint, g, request

from app.services.judging_service import JudgingService
from app.dao.judging_dao import JudgingRecordDAO, JudgeAssignmentDAO
from app.dao.work_dao import WorkDAO
from app.utils.auth import require_auth, require_role
from app.utils.errors import NotFoundError, ForbiddenError
from app.utils.response import success, created
from app.utils.validation import validate
from app.schemas import JudgmentSubmitSchema

judge_bp = Blueprint("judge", __name__)

judging_service = JudgingService()
judgment_dao = JudgingRecordDAO()
assignment_dao = JudgeAssignmentDAO()
work_dao = WorkDAO()


# =============================================
# 评委邀请（接受/拒绝）
# =============================================


@judge_bp.route("/api/v1/judge/invitations", methods=["GET"])
@require_auth
@require_role("judge")
def list_my_invitations():
    """评委查看自己收到的邀请"""
    return success(judging_service.list_my_invitations(g.current_user_id))


@judge_bp.route(
    "/api/v1/judge/invitations/<int:invitation_id>/accept",
    methods=["POST"],
)
@require_auth
@require_role("judge")
def accept_invitation(invitation_id):
    """评委接受邀请"""
    result = judging_service.accept_invitation(invitation_id, g.current_user_id)
    return success(result)


@judge_bp.route(
    "/api/v1/judge/invitations/<int:invitation_id>/reject",
    methods=["POST"],
)
@require_auth
@require_role("judge")
def reject_invitation(invitation_id):
    """评委拒绝邀请"""
    result = judging_service.reject_invitation(invitation_id, g.current_user_id)
    return success(result)


# =============================================
# 评审清单 + 评分
# =============================================


@judge_bp.route("/api/v1/judge/assignments", methods=["GET"])
@require_auth
@require_role("judge")
def list_my_assignments():
    """评委查看自己的评审清单（含 Work 摘要 + Review Readiness 风险摘要）"""
    result = judging_service.list_my_assignments(g.current_user_id)
    return success(result)


@judge_bp.route("/api/v1/judge/works/<int:work_id>/judgments", methods=["POST"])
@require_auth
@require_role("judge")
@validate(JudgmentSubmitSchema())
def submit_judgment(work_id):
    """提交四维评分 + 评语"""
    record = judging_service.submit_judgment(
        work_id, g.current_user_id, g.validated_body
    )
    return created(record)


@judge_bp.route("/api/v1/judge/judgments/<int:judgment_id>", methods=["PUT"])
@require_auth
@require_role("judge")
@validate(JudgmentSubmitSchema())
def update_judgment(judgment_id):
    """修改评分"""
    record = judging_service.update_judgment(
        judgment_id, g.current_user_id, g.validated_body
    )
    return success(record)


@judge_bp.route("/api/v1/judge/judgments/<int:judgment_id>", methods=["GET"])
@require_auth
@require_role("judge")
def get_judgment(judgment_id):
    """查看自己的某条评分详情"""
    record = judgment_dao.find_by_id(judgment_id)
    if record is None:
        raise NotFoundError("Judgment not found")
    if record["judge_user_id"] != g.current_user_id:
        raise ForbiddenError("You can only view your own judgments")
    return success(record)
