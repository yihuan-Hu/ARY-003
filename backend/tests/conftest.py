import pytest
import json

from app import create_app
from app.config import TestConfig
from app.database import reset_db, get_db
from app.utils.auth import hash_password


@pytest.fixture
def app():
    app = create_app(TestConfig)
    reset_db(app)
    yield app


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
    return _create_user(app, "admin", "admin123", ["admin", "organizer"])


@pytest.fixture
def admin_token(client, admin_user):
    return _login(client, "admin", "admin123")


@pytest.fixture
def organizer_a(app):
    return _create_user(app, "organizer_a", "org123", ["organizer"])


@pytest.fixture
def organizer_a_token(client, organizer_a):
    return _login(client, "organizer_a", "org123")


@pytest.fixture
def organizer_b(app):
    return _create_user(app, "organizer_b", "org123", ["organizer"])


@pytest.fixture
def organizer_b_token(client, organizer_b):
    return _login(client, "organizer_b", "org123")


@pytest.fixture
def rider_a(app):
    return _create_user(app, "rider_a", "rider123", ["contestant"])


@pytest.fixture
def rider_a_token(client, rider_a):
    return _login(client, "rider_a", "rider123")


@pytest.fixture
def rider_b(app):
    return _create_user(app, "rider_b", "rider123", ["contestant"])


@pytest.fixture
def rider_b_token(client, rider_b):
    return _login(client, "rider_b", "rider123")


# =============================================
# Race Fixture（通过 API 创建，测试也覆盖了 API）
# =============================================

@pytest.fixture
def race_a(client, organizer_a, organizer_a_token):
    resp = client.post("/api/v1/organizer/races",
                       data=json.dumps({"name": "Race A", "status": "open"}),
                       content_type="application/json",
                       headers={"Authorization": f"Bearer {organizer_a_token}"})
    return json.loads(resp.data)["data"]


@pytest.fixture
def race_b(client, organizer_b, organizer_b_token):
    resp = client.post("/api/v1/organizer/races",
                       data=json.dumps({"name": "Race B", "status": "open"}),
                       content_type="application/json",
                       headers={"Authorization": f"Bearer {organizer_b_token}"})
    return json.loads(resp.data)["data"]
