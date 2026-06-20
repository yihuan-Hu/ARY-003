from flask import Blueprint, request, g

from app.dao.user_dao import UserDAO
from app.utils.auth import hash_password, verify_password, create_token, require_auth
from app.utils.errors import UnauthorizedError, ValidationError
from app.utils.response import success

auth_bp = Blueprint("auth", __name__)

user_dao = UserDAO()


@auth_bp.route("/api/v1/auth/login", methods=["POST"])
def login():
    body = request.get_json(silent=True) or {}
    username = body.get("username", "").strip()
    password = body.get("password", "")

    if not username or not password:
        raise ValidationError("Username and password are required")

    user = user_dao.find_by_username(username)
    if user is None or not verify_password(password, user["password_hash"]):
        raise UnauthorizedError("Invalid username or password")

    roles = user_dao.get_roles(user)
    token = create_token(user["id"], user["username"], roles)

    return success({
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "roles": roles,
        },
    })


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
