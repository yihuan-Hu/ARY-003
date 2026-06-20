"""
ARY MVP 权限策略模块（角色 2 交付）

提供可复用的资源范围装饰器：
- require_own_registration: 报名归属校验
- require_own_race_project: RaceProject 归属校验
- require_managed_race: 赛事管理范围校验

所有装饰器依赖 require_auth 已注入的 g.current_user_id / g.current_roles。
"""
from functools import wraps

from flask import g

from app.dao.registration_dao import RegistrationDAO
from app.dao.race_project_dao import RaceProjectDAO
from app.dao.race_dao import RaceDAO
from app.utils.errors import ForbiddenError, NotFoundError


# ---- 资源范围 helper（非装饰器，供 Service 层直接调用） ----

def check_own_registration(registration_id: int, user_id: int) -> dict:
    """校验报名归属，返回 registration dict 或 raise"""
    reg = RegistrationDAO().find_by_id(registration_id)
    # own 资源对非 owner 隐藏存在性，避免通过 404/403 差异枚举报名 ID。
    if reg is None or reg["user_id"] != user_id:
        raise NotFoundError("Registration not found")
    return reg


def check_own_race_project(race_project_id: int, user_id: int) -> dict:
    """
    校验 RaceProject 归属。
    归属链: RaceProject → Registration → User
    返回 race_project dict 或 raise
    """
    rp = RaceProjectDAO().find_by_id(race_project_id)
    if rp is None:
        raise NotFoundError("RaceProject not found")

    reg = RegistrationDAO().find_by_id(rp["registration_id"])
    if reg is None or reg["user_id"] != user_id:
        raise NotFoundError("RaceProject not found")

    return rp


def check_managed_race(race_id: int, user_id: int) -> dict:
    """校验赛事管理范围，返回 race dict 或 raise"""
    race = RaceDAO().find_by_id(race_id)
    if race is None:
        raise NotFoundError("Race not found")
    if race["created_by_user_id"] != user_id:
        raise ForbiddenError("You can only manage your own races")
    return race


# ---- Flask 路由装饰器 ----

def require_own_registration(registration_id_param: str = "registration_id"):
    """
    装饰器：校验 URL 中的 registration_id 是否属于当前用户。

    用法:
        @rider_bp.route("/api/v1/rider/registrations/<int:registration_id>", methods=["GET"])
        @require_auth
        @require_own_registration()
        def get_my_registration(registration_id):
            # g.current_registration 已可用
            return success(g.current_registration)
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            registration_id = kwargs[registration_id_param]
            reg = check_own_registration(int(registration_id), g.current_user_id)
            g.current_registration = reg
            return f(*args, **kwargs)
        return decorated
    return decorator


def require_own_race_project(race_project_id_param: str = "race_project_id"):
    """
    装饰器：校验 URL 中的 race_project_id 是否属于当前用户。

    归属链: RaceProject → Registration → User

    用法:
        @rider_bp.route("/api/v1/rider/race-projects/<int:race_project_id>", methods=["GET"])
        @require_auth
        @require_own_race_project()
        def get_my_race_project(race_project_id):
            return success(g.current_race_project)
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            race_project_id = kwargs[race_project_id_param]
            rp = check_own_race_project(int(race_project_id), g.current_user_id)
            g.current_race_project = rp
            return f(*args, **kwargs)
        return decorated
    return decorator


def require_managed_race(race_id_param: str = "race_id"):
    """
    装饰器：校验 URL 中的 race_id 是否属于当前 organizer 管理的赛事。

    用法:
        @organizer_bp.route("/api/v1/organizer/races/<int:race_id>/registrations", methods=["GET"])
        @require_auth
        @require_role("organizer")
        @require_managed_race()
        def list_race_registrations(race_id):
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            race_id = kwargs[race_id_param]
            race = check_managed_race(int(race_id), g.current_user_id)
            g.current_race = race
            return f(*args, **kwargs)
        return decorated
    return decorator
