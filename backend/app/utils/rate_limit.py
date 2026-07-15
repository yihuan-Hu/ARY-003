"""
登录限流模块（人员 A 交付）

- IP 限流：同一 IP 5 分钟内 5 次登录失败 → 锁定 15 分钟
- 账号限流：同一账号累计 10 次登录失败 → 锁定 30 分钟
- 锁定期间返回 429 Too Many Requests
- 使用内存 dict + TTL 实现，无需 Redis
"""
import time
from functools import wraps

from flask import request, jsonify, g

# ---- 存储 ----
_ip_failures: dict[str, list[float]] = {}       # ip → [timestamp, ...]
_ip_lockout: dict[str, float] = {}               # ip → lockout_until_timestamp
_account_failures: dict[str, int] = {}            # username → failure_count
_account_lockout: dict[str, float] = {}           # username → lockout_until_timestamp

IP_WINDOW_SECONDS = 300       # 5 分钟窗口
IP_MAX_FAILURES = 5
IP_LOCKOUT_SECONDS = 900      # 15 分钟
ACCOUNT_MAX_FAILURES = 10
ACCOUNT_LOCKOUT_SECONDS = 1800  # 30 分钟


def _cleanup():
    """清理过期的 IP 记录和锁"""
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
    """
    登录前调用。如果被限流则 raise RateLimitError(429)，
    否则返回 None（允许继续登录）。
    """
    from app.utils.errors import RateLimitError

    _cleanup()
    now = time.time()
    client_ip = request.remote_addr or "unknown"

    # IP 锁检查
    if client_ip in _ip_lockout and now < _ip_lockout[client_ip]:
        remaining = int(_ip_lockout[client_ip] - now)
        raise RateLimitError(
            f"Too many login attempts from this IP. Try again in {remaining} seconds."
        )

    # 账号锁检查
    if username in _account_lockout and now < _account_lockout[username]:
        remaining = int(_account_lockout[username] - now)
        raise RateLimitError(
            f"Account temporarily locked. Try again in {remaining} seconds."
        )


def record_login_failure(username: str) -> None:
    """登录失败后调用"""
    now = time.time()
    client_ip = request.remote_addr or "unknown"

    # IP 失败记录
    if client_ip not in _ip_failures:
        _ip_failures[client_ip] = []
    _ip_failures[client_ip].append(now)

    # IP 锁定检查
    recent = [t for t in _ip_failures[client_ip] if now - t < IP_WINDOW_SECONDS]
    _ip_failures[client_ip] = recent
    if len(recent) >= IP_MAX_FAILURES:
        _ip_lockout[client_ip] = now + IP_LOCKOUT_SECONDS

    # 账号失败记录
    _account_failures[username] = _account_failures.get(username, 0) + 1
    if _account_failures[username] >= ACCOUNT_MAX_FAILURES:
        _account_lockout[username] = now + ACCOUNT_LOCKOUT_SECONDS


def record_login_success(username: str) -> None:
    """登录成功后调用，清除该账号的失败计数"""
    client_ip = request.remote_addr or "unknown"
    _account_failures.pop(username, None)
    _account_lockout.pop(username, None)
    _ip_failures.pop(client_ip, None)
    _ip_lockout.pop(client_ip, None)
