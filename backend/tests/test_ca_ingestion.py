"""
人员 D 测试：CA Session Ingestion + Live Hall + Timeline
"""
import json
import pytest

from tests.conftest import _create_user, _login


def _get_json(response):
    return json.loads(response.data)


def _setup_ca_connection(client, organizer_token, rider_token, app):
    """创建完整的 CA 连接链路：赛事 → 报名 → 审批 → CA 连接 → 握手"""
    # Organizer 创建赛事
    resp = client.post("/api/v1/organizer/races",
                       data=json.dumps({"name": "Ingestion Test Race"}),
                       content_type="application/json",
                       headers={"Authorization": f"Bearer {organizer_token}"})
    assert resp.status_code == 201
    race = _get_json(resp)["data"]
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

    # Organizer 批准
    client.post(
        f"/api/v1/organizer/races/{race['id']}/start",
        headers={"Authorization": f"Bearer {organizer_token}"},
    )
    client.post(
        f"/api/v1/organizer/registrations/{reg['id']}/approve",
        headers={"Authorization": f"Bearer {organizer_token}"},
    )

    # 获取 RaceProject ID
    from app.database import get_db
    with app.app_context():
        db = get_db()
        row = db.execute(
            """SELECT rp.id FROM race_projects rp
               JOIN registrations reg ON rp.registration_id = reg.id
               WHERE reg.race_id = ?
               ORDER BY rp.id DESC LIMIT 1""",
            (race['id'],),
        ).fetchone()
        rp_id = row["id"] if row else None

    # 创建 CA 连接
    resp = client.post(
        f"/api/v1/rider/race-projects/{rp_id}/ca-connections",
        data=json.dumps({
            "ca_type": "codex",
            "provider_name": "ingestion-codex",
            "api_key": "ingestion-api-key",
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {rider_token}"},
    )
    assert resp.status_code == 201
    conn_id = _get_json(resp)["data"]["id"]

    # 握手
    resp = client.post(
        f"/api/v1/ca-connections/{conn_id}/handshake",
        headers={"Authorization": f"Bearer {rider_token}"},
    )
    assert resp.status_code == 200

    return {"race": race, "rp_id": rp_id, "conn_id": conn_id, "reg": reg}


class TestCAIngestion:
    """CA Session 数据接入"""

    def test_ingest_session(self, client, organizer_a, organizer_a_token,
                              rider_a, rider_a_token, app):
        """成功接入 CA Session 数据"""
        ctx = _setup_ca_connection(client, organizer_a_token, rider_a_token, app)
        conn_id = ctx["conn_id"]

        resp = client.post(
            f"/api/v1/ca-connections/{conn_id}/ingest",
            data=json.dumps({
                "overall_progress": 0.5,
                "round_progress": 0.8,
                "cost_tokens": 15000,
                "cost_usd": 0.3,
                "risk_level": "low",
                "obstacle_count": 2,
                "violation_count": 0,
                "current_phase": "DEV",
            }),
            content_type="application/json",
            headers={"X-API-Key": "ingestion-api-key"},
        )
        assert resp.status_code == 201
        data = _get_json(resp)["data"]
        assert data["overall_progress"] == 0.5
        assert data["cost_tokens"] == 15000

        # 验证 connection_status 已升级为 active
        resp = client.get(
            f"/api/v1/rider/ca-connections/{conn_id}",
            headers={"Authorization": f"Bearer {rider_a_token}"},
        )
        assert resp.status_code == 200
        assert _get_json(resp)["data"]["connection_status"] == "active"

    def test_ingest_wrong_api_key(self, client, organizer_a, organizer_a_token,
                                    rider_a, rider_a_token, app):
        """用错误的 API Key ingest → 401"""
        ctx = _setup_ca_connection(client, organizer_a_token, rider_a_token, app)
        conn_id = ctx["conn_id"]

        resp = client.post(
            f"/api/v1/ca-connections/{conn_id}/ingest",
            data=json.dumps({"overall_progress": 0.3}),
            content_type="application/json",
            headers={"X-API-Key": "wrong-api-key"},
        )
        assert resp.status_code == 401

    def test_ingest_no_api_key(self, client, organizer_a, organizer_a_token,
                                 rider_a, rider_a_token, app):
        """无 API Key ingest → 401"""
        ctx = _setup_ca_connection(client, organizer_a_token, rider_a_token, app)
        conn_id = ctx["conn_id"]

        resp = client.post(
            f"/api/v1/ca-connections/{conn_id}/ingest",
            data=json.dumps({"overall_progress": 0.3}),
            content_type="application/json",
        )
        assert resp.status_code == 401

    def test_list_sessions(self, client, organizer_a, organizer_a_token,
                            rider_a, rider_a_token, app):
        """查看 Session 历史"""
        ctx = _setup_ca_connection(client, organizer_a_token, rider_a_token, app)
        conn_id = ctx["conn_id"]

        # 先 ingest 几条记录
        for i in range(3):
            client.post(
                f"/api/v1/ca-connections/{conn_id}/ingest",
                data=json.dumps({
                    "overall_progress": 0.1 * (i + 1),
                    "round_progress": 0.2 * (i + 1),
                    "cost_tokens": 1000 * (i + 1),
                    "cost_usd": 0.02 * (i + 1),
                    "risk_level": "none",
                }),
                content_type="application/json",
                headers={"X-API-Key": "ingestion-api-key"},
            )

        resp = client.get(
            f"/api/v1/rider/ca-connections/{conn_id}/sessions",
            headers={"Authorization": f"Bearer {rider_a_token}"},
        )
        assert resp.status_code == 200
        sessions = _get_json(resp)["data"]
        assert len(sessions) >= 3

    def test_organizer_ca_sessions(self, client, organizer_a, organizer_a_token,
                                     rider_a, rider_a_token, app):
        """Organizer 查看全场 CA Session 摘要"""
        ctx = _setup_ca_connection(client, organizer_a_token, rider_a_token, app)

        # Ingest session
        client.post(
            f"/api/v1/ca-connections/{ctx['conn_id']}/ingest",
            data=json.dumps({"overall_progress": 0.7, "round_progress": 0.9}),
            content_type="application/json",
            headers={"X-API-Key": "ingestion-api-key"},
        )

        resp = client.get(
            f"/api/v1/organizer/races/{ctx['race']['id']}/ca-sessions",
            headers={"Authorization": f"Bearer {organizer_a_token}"},
        )
        assert resp.status_code == 200
        sessions = _get_json(resp)["data"]
        assert len(sessions) >= 1


class TestLiveHall:
    """Live Hall 实时大屏"""

    def test_live_hall_basic(self, client, organizer_a, organizer_a_token,
                               rider_a, rider_a_token, app):
        """Live Hall 基本数据查询"""
        ctx = _setup_ca_connection(client, organizer_a_token, rider_a_token, app)

        # Ingest session
        client.post(
            f"/api/v1/ca-connections/{ctx['conn_id']}/ingest",
            data=json.dumps({
                "overall_progress": 0.65,
                "round_progress": 0.5,
                "risk_level": "low",
            }),
            content_type="application/json",
            headers={"X-API-Key": "ingestion-api-key"},
        )

        resp = client.get(
            f"/api/v1/public/races/{ctx['race']['id']}/live",
        )
        assert resp.status_code == 200
        data = _get_json(resp)["data"]
        assert data["race"]["id"] == ctx["race"]["id"]
        assert data["active_riders"] >= 1
        assert "codex" in data["ca_distribution"]

    def test_live_entries(self, client, organizer_a, organizer_a_token,
                            rider_a, rider_a_token, app):
        """Live Hall 参赛者进度列表"""
        ctx = _setup_ca_connection(client, organizer_a_token, rider_a_token, app)

        client.post(
            f"/api/v1/ca-connections/{ctx['conn_id']}/ingest",
            data=json.dumps({"round_progress": 0.8, "current_phase": "TEST"}),
            content_type="application/json",
            headers={"X-API-Key": "ingestion-api-key"},
        )

        resp = client.get(
            f"/api/v1/public/races/{ctx['race']['id']}/live/entries",
        )
        assert resp.status_code == 200
        entries = _get_json(resp)["data"]
        assert len(entries) >= 1
        assert entries[0]["ca_type"] == "codex"


class TestTimeline:
    """Evidence Timeline"""

    def test_rider_timeline(self, client, organizer_a, organizer_a_token,
                              rider_a, rider_a_token, app):
        """Rider 查看自己的 Timeline"""
        ctx = _setup_ca_connection(client, organizer_a_token, rider_a_token, app)

        # Ingest session 以产生更多事件
        client.post(
            f"/api/v1/ca-connections/{ctx['conn_id']}/ingest",
            data=json.dumps({"overall_progress": 0.3}),
            content_type="application/json",
            headers={"X-API-Key": "ingestion-api-key"},
        )

        resp = client.get(
            f"/api/v1/rider/race-projects/{ctx['rp_id']}/timeline",
            headers={"Authorization": f"Bearer {rider_a_token}"},
        )
        assert resp.status_code == 200
        events = _get_json(resp)["data"]
        assert len(events) >= 3  # registration + ca_connection + ca_session

        event_types = {e["event_type"] for e in events}
        assert "registration.submitted" in event_types
        assert "ca_connection.create" in event_types

    def test_public_timeline(self, client, organizer_a, organizer_a_token,
                               rider_a, rider_a_token, app):
        """公开端 Timeline（只展示可公开摘要事件）"""
        ctx = _setup_ca_connection(client, organizer_a_token, rider_a_token, app)

        resp = client.get(
            f"/api/v1/public/race-projects/{ctx['rp_id']}/timeline",
        )
        assert resp.status_code == 200
        events = _get_json(resp)["data"]
        # 公开端应该有事件但不暴露详细 session 数据
        assert len(events) >= 1

    def test_organizer_timeline(self, client, organizer_a, organizer_a_token,
                                  rider_a, rider_a_token, app):
        """Organizer 查看选手 Timeline"""
        ctx = _setup_ca_connection(client, organizer_a_token, rider_a_token, app)

        resp = client.get(
            f"/api/v1/organizer/races/{ctx['race']['id']}/race-projects/{ctx['rp_id']}/timeline",
            headers={"Authorization": f"Bearer {organizer_a_token}"},
        )
        assert resp.status_code == 200
        events = _get_json(resp)["data"]
        assert len(events) >= 1
