"""Checkpoint 1 集成测试"""
import json
import sqlite3
import pytest


# =============================================
# 基础：登录与 Token
# =============================================

def test_login_success(client, rider_a):
    resp = client.post("/api/v1/auth/login",
                       data=json.dumps({"username": "rider_a", "password": "rider123"}),
                       content_type="application/json")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert "token" in data["data"]
    assert data["data"]["user"]["username"] == "rider_a"
    assert "contestant" in data["data"]["user"]["roles"]


def test_login_fail_wrong_password(client, rider_a):
    resp = client.post("/api/v1/auth/login",
                       data=json.dumps({"username": "rider_a", "password": "wrong"}),
                       content_type="application/json")
    assert resp.status_code == 401


def test_unauthorized_access(client):
    resp = client.get("/api/v1/rider/registrations")
    assert resp.status_code == 401


# =============================================
# 报名流程
# =============================================

def test_rider_submit_registration(client, rider_a_token, race_a, rider_a):
    resp = client.post(
        f"/api/v1/rider/races/{race_a['id']}/registrations",
        headers={"Authorization": f"Bearer {rider_a_token}"}
    )
    assert resp.status_code == 201
    data = json.loads(resp.data)
    assert data["data"]["status"] == "submitted"
    assert data["data"]["race_id"] == race_a["id"]
    assert data["data"]["user_id"] == rider_a["id"]


def test_duplicate_registration_rejected(client, rider_a_token, race_a):
    """重复报名应返回冲突"""
    # 第一次
    client.post(
        f"/api/v1/rider/races/{race_a['id']}/registrations",
        headers={"Authorization": f"Bearer {rider_a_token}"}
    )
    # 第二次
    resp = client.post(
        f"/api/v1/rider/races/{race_a['id']}/registrations",
        headers={"Authorization": f"Bearer {rider_a_token}"}
    )
    assert resp.status_code == 409


def test_rider_view_own_registrations(client, rider_a_token, race_a):
    """Rider 查看自己的报名"""
    submit_resp = client.post(
        f"/api/v1/rider/races/{race_a['id']}/registrations",
        headers={"Authorization": f"Bearer {rider_a_token}"}
    )
    reg_id = json.loads(submit_resp.data)["data"]["id"]

    resp = client.get("/api/v1/rider/registrations",
                      headers={"Authorization": f"Bearer {rider_a_token}"})
    assert resp.status_code == 200
    registrations = json.loads(resp.data)["data"]
    assert len(registrations) >= 1
    assert any(r["id"] == reg_id for r in registrations)


# =============================================
# 审核与 RaceProject 自动生成
# =============================================

def test_organizer_approve_creates_raceproject(client, rider_a_token, race_a, organizer_a_token):
    """Organizer approve → 自动生成 RaceProject"""
    # Rider 报名
    submit_resp = client.post(
        f"/api/v1/rider/races/{race_a['id']}/registrations",
        headers={"Authorization": f"Bearer {rider_a_token}"}
    )
    reg = json.loads(submit_resp.data)["data"]

    # Organizer approve
    approve_resp = client.post(
        f"/api/v1/organizer/registrations/{reg['id']}/approve",
        headers={"Authorization": f"Bearer {organizer_a_token}"}
    )
    assert approve_resp.status_code == 200
    result = json.loads(approve_resp.data)["data"]
    assert result["idempotent"] is False
    assert result["race_project"] is not None
    assert result["race_project"]["registration_id"] == reg["id"]
    assert result["race_project"]["aggregate_ingestion_status"] == "not_configured"
    assert result["registration"]["status"] == "approved"


def test_duplicate_approve_is_idempotent(client, rider_a_token, race_a, organizer_a_token):
    """重复 approve 幂等：不生成第二个 RaceProject"""
    # Rider 报名
    submit_resp = client.post(
        f"/api/v1/rider/races/{race_a['id']}/registrations",
        headers={"Authorization": f"Bearer {rider_a_token}"}
    )
    reg = json.loads(submit_resp.data)["data"]

    # 第一次 approve
    r1 = client.post(
        f"/api/v1/organizer/registrations/{reg['id']}/approve",
        headers={"Authorization": f"Bearer {organizer_a_token}"}
    )
    assert r1.status_code == 200
    rp_id_1 = json.loads(r1.data)["data"]["race_project"]["id"]

    # 第二次 approve（重复）
    r2 = client.post(
        f"/api/v1/organizer/registrations/{reg['id']}/approve",
        headers={"Authorization": f"Bearer {organizer_a_token}"}
    )
    assert r2.status_code == 200
    result = json.loads(r2.data)["data"]
    assert result["idempotent"] is True
    assert result["race_project"]["id"] == rp_id_1  # 同一个 RaceProject

    # 数据库验证：只有一个 RaceProject
    from app.database import get_db
    from flask import g
    with client.application.app_context():
        db = get_db()
        count = db.execute(
            "SELECT COUNT(*) as cnt FROM race_projects WHERE registration_id = ?",
            (reg["id"],)
        ).fetchone()
        assert count["cnt"] == 1


def test_reject_does_not_create_raceproject(client, rider_a_token, race_a, organizer_a_token):
    """reject 不应该生成 RaceProject"""
    submit_resp = client.post(
        f"/api/v1/rider/races/{race_a['id']}/registrations",
        headers={"Authorization": f"Bearer {rider_a_token}"}
    )
    reg = json.loads(submit_resp.data)["data"]

    resp = client.post(
        f"/api/v1/organizer/registrations/{reg['id']}/reject",
        headers={"Authorization": f"Bearer {organizer_a_token}"}
    )
    assert resp.status_code == 200
    assert json.loads(resp.data)["data"]["registration"]["status"] == "rejected"

    # 数据库验证：没有 RaceProject
    from app.database import get_db
    from flask import g
    with client.application.app_context():
        db = get_db()
        count = db.execute(
            "SELECT COUNT(*) as cnt FROM race_projects WHERE registration_id = ?",
            (reg["id"],)
        ).fetchone()
        assert count["cnt"] == 0


def test_rider_view_own_raceproject(client, rider_a_token, race_a, organizer_a_token):
    """Rider 查看自动生成的 RaceProject"""
    submit_resp = client.post(
        f"/api/v1/rider/races/{race_a['id']}/registrations",
        headers={"Authorization": f"Bearer {rider_a_token}"}
    )
    reg = json.loads(submit_resp.data)["data"]

    client.post(
        f"/api/v1/organizer/registrations/{reg['id']}/approve",
        headers={"Authorization": f"Bearer {organizer_a_token}"}
    )

    # 获取 registration 详情（含 race_project 信息）
    reg_resp = client.get(
        f"/api/v1/rider/registrations/{reg['id']}",
        headers={"Authorization": f"Bearer {rider_a_token}"}
    )
    assert reg_resp.status_code == 200


# =============================================
# 越权测试
# =============================================

def test_rider_cannot_view_others_registration(client, rider_b_token, race_a, rider_a_token):
    """Rider A 的报名，Rider B 不能查看"""
    # Rider A 报名
    submit_resp = client.post(
        f"/api/v1/rider/races/{race_a['id']}/registrations",
        headers={"Authorization": f"Bearer {rider_a_token}"}
    )
    reg_a_id = json.loads(submit_resp.data)["data"]["id"]

    # Rider B 尝试查看
    resp = client.get(
        f"/api/v1/rider/registrations/{reg_a_id}",
        headers={"Authorization": f"Bearer {rider_b_token}"}
    )
    assert resp.status_code == 403


def test_organizer_cannot_review_other_race(client, rider_a_token, race_a, organizer_b_token, rider_b):
    """Organizer B 不能审核不属于自己的 Race 的报名"""
    # Rider B 报名到 Race A（由 Organizer A 创建）
    # 先让 Rider B 也是 contestant
    submit_resp = client.post(
        f"/api/v1/rider/races/{race_a['id']}/registrations",
        headers={"Authorization": f"Bearer {rider_a_token}"}
    )
    reg_id = json.loads(submit_resp.data)["data"]["id"]

    # Organizer B 尝试 approve（应被拒绝）
    resp = client.post(
        f"/api/v1/organizer/registrations/{reg_id}/approve",
        headers={"Authorization": f"Bearer {organizer_b_token}"}
    )
    assert resp.status_code == 403


def test_rider_cannot_approve(client, rider_a_token, race_a, rider_b_token):
    """Rider 不能调用 organizer 接口"""
    # Rider A 报名
    submit_resp = client.post(
        f"/api/v1/rider/races/{race_a['id']}/registrations",
        headers={"Authorization": f"Bearer {rider_a_token}"}
    )
    reg_id = json.loads(submit_resp.data)["data"]["id"]

    # Rider 尝试 approve（角色不够）
    resp = client.post(
        f"/api/v1/organizer/registrations/{reg_id}/approve",
        headers={"Authorization": f"Bearer {rider_a_token}"}
    )
    assert resp.status_code == 403


def test_public_cannot_access_organizer_routes(client, race_a):
    """未认证用户不能访问 organizer 接口"""
    resp = client.get(f"/api/v1/organizer/races/{race_a['id']}/registrations")
    assert resp.status_code == 401


# =============================================
# 数据库约束验证
# =============================================

def test_db_unique_registration_constraint(app, race_a, rider_a):
    """数据库级 UNIQUE(race_id, user_id) 约束"""
    from app.database import get_db
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO registrations (race_id, user_id, status) VALUES (?, ?, 'submitted')",
            (race_a["id"], rider_a["id"])
        )
        db.commit()

        # 重复插入应触发约束冲突
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO registrations (race_id, user_id, status) VALUES (?, ?, 'submitted')",
                (race_a["id"], rider_a["id"])
            )
            db.commit()
        db.rollback()


def test_db_unique_raceproject_constraint(app, race_a, rider_a, organizer_a_token, rider_a_token, client):
    """数据库级 UNIQUE(registration_id) 约束"""
    # 创建报名
    submit_resp = client.post(
        f"/api/v1/rider/races/{race_a['id']}/registrations",
        headers={"Authorization": f"Bearer {rider_a_token}"}
    )
    reg_id = json.loads(submit_resp.data)["data"]["id"]

    from app.database import get_db
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO race_projects (registration_id) VALUES (?)",
            (reg_id,)
        )
        db.commit()

        # 重复插入应触发 UNIQUE 约束冲突
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO race_projects (registration_id) VALUES (?)",
                (reg_id,)
            )
            db.commit()
        db.rollback()


# =============================================
# RaceProject 不能手动创建
# =============================================

def test_raceproject_not_creatable_by_rider(client, rider_a_token):
    """Rider 不能手动创建 RaceProject（没有对应接口）"""
    resp = client.post("/api/v1/rider/race-projects",
                       headers={"Authorization": f"Bearer {rider_a_token}"})
    # 路由不存在或返回 405/404
    assert resp.status_code in (404, 405)


# =============================================
# 完整集成测试：端到端
# =============================================

def test_full_e2e_flow(client, race_a, organizer_a, organizer_a_token, rider_a, rider_a_token, rider_b, rider_b_token):
    """
    完整链路：
    创建 Organizer 和 Rider
    → Organizer 创建 Race
    → Rider 报名
    → Organizer approve
    → 查询 Registration
    → 查询自动生成的 RaceProject
    → 再次 approve
    → 验证仍然只有一个 RaceProject
    """
    # 1. Organizer 创建 Race（已有 race_a fixture）
    assert race_a["created_by_user_id"] == organizer_a["id"]

    # 2. Rider A 报名
    submit_resp = client.post(
        f"/api/v1/rider/races/{race_a['id']}/registrations",
        headers={"Authorization": f"Bearer {rider_a_token}"}
    )
    assert submit_resp.status_code == 201
    reg = json.loads(submit_resp.data)["data"]
    reg_id = reg["id"]
    assert reg["status"] == "submitted"

    # 3. 查询自己的 Registration
    get_resp = client.get(
        f"/api/v1/rider/registrations/{reg_id}",
        headers={"Authorization": f"Bearer {rider_a_token}"}
    )
    assert get_resp.status_code == 200
    assert json.loads(get_resp.data)["data"]["id"] == reg_id

    # 4. Organizer approve
    approve_resp = client.post(
        f"/api/v1/organizer/registrations/{reg_id}/approve",
        headers={"Authorization": f"Bearer {organizer_a_token}"}
    )
    assert approve_resp.status_code == 200
    result = json.loads(approve_resp.data)["data"]
    rp_id = result["race_project"]["id"]
    assert result["registration"]["status"] == "approved"

    # 5. Organizer 查看 managed race 的 Registrations
    regs_resp = client.get(
        f"/api/v1/organizer/races/{race_a['id']}/registrations",
        headers={"Authorization": f"Bearer {organizer_a_token}"}
    )
    assert regs_resp.status_code == 200
    regs = json.loads(regs_resp.data)["data"]
    assert any(r["id"] == reg_id for r in regs)

    # 6. Organizer 查看 managed race 的 RaceProjects
    rps_resp = client.get(
        f"/api/v1/organizer/races/{race_a['id']}/race-projects",
        headers={"Authorization": f"Bearer {organizer_a_token}"}
    )
    assert rps_resp.status_code == 200
    rps = json.loads(rps_resp.data)["data"]
    assert len(rps) >= 1
    assert any(rp["id"] == rp_id for rp in rps)

    # 7. Rider 查看自己的 RaceProject
    rp_resp = client.get(
        f"/api/v1/rider/race-projects/{rp_id}",
        headers={"Authorization": f"Bearer {rider_a_token}"}
    )
    assert rp_resp.status_code == 200
    rp_data = json.loads(rp_resp.data)["data"]
    assert rp_data["id"] == rp_id
    assert rp_data["aggregate_ingestion_status"] == "not_configured"

    # 8. 再次 approve（幂等）
    approve2_resp = client.post(
        f"/api/v1/organizer/registrations/{reg_id}/approve",
        headers={"Authorization": f"Bearer {organizer_a_token}"}
    )
    assert approve2_resp.status_code == 200
    result2 = json.loads(approve2_resp.data)["data"]
    assert result2["idempotent"] is True
    assert result2["race_project"]["id"] == rp_id  # 同一个

    # 9. 数据库验证只有一个 RaceProject
    from app.database import get_db
    from flask import g
    with client.application.app_context():
        db = get_db()
        cnt = db.execute(
            "SELECT COUNT(*) as c FROM race_projects WHERE registration_id = ?",
            (reg_id,)
        ).fetchone()
        assert cnt["c"] == 1
