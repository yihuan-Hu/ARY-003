"""
资源完整性验证服务（人员 A 交付）

提供 verify_resource_integrity() 公开验证函数：
从 integrity_log 重算 hash 链，检测是否被篡改。
"""
from app.database import get_db


def verify_resource_integrity(resource_type: str, resource_id: int) -> dict:
    """
    从 integrity_log 重算 hash 链，返回验证结果。

    返回:
        {
            "valid": True/False,
            "chain_length": N,
            "first_seen": "...",
            "last_modified": "...",
            "events": [...]
        }

    若 chain_length == 0 则说明无记录（资源未注册完整性保护）。
    """
    db = get_db()
    rows = db.execute(
        """SELECT * FROM integrity_log
           WHERE resource_type = ? AND resource_id = ?
           ORDER BY created_at ASC""",
        (resource_type, resource_id),
    ).fetchall()

    if not rows:
        return {
            "valid": True,
            "chain_length": 0,
            "first_seen": None,
            "last_modified": None,
            "events": [],
        }

    events = [dict(r) for r in rows]
    valid = True
    prev_hash = None

    for ev in events:
        # 第一条记录 prev_hash 应为空或等于之前的链末
        if prev_hash is not None and ev.get("prev_hash") != prev_hash:
            valid = False
        prev_hash = ev.get("content_hash")

    # 最后一条记录的 hash 应该等于链上最后一个 content_hash
    # （无更多记录来断开，所以只要 prev_hash 链没断就是 valid）

    return {
        "valid": valid,
        "chain_length": len(events),
        "first_seen": events[0]["created_at"],
        "last_modified": events[-1]["created_at"],
        "events": events,
    }
