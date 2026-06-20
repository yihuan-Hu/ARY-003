import jwt
import hashlib
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import request, g, current_app

from app.utils.errors import UnauthorizedError, ForbiddenError


def hash_password(password: str) -> str:
    salt = "ary-salt-v1"
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()


def verify_password(password: str, password_hash: str) -> bool:
    return hash_password(password) == password_hash


def create_token(user_id: int, username: str, roles: list[str]) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "roles": roles,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=current_app.config["JWT_EXPIRATION_HOURS"]),
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm=current_app.config["JWT_ALGORITHM"])


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            current_app.config["SECRET_KEY"],
            algorithms=[current_app.config["JWT_ALGORITHM"]],
        )
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Token expired")
    except jwt.InvalidTokenError:
        raise UnauthorizedError("Invalid token")


def require_auth(f):
    """JWT 认证装饰器"""

    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise UnauthorizedError("Missing or invalid Authorization header")

        token = auth_header[7:]
        payload = decode_token(token)
        g.current_user_id = int(payload["sub"])
        g.current_username = payload["username"]
        g.current_roles = payload["roles"]
        return f(*args, **kwargs)

    return decorated


def require_role(role: str):
    """角色门禁装饰器"""

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
