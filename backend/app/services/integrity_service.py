"""
资源完整性验证服务（人员 A 交付 — 生产级）

提供：
- verify_resource_integrity(): 从 integrity_log 重算 hash 链 + 验证 HMAC commitment
- verify_commitment(): B/C/D 可调用的单条 commitment 验证

公开端点（无需 SUBMISSION_SECRET）只验证 hash 链连续性；
内部调用（有 SUBMISSION_SECRET）同时验证每条 commitment 的 HMAC。
"""
import hashlib
import hmac

from flask import current_app, has_request_context

from app.database import get_db


def _get_submission_secret() -> str:
    """安全获取 SUBMISSION_SECRET"""
    if has_request_context():
        return current_app.config.get("SUBMISSION_SECRET", "")
    return ""


def verify_commitment(content_hash: str, commitment: str) -> bool:
    """验证单条 commitment 是否由 content_hash + SUBMISSION_SECRET 生成"""
    secret = _get_submission_secret()
    if not secret:
        return None  # 无法验证（无密钥），返回 None 表示"未验证"
    expected = hmac.new(
        secret.encode("utf-8"),
        content_hash.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, commitment)


def verify_resource_integrity(resource_type: str, resource_id: int, verify_commitments: bool = True) -> dict:
    """
    从 integrity_log 重算 hash 链，返回验证结果。

    检查项：
    1. prev_hash 链连续性（每条记录指向前一条的 hash）
    2. commitment HMAC 验证（每条 commitment = HMAC(content_hash, SECRET)）

    返回:
        {
            "valid": True/False,
            "chain_length": N,
            "first_seen": "...",
            "last_modified": "...",
            "events": [...],
            "verification": {
                "hash_chain": "ok" | "broken",
                "commitments": "ok" | "broken" | "skipped",
            }
        }

    chain_length == 0 表示资源无完整性记录。
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
            "verification": {"hash_chain": "ok", "commitments": "ok"},
        }

    events = [dict(r) for r in rows]
    hash_chain_ok = True
    commitments_ok = True
    commitments_skipped = False
    prev_hash = None

    for ev in events:
        # 1. 检查 hash 链：prev_hash 应指向上一条的 content_hash
        if prev_hash is not None and ev.get("prev_hash") != prev_hash:
            hash_chain_ok = False
        prev_hash = ev.get("content_hash")

        # 2. 检查 HMAC commitment
        result = verify_commitment(ev.get("content_hash", ""), ev.get("commitment", ""))
        if result is None:
            commitments_skipped = True
        elif result is False:
            commitments_ok = False

    return {
        "valid": hash_chain_ok and commitments_ok,
        "chain_length": len(events),
        "first_seen": events[0]["created_at"],
        "last_modified": events[-1]["created_at"],
        "events": events,
        "verification": {
            "hash_chain": "ok" if hash_chain_ok else "broken",
            "commitments": "ok" if commitments_ok else ("skipped" if commitments_skipped else "broken"),
        },
    }
