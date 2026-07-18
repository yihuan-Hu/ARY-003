from flask import Blueprint, request, g, make_response, redirect

from app.dao.user_dao import UserDAO
from app.utils.auth import (
    hash_password,
    verify_password,
    create_token,
    create_refresh_token,
    decode_token,
    revoke_token,
    require_auth,
)
from app.utils.rate_limit import check_login_allowed, record_login_failure, record_login_success
from app.utils.logging import audit_log
from app.utils.errors import UnauthorizedError, ValidationError, ForbiddenError
from app.utils.response import success

auth_bp = Blueprint("auth", __name__)

user_dao = UserDAO()


# ---- 注册 ----

@auth_bp.route("/api/v1/auth/register", methods=["POST"])
def register():
    """用户注册：校验用户名唯一性、密码复杂度、确认密码一致性"""
    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    confirm_password = body.get("confirm_password") or ""

    # 1. 非空校验
    if not username or not password or not confirm_password:
        raise ValidationError("Username, password, and confirm_password are required")

    # 2. 两次密码一致
    if password != confirm_password:
        raise ValidationError("Passwords do not match")

    # 3. 用户名格式校验（字母数字下划线，不允许纯数字开头）
    import re
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]{2,63}$', username):
        raise ValidationError(
            "Username must be 3-64 characters, start with a letter, "
            "and contain only letters, digits, and underscores"
        )

    # 4. 用户名唯一性校验
    if user_dao.find_by_username(username) is not None:
        raise ValidationError("Username already exists")

    # 5. 密码哈希（内部强制复杂度校验：≥8位、含大小写字母+数字）
    from app.utils.auth import hash_password as _hash_password
    password_hash = _hash_password(password)

    # 6. 角色选择（仅允许 rider 或 organizer）
    role = (body.get("role") or "rider").strip().lower()
    if role not in ("rider", "organizer"):
        raise ValidationError("Role must be 'rider' or 'organizer'")
    roles = [role]

    # 7. 入库
    user = user_dao.create(username, password_hash, roles=roles)

    # 8. 自动登录，签发 token
    access_token = create_token(user["id"], user["username"], roles)
    refresh_token = create_refresh_token(user["id"])

    audit_log("auth.register.success", user["id"], "user", user["id"])

    resp = make_response(success({
        "token": access_token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "roles": roles,
        },
    }, "Registration successful"))
    resp.set_cookie(
        "refresh_token",
        refresh_token,
        httponly=True,
        secure=False,
        samesite="Strict",
        max_age=7 * 24 * 3600,
        path="/api/v1/auth",
    )
    return resp


# ---- 登录 ----

@auth_bp.route("/api/v1/auth/login", methods=["POST"])
def login():
    body = request.get_json(silent=True) or {}
    username = body.get("username", "").strip()
    password = body.get("password", "")

    if not username or not password:
        raise ValidationError("Username and password are required")

    # 限流检查
    check_login_allowed(username)

    user = user_dao.find_by_username(username)
    if user is None or not verify_password(password, user["password_hash"]):
        record_login_failure(username)
        audit_log("auth.login.failed", 0, "user", None, f"username={username}")
        raise UnauthorizedError("Invalid username or password")

    record_login_success(username)
    roles = user_dao.get_roles(user)
    access_token = create_token(user["id"], user["username"], roles)
    refresh_token = create_refresh_token(user["id"])

    audit_log("auth.login.success", user["id"], "user", user["id"])

    # refresh token 写入 httpOnly cookie
    resp = make_response(success({
        "token": access_token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "roles": roles,
        },
    }))
    resp.set_cookie(
        "refresh_token",
        refresh_token,
        httponly=True,
        secure=False,  # 生产环境应设为 True + HTTPS
        samesite="Strict",
        max_age=7 * 24 * 3600,  # 7 天
        path="/api/v1/auth",
    )
    return resp


# ---- Token 刷新 ----

@auth_bp.route("/api/v1/auth/refresh", methods=["POST"])
def refresh():
    """用 refresh token（httpOnly cookie）换新 access token"""
    refresh_token = request.cookies.get("refresh_token", "")
    if not refresh_token:
        raise UnauthorizedError("Refresh token required")

    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise UnauthorizedError("Invalid refresh token")

    user_id = int(payload["sub"])
    user = user_dao.find_by_id(user_id)
    if user is None:
        raise UnauthorizedError("User not found")

    roles = user_dao.get_roles(user)
    access_token = create_token(user["id"], user["username"], roles)

    return success({"token": access_token})


# ---- 登出 ----

@auth_bp.route("/api/v1/auth/logout", methods=["POST"])
def logout():
    """access token 加入黑名单 + 清除 refresh cookie"""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        revoke_token(auth_header[7:])

    resp = make_response(success(None, "Logged out"))
    resp.set_cookie(
        "refresh_token",
        "",
        httponly=True,
        secure=False,
        samesite="Strict",
        max_age=0,
        path="/api/v1/auth",
    )
    return resp


# ---- 当前用户 ----

@auth_bp.route("/api/v1/auth/me", methods=["GET"])
@require_auth
def me():
    user = user_dao.find_by_id(g.current_user_id)
    if user is None:
        raise UnauthorizedError("User not found")

    return success({
        "id": user["id"],
        "username": user["username"],
        "roles": user_dao.get_roles(user),
    })


# ---- 个人信息 ----

@auth_bp.route("/api/v1/auth/profile", methods=["GET"])
@require_auth
def get_profile():
    """查看个人信息"""
    user = user_dao.find_by_id(g.current_user_id)
    if user is None:
        raise UnauthorizedError("User not found")

    return success({
        "id": user["id"],
        "username": user["username"],
        "github_login": user.get("github_login", ""),
        "roles": user_dao.get_roles(user),
        "profile_completed": bool(user.get("profile_completed", 0)),
        "display_name": user.get("display_name", ""),
        "school_org": user.get("school_org", ""),
        "bio": user.get("bio", ""),
    })


@auth_bp.route("/api/v1/auth/profile", methods=["PUT"])
@require_auth
def update_profile():
    """完善个人信息"""
    body = request.get_json(silent=True) or {}

    user = user_dao.find_by_id(g.current_user_id)
    if user is None:
        raise UnauthorizedError("User not found")

    updates = {}
    for field in ("display_name", "school_org", "bio"):
        if field in body:
            updates[field] = str(body[field]).strip()

    if updates:
        user_dao.update(g.current_user_id, **updates)

    # 如果三个字段都已填写，标记 profile_completed
    updated = user_dao.find_by_id(g.current_user_id)
    if all(updated.get(f, "") for f in ("display_name", "school_org", "bio")):
        user_dao.update(g.current_user_id, profile_completed=1)

    return success({
        "id": updated["id"],
        "username": updated["username"],
        "profile_completed": bool(updated.get("profile_completed", 0)),
    })


# ---- GitHub OAuth（人员 D） ----

@auth_bp.route("/api/v1/auth/github", methods=["GET"])
def github_login():
    """发起 GitHub OAuth 授权"""
    redirect_uri = request.args.get("redirect_uri", "")
    if not redirect_uri:
        redirect_uri = request.host_url.rstrip("/") + "/api/v1/auth/github/callback"
    try:
        from app.services.oauth_service import GitHubOAuthService
        svc = GitHubOAuthService()
        url, state = svc.get_authorize_url(redirect_uri)
        resp = redirect(url)
        resp.set_cookie("oauth_state", state, httponly=True, samesite="Lax", max_age=600)
        return resp
    except RuntimeError as e:
        raise ValidationError(str(e))


@auth_bp.route("/api/v1/auth/github/callback", methods=["GET"])
def github_callback():
    """GitHub OAuth 回调处理"""
    code = request.args.get("code", "")
    state = request.args.get("state", "")

    if not code:
        raise ValidationError("Missing authorization code")

    try:
        from app.services.oauth_service import GitHubOAuthService
        svc = GitHubOAuthService()
        result = svc.handle_callback(code, state)
        resp = make_response(success({
            "token": result["token"],
            "user": result["user"],
            "is_new": result["is_new"],
        }))
        return resp
    except RuntimeError as e:
        raise ValidationError(str(e))
