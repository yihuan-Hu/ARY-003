"""NotificationDAO（人员 A 交付 — 通知系统）"""
from app.dao.base import BaseDAO
from app.database import get_db


class NotificationDAO(BaseDAO):
    table = "notifications"

    def find_by_user(self, user_id: int, unread_only: bool = False,
                     page: int = 1, per_page: int = 20) -> dict:
        """分页查询用户通知"""
        filters = {"recipient_user_id": user_id}
        if unread_only:
            filters["is_read"] = 0
        return self.paginate(
            page=page, per_page=per_page, order_by="created_at DESC", **filters
        )

    def mark_read(self, notification_id: int, user_id: int) -> dict | None:
        """标记单条已读（校验归属）"""
        db = get_db()
        db.execute(
            "UPDATE notifications SET is_read = 1 WHERE id = ? AND recipient_user_id = ?",
            (notification_id, user_id),
        )
        db.commit()
        return self.find_by_id(notification_id)

    def mark_all_read(self, user_id: int) -> int:
        """全部已读，返回更新条数"""
        db = get_db()
        cursor = db.execute(
            "UPDATE notifications SET is_read = 1 WHERE recipient_user_id = ? AND is_read = 0",
            (user_id,),
        )
        db.commit()
        return cursor.rowcount

    def unread_count(self, user_id: int) -> int:
        db = get_db()
        row = db.execute(
            "SELECT COUNT(*) as cnt FROM notifications WHERE recipient_user_id = ? AND is_read = 0",
            (user_id,),
        ).fetchone()
        return row["cnt"] if row else 0
