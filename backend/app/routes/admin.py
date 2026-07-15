"""
人员 C：管理后台路由（Admin 蓝图）

提供评委分配（批量 + 查看 + 取消）。
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


@admin_bp.route(
    "/api/v1/admin/races/<int:race_id>/judge-assignments",
    methods=["POST"],
)
@require_auth
@require_role("admin")
@validate(JudgeAssignmentBatchSchema())
def batch_assign_judges(race_id):
    """批量分配评委"""
    body = g.validated_body
    assignments = body["assignments"]
    # 转换格式：[{"work_id": 1, "judge_user_id": 5}, ...]
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
