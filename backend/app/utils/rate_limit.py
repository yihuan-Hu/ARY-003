"""
登录限流模块（人员 A 交付 — 生产级）

- IP 限流：同一 IP 5 分钟内 5 次登录失败 → 锁定 15 分钟
- 账号限流：同一账号累计 10 次登录失败 → 锁定 30 分钟
- 锁定期间返回 429 Too Many Requests

双层架构：内存缓存（快速） + SQLite 持久化（重启不丢失）。
"""
import time
from functools import wraps

from flask import request

# ---- 内存缓存（快速路径） ----
_ip_failures: dict[str, list[float]] = {}
_ip_lockout: dict[str, float] = {}
_account_failures: dict[str, int] = {}
_account_lockout: dict[str, float] = {}

IP_WINDOW_SECONDS = 300       # 5 分钟
IP_MAX_FAILURES = 5
IP_LOCKOUT_SECONDS = 900      # 15 分钟
ACCOUNT_MAX_FAILURES = 10
ACCOUNT_LOCKOUT_SECONDS = 1800  # 30 分钟


def _get_db_safe():
    """安全获取 DB 连接（表不存在时返回 None）"""
    try:
        from app.database import get_db
        return get_db()
    except Exception:
        return None


def _cleanup():
    """清理过期的内存记录"""
    now = time.time()
    for ip in list(_ip_failures):
        _ip_failures[ip] = [t for t in _ip_failures[ip] if now - t < IP_WINDOW_SECONDS]
        if not _ip_failures[ip]:
            del _ip_failures[ip]
    for ip in list(_ip_lockout):
        if now >= _ip_lockout[ip]:
            del _ip_lockout[ip]
    for username in list(_account_lockout):
        if now >= _account_lockout[username]:
            del _account_lockout[username]
            _account_failures.pop(username, None)


def check_login_allowed(username: str) -> None:
    """登录前调用。被限流则 raise RateLimitError(429)。"""
    from app.utils.errors import RateLimitError

    _cleanup()
    now = time.time()
    client_ip = request.remote_addr or "unknown"

    # --- 内存缓存检查（快速路径） ---

    # IP 锁
    if client_ip in _ip_lockout and now < _ip_lockout[client_ip]:
        remaining = int(_ip_lockout[client_ip] - now)
        raise RateLimitError(f"Too many login attempts from this IP. Try again in {remaining}s.")

    # 账号锁
    if username in _account_lockout and now < _account_lockout[username]:
        remaining = int(_account_lockout[username] - now)
        raise RateLimitError(f"Account temporarily locked. Try again in {remaining}s.")

    # --- SQLite 持久化检查（内存未命中时回退） ---
    db = _get_db_safe()
    if db:
        # 检查 IP 锁
        row = db.execute(
            "SELECT locked_until FROM login_rate_limit WHERE key = ? AND key_type = 'ip'",
            (client_ip,),
        ).fetchone()
        if row and row["locked_until"]:
            from datetime import datetime
            lock_until = datetime.fromisoformat(row["locked_until"]).timestamp()
            if now < lock_until:
                remaining = int(lock_until - now)
                raise RateLimitError(f"Too many login attempts from this IP. Try again in {remaining}s.")

        # 检查账号锁
        row = db.execute(
            "SELECT locked_until FROM login_rate_limit WHERE key = ? AND key_type = 'account'",
            (username,),
        ).fetchone()
        if row and row["locked_until"]:
            from datetime import datetime
            lock_until = datetime.fromisoformat(row["locked_until"]).timestamp()
            if now < lock_until:
                remaining = int(lock_until - now)
                raise RateLimitError(f"Account temporarily locked. Try again in {remaining}s.")


def record_login_failure(username: str) -> None:
    """登录失败后调用"""
    now = time.time()
    from datetime import datetime, timedelta
    client_ip = request.remote_addr or "unknown"

    # --- 内存缓存 ---
    if client_ip not in _ip_failures:
        _ip_failures[client_ip] = []
    _ip_failures[client_ip].append(now)
    recent = [t for t in _ip_failures[client_ip] if now - t < IP_WINDOW_SECONDS]
    _ip_failures[client_ip] = recent
    if len(recent) >= IP_MAX_FAILURES:
        _ip_lockout[client_ip] = now + IP_LOCKOUT_SECONDS

    _account_failures[username] = _account_failures.get(username, 0) + 1
    if _account_failures[username] >= ACCOUNT_MAX_FAILURES:
        _account_lockout[username] = now + ACCOUNT_LOCKOUT_SECONDS

    # --- SQLite 持久化 ---
    db = _get_db_safe()
    if db:
        # IP
        db.execute(
            """INSERT INTO login_rate_limit (key, key_type, failure_count, window_start)
               VALUES (?, 'ip', 1, datetime('now'))
               ON CONFLICT(key) DO UPDATE SET
                 failure_count = failure_count + 1,
                 window_start = CASE
                   WHEN datetime(window_start) < datetime('now', ?) THEN datetime('now')
                   ELSE window_start
                 END""",
            (client_ip, f'-{IP_WINDOW_SECONDS} seconds'),
        )
        row = db.execute(
            "SELECT failure_count FROM login_rate_limit WHERE key = ? AND key_type = 'ip'",
            (client_ip,),
        ).fetchone()
        if row and row["failure_count"] >= IP_MAX_FAILURES:
            lock_until = (datetime.utcnow() + timedelta(seconds=IP_LOCKOUT_SECONDS)).isoformat()
            db.execute(
                "UPDATE login_rate_limit SET locked_until = ? WHERE key = ? AND key_type = 'ip'",
                (lock_until, client_ip),
            )

        # Account
        db.execute(
            """INSERT INTO login_rate_limit (key, key_type, failure_count)
               VALUES (?, 'account', 1)
               ON CONFLICT(key) DO UPDATE SET failure_count = failure_count + 1""",
            (username,),
        )
        row = db.execute(
            "SELECT failure_count FROM login_rate_limit WHERE key = ? AND key_type = 'account'",
            (username,),
        ).fetchone()
        if row and row["failure_count"] >= ACCOUNT_MAX_FAILURES:
            lock_until = (datetime.utcnow() + timedelta(seconds=ACCOUNT_LOCKOUT_SECONDS)).isoformat()
            db.execute(
                "UPDATE login_rate_limit SET locked_until = ? WHERE key = ? AND key_type = 'account'",
                (lock_until, username),
            )

        db.commit()


def record_login_success(username: str) -> None:
    """登录成功后调用，清除该账号和 IP 的失败计数"""
    client_ip = request.remote_addr or "unknown"

    # 内存
    _account_failures.pop(username, None)
    _account_lockout.pop(username, None)
    _ip_failures.pop(client_ip, None)
    _ip_lockout.pop(client_ip, None)

    # SQLite
    db = _get_db_safe()
    if db:
        db.execute("DELETE FROM login_rate_limit WHERE key = ? AND key_type = 'account'", (username,))
        db.execute("DELETE FROM login_rate_limit WHERE key = ? AND key_type = 'ip'", (client_ip,))
        db.commit()
