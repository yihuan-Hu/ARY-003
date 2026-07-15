"""通知路由（人员 A 交付）"""
from flask import Blueprint, request, g

from app.services.notification_service import NotificationService
from app.utils.auth import require_auth
from app.utils.response import success

notification_bp = Blueprint("notification", __name__)

svc = NotificationService()


@notification_bp.route("/api/v1/notifications", methods=["GET"])
@require_auth
def list_notifications():
    unread_only = request.args.get("unread_only", "0") == "1"
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    result = svc.list_for_user(g.current_user_id, unread_only=unread_only,
                               page=page, per_page=per_page)
    return success(result)


@notification_bp.route("/api/v1/notifications/unread-count", methods=["GET"])
@require_auth
def unread_count():
    return success(svc.unread_count(g.current_user_id))


@notification_bp.route("/api/v1/notifications/<int:notification_id>/read", methods=["PUT"])
@require_auth
def mark_read(notification_id):
    return success(svc.mark_read(notification_id, g.current_user_id))


@notification_bp.route("/api/v1/notifications/read-all", methods=["PUT"])
@require_auth
def mark_all_read():
    return success(svc.mark_all_read(g.current_user_id))
