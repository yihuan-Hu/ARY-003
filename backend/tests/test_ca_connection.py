"""
人员 D 测试：CA Connection 全链路（登记 + 握手 + 双模式）
"""
import json
import pytest

from tests.conftest import _create_user, _login, _db_execute, _db_fetchone


def _get_json(response):
    return json.loads(response.data)


def _create_race_and_project(client, organizer_token, rider_token, rider_id,
                             ca_policy="rider_choice", ca_policy_config="{}"):
    """Helper: Organizer 创建赛事并推进到 registration，Rider 报名并审批通过"""
    # Organizer 创建赛事
    resp = client.post("/api/v1/organizer/races",
                       data=json.dumps({
                           "name": "Test CA Race",
                           "ca_policy": ca_policy,
                           "ca_policy_config": ca_policy_config,
                       }),
                       content_type="application/json",
                       headers={"Authorization": f"Bearer {organizer_token}"})
    assert resp.status_code == 201
    race = _get_json(resp)["data"]

    # 发布并开放报名
    for action in ("publish", "open-registration"):
        resp = client.post(
            f"/api/v1/organizer/races/{race['id']}/{action}",
            headers={"Authorization": f"Bearer {organizer_token}"},
        )
        assert resp.status_code == 200

    # Rider 报名
    resp = client.post(
        f"/api/v1/rider/races/{race['id']}/registrations",
        headers={"Authorization": f"Bearer {rider_token}"},
    )
    assert resp.status_code == 201
    reg = _get_json(resp)["data"]

    # Organizer 开始比赛并审批
    client.post(
        f"/api/v1/organizer/races/{race['id']}/start",
        headers={"Authorization": f"Bearer {organizer_token}"},
    )
    resp = client.post(
        f"/api/v1/organizer/registrations/{reg['id']}/approve",
        headers={"Authorization": f"Bearer {organizer_token}"},
    )
    assert resp.status_code == 200

    # 获取 RaceProject ID
    race_project_id = None
    from app.database import get_db
    from flask import current_app
    resp_rp = client.get("/api/v1/rider/registrations",
                         headers={"Authorization": f"Bearer {rider_token}"})
    regs = _get_json(resp_rp)["data"]
    reg_data = regs["items"] if isinstance(regs, dict) else regs

    return {"race": race, "registration": reg, "race_project_id": None}


def _get_race_project_id(app, rider_user_id):
    """通过 DB 直接获取 RaceProject ID"""
    from app.database import get_db
    with app.app_context():
        db = get_db()
        row = db.execute(
            """SELECT rp.id FROM race_projects rp
               JOIN registrations reg ON rp.registration_id = reg.id
               WHERE reg.user_id = ?
               ORDER BY rp.id DESC LIMIT 1""",
            (rider_user_id,),
        ).fetchone()
        return row["id"] if row else None


class TestCAConnection:
    """CA 连接登记 + 双模式"""

    def test_get_ca_policy_rider_choice(self, client, organizer_a, organizer_a_token,
                                         rider_a, rider_a_token, app):
        """rider_choice 模式下查询 CA 策略"""
        ca_policy_config = json.dumps({"allowed_ca_types": ["codex", "claude"],
                                        "config_template": {"repo_url": True, "api_key": True}})
        _create_race_and_project(client, organizer_a_token, rider_a_token,
                                 rider_a["id"], "rider_choice", ca_policy_config)

        rp_id = _get_race_project_id(app, rider_a["id"])
        assert rp_id is not None

        resp = client.get(
            f"/api/v1/rider/race-projects/{rp_id}/ca-policy",
            headers={"Authorization": f"Bearer {rider_a_token}"},
        )
        assert resp.status_code == 200
        data = _get_json(resp)["data"]
        assert data["ca_policy"] == "rider_choice"
        assert "codex" in data["allowed_ca_types"]
        assert "claude" in data["allowed_ca_types"]
        assert "other" in data["allowed_ca_types"]

    def test_get_ca_policy_organizer_specified(self, client, organizer_a, organizer_a_token,
                                                rider_a, rider_a_token, app):
        """organizer_specified 模式下查询 CA 策略"""
        ca_policy_config = json.dumps({
            "allowed_ca_types": ["codex"],
            "config_template": {"repo_url": True, "api_key": True},
        })
        _create_race_and_project(client, organizer_a_token, rider_a_token,
                                 rider_a["id"], "organizer_specified", ca_policy_config)

        rp_id = _get_race_project_id(app, rider_a["id"])
        assert rp_id is not None

        resp = client.get(
            f"/api/v1/rider/race-projects/{rp_id}/ca-policy",
            headers={"Authorization": f"Bearer {rider_a_token}"},
        )
        assert resp.status_code == 200
        data = _get_json(resp)["data"]
        assert data["ca_policy"] == "organizer_specified"
        assert data["allowed_ca_types"] == ["codex"]
        assert data["config_template"] == {"repo_url": True, "api_key": True}

    def test_create_ca_connection(self, client, organizer_a, organizer_a_token,
                                   rider_a, rider_a_token, app):
        """登记 CA 连接"""
        _create_race_and_project(client, organizer_a_token, rider_a_token,
                                 rider_a["id"])

        rp_id = _get_race_project_id(app, rider_a["id"])
        assert rp_id is not None

        resp = client.post(
            f"/api/v1/rider/race-projects/{rp_id}/ca-connections",
            data=json.dumps({
                "ca_type": "codex",
                "provider_name": "test-codex",
                "api_key": "test-api-key-123",
                "config_json": {"repo_url": "https://github.com/test/repo"},
            }),
            content_type="application/json",
            headers={"Authorization": f"Bearer {rider_a_token}"},
        )
        assert resp.status_code == 201
        data = _get_json(resp)["data"]
        assert data["ca_type"] == "codex"
        assert data["provider_name"] == "test-codex"
        assert data["connection_status"] == "pending"
        assert "api_key_hash" not in data

    def test_create_duplicate_ca_connection(self, client, organizer_a, organizer_a_token,
                                              rider_a, rider_a_token, app):
        """重复登记同一 provider 的 CA 连接 → 409"""
        _create_race_and_project(client, organizer_a_token, rider_a_token,
                                 rider_a["id"])

        rp_id = _get_race_project_id(app, rider_a["id"])
        assert rp_id is not None

        body = {
            "ca_type": "claude",
            "provider_name": "test-claude",
            "api_key": "claude-api-key",
        }
        resp = client.post(
            f"/api/v1/rider/race-projects/{rp_id}/ca-connections",
            data=json.dumps(body),
            content_type="application/json",
            headers={"Authorization": f"Bearer {rider_a_token}"},
        )
        assert resp.status_code == 201

        resp = client.post(
            f"/api/v1/rider/race-projects/{rp_id}/ca-connections",
            data=json.dumps(body),
            content_type="application/json",
            headers={"Authorization": f"Bearer {rider_a_token}"},
        )
        assert resp.status_code == 409

    def test_list_ca_connections(self, client, organizer_a, organizer_a_token,
                                  rider_a, rider_a_token, app):
        """查看 CA 连接列表"""
        _create_race_and_project(client, organizer_a_token, rider_a_token,
                                 rider_a["id"])

        rp_id = _get_race_project_id(app, rider_a["id"])
        # 创建两个连接
        for i, ca_type in enumerate(["codex", "claude"]):
            resp = client.post(
                f"/api/v1/rider/race-projects/{rp_id}/ca-connections",
                data=json.dumps({
                    "ca_type": ca_type,
                    "provider_name": f"test-{ca_type}-{i}",
                    "api_key": f"key-{i}",
                }),
                content_type="application/json",
                headers={"Authorization": f"Bearer {rider_a_token}"},
            )
            assert resp.status_code == 201

        resp = client.get(
            f"/api/v1/rider/race-projects/{rp_id}/ca-connections",
            headers={"Authorization": f"Bearer {rider_a_token}"},
        )
        assert resp.status_code == 200
        items = _get_json(resp)["data"]
        assert len(items) >= 2


class TestCAHandshake:
    """CA 握手验证"""

    def test_handshake_success(self, client, organizer_a, organizer_a_token,
                                rider_a, rider_a_token, app):
        """CA 握手成功（有 API Key）"""
        _create_race_and_project(client, organizer_a_token, rider_a_token,
                                 rider_a["id"])

        rp_id = _get_race_project_id(app, rider_a["id"])
        # 创建连接
        resp = client.post(
            f"/api/v1/rider/race-projects/{rp_id}/ca-connections",
            data=json.dumps({
                "ca_type": "codex",
                "provider_name": "handshake-test",
                "api_key": "valid-api-key",
            }),
            content_type="application/json",
            headers={"Authorization": f"Bearer {rider_a_token}"},
        )
        assert resp.status_code == 201
        conn_id = _get_json(resp)["data"]["id"]

        resp = client.post(
            f"/api/v1/ca-connections/{conn_id}/handshake",
            headers={"Authorization": f"Bearer {rider_a_token}"},
        )
        assert resp.status_code == 200
        data = _get_json(resp)["data"]
        assert data["connection_status"] == "connected"
        assert data["handshake_at"] is not None
        assert data["error_message"] == ""

    def test_handshake_fail_no_api_key(self, client, organizer_a, organizer_a_token,
                                         rider_a, rider_a_token, app):
        """CA 握手失败：未配置 API Key"""
        _create_race_and_project(client, organizer_a_token, rider_a_token,
                                 rider_a["id"])

        rp_id = _get_race_project_id(app, rider_a["id"])
        resp = client.post(
            f"/api/v1/rider/race-projects/{rp_id}/ca-connections",
            data=json.dumps({
                "ca_type": "claude",
                "provider_name": "no-key-test",
            }),
            content_type="application/json",
            headers={"Authorization": f"Bearer {rider_a_token}"},
        )
        assert resp.status_code == 201
        conn_id = _get_json(resp)["data"]["id"]

        resp = client.post(
            f"/api/v1/ca-connections/{conn_id}/handshake",
            headers={"Authorization": f"Bearer {rider_a_token}"},
        )
        assert resp.status_code == 422

    def test_update_ca_connection(self, client, organizer_a, organizer_a_token,
                                   rider_a, rider_a_token, app):
        """更新 CA 连接配置"""
        _create_race_and_project(client, organizer_a_token, rider_a_token,
                                 rider_a["id"])

        rp_id = _get_race_project_id(app, rider_a["id"])
        resp = client.post(
            f"/api/v1/rider/race-projects/{rp_id}/ca-connections",
            data=json.dumps({
                "ca_type": "codex",
                "provider_name": "update-test",
                "api_key": "old-key",
            }),
            content_type="application/json",
            headers={"Authorization": f"Bearer {rider_a_token}"},
        )
        assert resp.status_code == 201
        conn_id = _get_json(resp)["data"]["id"]

        resp = client.put(
            f"/api/v1/rider/ca-connections/{conn_id}",
            data=json.dumps({"api_key": "new-key"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {rider_a_token}"},
        )
        assert resp.status_code == 200

    def test_delete_ca_connection(self, client, organizer_a, organizer_a_token,
                                   rider_a, rider_a_token, app):
        """删除 CA 连接"""
        _create_race_and_project(client, organizer_a_token, rider_a_token,
                                 rider_a["id"])

        rp_id = _get_race_project_id(app, rider_a["id"])
        resp = client.post(
            f"/api/v1/rider/race-projects/{rp_id}/ca-connections",
            data=json.dumps({
                "ca_type": "other",
                "provider_name": "delete-test",
                "api_key": "some-key",
            }),
            content_type="application/json",
            headers={"Authorization": f"Bearer {rider_a_token}"},
        )
        assert resp.status_code == 201
        conn_id = _get_json(resp)["data"]["id"]

        resp = client.delete(
            f"/api/v1/rider/ca-connections/{conn_id}",
            headers={"Authorization": f"Bearer {rider_a_token}"},
        )
        assert resp.status_code == 200


class TestCAWizard:
    """CA 接入向导"""

    def test_get_wizard_rider_choice(self, client, organizer_a, organizer_a_token,
                                       rider_a, rider_a_token, app):
        """rider_choice 模式下的向导"""
        _create_race_and_project(client, organizer_a_token, rider_a_token,
                                 rider_a["id"], "rider_choice")
        rp_id = _get_race_project_id(app, rider_a["id"])
        resp = client.get(
            f"/api/v1/rider/race-projects/{rp_id}/ca-wizard",
            headers={"Authorization": f"Bearer {rider_a_token}"},
        )
        assert resp.status_code == 200
        data = _get_json(resp)["data"]
        assert data["ca_policy"]["mode"] == "rider_choice"
        assert data["current_step"] == 1

    def test_submit_wizard_step(self, client, organizer_a, organizer_a_token,
                                  rider_a, rider_a_token, app):
        """提交向导步骤"""
        _create_race_and_project(client, organizer_a_token, rider_a_token,
                                 rider_a["id"])
        rp_id = _get_race_project_id(app, rider_a["id"])

        # Step 1: 选择 CA 类型
        resp = client.post(
            f"/api/v1/rider/race-projects/{rp_id}/ca-wizard/step/1",
            data=json.dumps({"ca_type": "codex"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {rider_a_token}"},
        )
        assert resp.status_code == 200
        data = _get_json(resp)["data"]
        assert data["ca_type"] == "codex"

        # Step 2: 填写配置并提交
        resp = client.post(
            f"/api/v1/rider/race-projects/{rp_id}/ca-wizard/step/2",
            data=json.dumps({
                "ca_type": "codex",
                "provider_name": "wizard-codex",
                "api_key": "wizard-key",
                "config_json": {"repo_url": "https://github.com/test/repo"},
            }),
            content_type="application/json",
            headers={"Authorization": f"Bearer {rider_a_token}"},
        )
        assert resp.status_code == 200
        data = _get_json(resp)["data"]
        assert data["connection_status"] == "pending"

        # Step 4: 握手
        resp = client.post(
            f"/api/v1/rider/race-projects/{rp_id}/ca-wizard/step/4",
            content_type="application/json",
            headers={"Authorization": f"Bearer {rider_a_token}"},
        )
        assert resp.status_code == 200
        data = _get_json(resp)["data"]
        assert data["connection_status"] == "connected"


class TestCrossTenantIsolation:
    """跨租户隔离"""

    def test_rider_b_cannot_view_rider_a_ca(self, client, organizer_a, organizer_a_token,
                                               rider_a, rider_a_token, rider_b, rider_b_token, app):
        """Rider B 不能访问 Rider A 的 CA 连接"""
        # 创建 Rider A 的 race 和 ca connection
        _create_race_and_project(client, organizer_a_token, rider_a_token,
                                 rider_a["id"])
        rp_id_a = _get_race_project_id(app, rider_a["id"])
        resp = client.post(
            f"/api/v1/rider/race-projects/{rp_id_a}/ca-connections",
            data=json.dumps({
                "ca_type": "codex",
                "provider_name": "isolation-test",
                "api_key": "secret-key",
            }),
            content_type="application/json",
            headers={"Authorization": f"Bearer {rider_a_token}"},
        )
        assert resp.status_code == 201
        conn_id = _get_json(resp)["data"]["id"]

        # Rider B 尝试查看 → 404
        resp = client.get(
            f"/api/v1/rider/ca-connections/{conn_id}",
            headers={"Authorization": f"Bearer {rider_b_token}"},
        )
        assert resp.status_code == 404
