"""
ARY 统一认证模块（人员 A 交付）

提供：
- 密码哈希：PBKDF2-SHA256、每用户随机盐、60 万次迭代
- 密码比较：hmac.compare_digest 常量时间
- 密码复杂度校验：≥8 位，含大小写字母 + 数字
- JWT 签发/解码：roles 数组在 payload 中
- 装饰器：@require_auth, @require_role, @require_any_role
- Token 黑名单（内存，logout 用）
"""
import hashlib
import hmac
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import current_app, g, request

from app.utils.errors import UnauthorizedError, ForbiddenError, ValidationError

# ---- Token 黑名单（内存缓存 + SQLite 持久化） ----
_token_blacklist: dict[str, float] = {}  # 内存缓存，重启后从 DB 恢复

# ---- 密码复杂度校验 ----

def _validate_password_complexity(password: str) -> None:
    """密码复杂度：≥8 位，含大小写字母 + 数字"""
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters")
    if not any(c.islower() for c in password):
        raise ValidationError("Password must contain at least one lowercase letter")
    if not any(c.isupper() for c in password):
        raise ValidationError("Password must contain at least one uppercase letter")
    if not any(c.isdigit() for c in password):
        raise ValidationError("Password must contain at least one digit")


# ---- PBKDF2 密码哈希（每用户随机盐 + 60 万次迭代） ----

def hash_password(password: str) -> str:
    """返回格式: pbkdf2_sha256$<hex_salt>$<hex_digest>"""
    _validate_password_complexity(password)
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        600_000,
    ).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    """常量时间比较，防 timing attack"""
    try:
        scheme, salt, expected = stored_hash.split("$", 2)
    except ValueError:
        return False
    if scheme != "pbkdf2_sha256":
        return False
    actual = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        600_000,
    ).hex()
    return hmac.compare_digest(actual, expected)


# ---- JWT ----

def create_token(user_id: int, username: str, roles: list[str]) -> str:
    """签发 access token，默认 1 小时过期"""
    payload = {
        "sub": str(user_id),
        "username": username,
        "roles": roles,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc)
        + timedelta(hours=current_app.config.get("JWT_EXPIRATION_HOURS", 1)),
        "jti": secrets.token_hex(8),  # 唯一 token ID，用于黑名单
    }
    return jwt.encode(
        payload,
        current_app.config["SECRET_KEY"],
        algorithm=current_app.config["JWT_ALGORITHM"],
    )


def create_refresh_token(user_id: int) -> str:
    """签发 refresh token，7 天有效"""
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(
        payload,
        current_app.config["SECRET_KEY"],
        algorithm=current_app.config["JWT_ALGORITHM"],
    )


def decode_token(token: str) -> dict:
    """解码 JWT，验证签名 + 过期 + 黑名单"""
    # 检查黑名单（先快速过滤已过期的条目）
    _cleanup_blacklist()
    try:
        payload = jwt.decode(
            token,
            current_app.config["SECRET_KEY"],
            algorithms=[current_app.config["JWT_ALGORITHM"]],
        )
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Token expired")
    except jwt.InvalidTokenError:
        raise UnauthorizedError("Invalid token")

    # logout 黑名单检查（仅 access token）
    if payload.get("type") != "refresh":
        jti = payload.get("jti")
        if jti and jti in _token_blacklist:
            raise UnauthorizedError("Token has been revoked")

    return payload


def revoke_token(token: str) -> None:
    """将 access token 加入黑名单（内存 + SQLite 持久化）"""
    try:
        payload = jwt.decode(
            token,
            current_app.config["SECRET_KEY"],
            algorithms=[current_app.config["JWT_ALGORITHM"]],
            options={"verify_exp": False},
        )
        jti = payload.get("jti")
        exp = payload.get("exp", 0)
        if jti:
            _token_blacklist[jti] = exp
            # 持久化到 SQLite
            try:
                from app.database import get_db as _get_db
                db = _get_db()
                db.execute(
                    "INSERT OR REPLACE INTO token_blacklist (jti, expires_at) VALUES (?, datetime(?, 'unixepoch'))",
                    (jti, exp),
                )
                db.commit()
            except Exception:
                pass  # DB 写入失败不影响 logout 核心功能（内存已有）
    except jwt.InvalidTokenError:
        pass


def _load_blacklist_from_db() -> None:
    """启动时从 SQLite 恢复未过期的黑名单"""
    try:
        from app.database import get_db as _get_db
        db = _get_db()
        rows = db.execute(
            "SELECT jti, expires_at FROM token_blacklist WHERE expires_at > datetime('now')"
        ).fetchall()
        now = time.time()
        for row in rows:
            from datetime import datetime as _dt
            try:
                exp_ts = _dt.fromisoformat(row["expires_at"]).timestamp()
                _token_blacklist[row["jti"]] = exp_ts
            except (ValueError, OSError):
                pass
        # 清理过期条目
        db.execute("DELETE FROM token_blacklist WHERE expires_at <= datetime('now')")
        db.commit()
    except Exception:
        pass  # 表不存在等情况，内存模式降级


def _cleanup_blacklist() -> None:
    """清理已过期的黑名单条目（内存 + DB）"""
    now = time.time()
    expired = [jti for jti, exp in _token_blacklist.items() if exp < now]
    for jti in expired:
        del _token_blacklist[jti]
    if expired:
        try:
            from app.database import get_db as _get_db
            db = _get_db()
            db.execute("DELETE FROM token_blacklist WHERE expires_at <= datetime('now')")
            db.commit()
        except Exception:
            pass


# ---- 装饰器 ----

def require_auth(f):
    """JWT 认证装饰器，注入 g.current_user_id / g.current_username / g.current_roles"""

    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise UnauthorizedError("Missing or invalid Authorization header")

        token = auth_header[7:]
        payload = decode_token(token)

        if payload.get("type") == "refresh":
            raise UnauthorizedError("Refresh token cannot be used as access token")

        g.current_user_id = int(payload["sub"])
        g.current_username = payload["username"]
        g.current_roles = payload["roles"]
        g.current_token_jti = payload.get("jti", "")
        return f(*args, **kwargs)

    return decorated


def require_role(role: str):
    """单角色门禁"""

    def decorator(f):
        @wraps(f)
        @require_auth
        def decorated(*args, **kwargs):
            if role not in g.current_roles:
                raise ForbiddenError(f"Role '{role}' required")
            return f(*args, **kwargs)

        return decorated

    return decorator


def require_any_role(*roles: str):
    """多角色任一满足"""

    def decorator(f):
        @wraps(f)
        @require_auth
        def decorated(*args, **kwargs):
            user_roles = set(g.current_roles)
            if not user_roles.intersection(roles):
                raise ForbiddenError(f"One of {roles} roles required")
            return f(*args, **kwargs)

        return decorated

    return decorator
