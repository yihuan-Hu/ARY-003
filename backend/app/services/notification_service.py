"""NotificationService（人员 A 交付 — 通知系统）

提供 send() 供 B/C/D 在关键事件时调用。
"""
from app.dao.notification_dao import NotificationDAO
from app.utils.errors import NotFoundError, ForbiddenError


class NotificationService:
    def __init__(self):
        self.dao = NotificationDAO()

    # ---- B/C/D 调用 ----

    def send(self, user_id: int, title: str, body: str = "", link: str = "") -> dict:
        """发送通知。B/C/D 在关键事件后调用。"""
        return self.dao.create(
            recipient_user_id=user_id,
            title=title,
            body=body,
            link=link,
        )

    # ---- API 层 ----

    def list_for_user(self, user_id: int, unread_only: bool = False,
                      page: int = 1, per_page: int = 20) -> dict:
        return self.dao.find_by_user(user_id, unread_only=unread_only,
                                     page=page, per_page=per_page)

    def mark_read(self, notification_id: int, user_id: int) -> dict:
        result = self.dao.mark_read(notification_id, user_id)
        if result is None:
            raise NotFoundError("Notification not found")
        return result

    def mark_all_read(self, user_id: int) -> dict:
        count = self.dao.mark_all_read(user_id)
        return {"marked_read": count}

    def unread_count(self, user_id: int) -> dict:
        return {"unread": self.dao.unread_count(user_id)}
