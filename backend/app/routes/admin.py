"""
人员 C：管理后台路由（Admin 蓝图）

提供评委邀请 + 分配（批量 + 查看 + 取消）。
"""
from flask import Blueprint, g, request

from app.services.judging_service import JudgingService
from app.dao.judging_dao import JudgeAssignmentDAO
from app.utils.auth import require_auth, require_role
from app.utils.errors import ValidationError, NotFoundError
from app.utils.response import success, created
from app.utils.validation import validate
from app.schemas import JudgeAssignmentBatchSchema

admin_bp = Blueprint("admin", __name__)

judging_service = JudgingService()
assignment_dao = JudgeAssignmentDAO()


# =============================================
# 评委邀请（两步制：邀请 → 接受/拒绝 → 分配）
# =============================================


@admin_bp.route(
    "/api/v1/admin/races/<int:race_id>/judge-invitations",
    methods=["POST"],
)
@require_auth
@require_role("admin")
def invite_judge(race_id):
    """邀请评委加入赛事"""
    body = request.get_json(silent=True) or {}
    judge_user_id = body.get("judge_user_id")
    message = body.get("message", "")
    if not judge_user_id:
        raise ValidationError("judge_user_id is required")
    result = judging_service.invite_judge(
        race_id, int(judge_user_id), g.current_user_id, message
    )
    return created(result)


@admin_bp.route(
    "/api/v1/admin/races/<int:race_id>/judge-invitations",
    methods=["GET"],
)
@require_auth
@require_role("admin")
def list_judge_invitations(race_id):
    """查看赛事的所有评委邀请"""
    return success(judging_service.list_invitations(race_id, g.current_user_id))


# =============================================
# 评委分配
# =============================================


@admin_bp.route(
    "/api/v1/admin/races/<int:race_id>/judge-assignments",
    methods=["POST"],
)
@require_auth
@require_role("admin")
@validate(JudgeAssignmentBatchSchema())
def batch_assign_judges(race_id):
    """批量分配评委（仅已接受邀请的评委可被分配）"""
    body = g.validated_body
    assignments = body["assignments"]
    normalized = []
    for item in assignments:
        if "work_id" not in item or "judge_user_id" not in item:
            raise ValidationError(
                "Each assignment must have work_id and judge_user_id"
            )
        normalized.append({
            "work_id": int(item["work_id"]),
            "judge_user_id": int(item["judge_user_id"]),
        })

    result = judging_service.batch_assign(
        race_id, normalized, g.current_user_id
    )
    return created(result)


@admin_bp.route(
    "/api/v1/admin/races/<int:race_id>/judge-assignments",
    methods=["GET"],
)
@require_auth
@require_role("admin")
def list_judge_assignments(race_id):
    """查看当前分配情况"""
    result = judging_service.list_assignments(race_id, g.current_user_id)
    return success(result)


@admin_bp.route(
    "/api/v1/admin/judge-assignments/<int:assignment_id>",
    methods=["DELETE"],
)
@require_auth
@require_role("admin")
def delete_judge_assignment(assignment_id):
    """取消单条分配（评审尚未提交时）"""
    result = judging_service.delete_assignment(
        assignment_id, g.current_user_id
    )
    return success(result)
