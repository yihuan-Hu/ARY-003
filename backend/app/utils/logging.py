"""
结构化日志 + 审计日志 + 日志脱敏（人员 A 交付）
"""
import json
import re
import time
import uuid
from functools import wraps

from flask import g, request, current_app

_SENSITIVE_FIELDS = {"token", "password", "password_hash", "api_key", "secret"}


def _mask(data: dict) -> dict:
    """脱敏：自动过滤敏感字段"""
    if not isinstance(data, dict):
        return data
    result = {}
    for k, v in data.items():
        if k.lower() in _SENSITIVE_FIELDS:
            result[k] = "[REDACTED]"
        elif isinstance(v, dict):
            result[k] = _mask(v)
        else:
            result[k] = v
    return result


def request_log():
    """
    结构化 HTTP 请求日志（在 after_request 中调用）。
    格式: timestamp method path status_code duration_ms user_id request_id
    """
    from app.database import get_db

    duration_ms = int((time.time() - g.get("_request_start", time.time())) * 1000)

    log_entry = {
        "method": request.method,
        "path": request.path,
        "status_code": getattr(g, "_response_status", 0),
        "duration_ms": duration_ms,
        "user_id": getattr(g, "current_user_id", None),
        "request_id": getattr(g, "request_id", "unknown"),
        "remote_addr": request.remote_addr,
    }

    # 输出到 stdout（可被日志收集器抓取）
    print(json.dumps(log_entry, ensure_ascii=False, default=str))


def request_start():
    """记录请求开始时间"""
    g._request_start = time.time()


# ---- 审计日志 ----

def audit_log(action: str, actor_user_id: int, target_type: str,
              target_id: int = None, detail: str = "") -> None:
    """
    写入审计日志到 audit_logs 表。

    B/C/D 在所有写操作后调用此函数。

    用法:
        from app.utils.logging import audit_log
        audit_log("registration.approve", current_user_id, "registration", reg_id, "Approved by organizer")
    """
    from app.database import get_db

    try:
        db = get_db()
        db.execute(
            """INSERT INTO audit_logs (action, actor_user_id, target_type, target_id, detail, request_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                action,
                actor_user_id,
                target_type,
                target_id,
                detail,
                getattr(g, "request_id", "unknown"),
            ),
        )
        db.commit()
    except Exception as exc:
        # 审计日志写入失败不应阻断主业务流程，但必须输出到 stderr 供运维发现
        import sys
        import traceback
        print(
            f"[ARY] AUDIT_LOG_FAILED: action={action} target={target_type}/{target_id} "
            f"error={exc}",
            file=sys.stderr,
        )
        traceback.print_exc(file=sys.stderr)
