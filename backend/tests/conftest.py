import os
import tempfile

import pytest
import json

from app import create_app
from app.config import TestConfig
from app.database import get_db
from app.utils.auth import hash_password


@pytest.fixture
def app():
    """每个测试独立的临时数据库文件，测试结束后清理"""
    fd, db_path = tempfile.mkstemp(suffix=".db", prefix="ary_test_")
    os.close(fd)
    os.unlink(db_path)
    TestConfig.DATABASE_PATH = db_path
    app = create_app(TestConfig)
    yield app
    # 关闭连接后清理
    with app.app_context():
        db = get_db()
        db.close()
    try:
        os.unlink(db_path)
        os.unlink(db_path + "-wal")
        os.unlink(db_path + "-shm")
    except OSError:
        pass


@pytest.fixture
def client(app):
    return app.test_client()


# =============================================
# 工具函数
# =============================================

def _login(client, username, password):
    resp = client.post("/api/v1/auth/login",
                       data=json.dumps({"username": username, "password": password}),
                       content_type="application/json")
    return json.loads(resp.data)["data"]["token"]


def _db_execute(app, sql, params=()):
    """在 app context 内执行 SQL"""
    with app.app_context():
        db = get_db()
        cursor = db.execute(sql, params)
        db.commit()
        return cursor


def _db_fetchone(app, sql, params=()):
    with app.app_context():
        db = get_db()
        return db.execute(sql, params).fetchone()


def _create_user(app, username, password, roles):
    """通过 API 创建用户（更接近实际流程）或直接通过 DB 创建"""
    import json as _json
    with app.app_context():
        db = get_db()
        pw_hash = hash_password(password)
        roles_json = _json.dumps(roles)
        cursor = db.execute(
            "INSERT INTO users (username, password_hash, roles) VALUES (?, ?, ?)",
            (username, pw_hash, roles_json),
        )
        db.commit()
        user_id = cursor.lastrowid
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row)


# =============================================
# 用户 Fixture
# =============================================

@pytest.fixture
def admin_user(app):
    return _create_user(app, "admin", "Admin123!", ["admin", "organizer"])


@pytest.fixture
def admin_token(client, admin_user):
    return _login(client, "admin", "Admin123!")


@pytest.fixture
def organizer_a(app):
    return _create_user(app, "organizer_a", "Organizer123!", ["organizer"])


@pytest.fixture
def organizer_a_token(client, organizer_a):
    return _login(client, "organizer_a", "Organizer123!")


@pytest.fixture
def organizer_b(app):
    return _create_user(app, "organizer_b", "Organizer123!", ["organizer"])


@pytest.fixture
def organizer_b_token(client, organizer_b):
    return _login(client, "organizer_b", "Organizer123!")


@pytest.fixture
def rider_a(app):
    return _create_user(app, "rider_a", "Rider123!", ["rider"])


@pytest.fixture
def rider_a_token(client, rider_a):
    return _login(client, "rider_a", "Rider123!")


@pytest.fixture
def rider_b(app):
    return _create_user(app, "rider_b", "Rider123!", ["rider"])


@pytest.fixture
def rider_b_token(client, rider_b):
    return _login(client, "rider_b", "Rider123!")


# =============================================
# Race Fixture（通过 API 创建，测试也覆盖了 API）
# =============================================

@pytest.fixture
def race_a(client, organizer_a, organizer_a_token):
    resp = client.post("/api/v1/organizer/races",
                       data=json.dumps({"name": "Race A"}),
                       content_type="application/json",
                       headers={"Authorization": f"Bearer {organizer_a_token}"})
    race = json.loads(resp.data)["data"]
    for action in ("publish", "open-registration"):
        transition = client.post(
            f"/api/v1/organizer/races/{race['id']}/{action}",
            headers={"Authorization": f"Bearer {organizer_a_token}"},
        )
        assert transition.status_code == 200
        race = json.loads(transition.data)["data"]
    return race


@pytest.fixture
def race_b(client, organizer_b, organizer_b_token):
    resp = client.post("/api/v1/organizer/races",
                       data=json.dumps({"name": "Race B"}),
                       content_type="application/json",
                       headers={"Authorization": f"Bearer {organizer_b_token}"})
    race = json.loads(resp.data)["data"]
    for action in ("publish", "open-registration"):
        transition = client.post(
            f"/api/v1/organizer/races/{race['id']}/{action}",
            headers={"Authorization": f"Bearer {organizer_b_token}"},
        )
        assert transition.status_code == 200
        race = json.loads(transition.data)["data"]
    return race
