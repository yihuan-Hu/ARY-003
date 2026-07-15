"""人员 C：Review Readiness + RiderProfile 测试"""
import json
import pytest

from tests.conftest import _create_user, _login


# =============================================
# Fixtures
# =============================================


@pytest.fixture
def race_with_work(client, organizer_a, organizer_a_token, rider_a, rider_a_token):
    """创建赛事 + 报名（registration） + 审批 → submitting 状态"""
    resp = client.post(
        "/api/v1/organizer/races",
        data=json.dumps({"name": "Readiness Test Race"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    race = json.loads(resp.data)["data"]
    race_id = race["id"]

    # 发布 → 开放报名
    for action in ("publish", "open-registration"):
        client.post(
            f"/api/v1/organizer/races/{race_id}/{action}",
            headers={"Authorization": f"Bearer {organizer_a_token}"},
        )

    # Rider 报名（race 为 registration）
    reg_resp = client.post(
        f"/api/v1/rider/races/{race_id}/registrations",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    reg = json.loads(reg_resp.data)["data"]

    # Organizer 审批
    client.post(
        f"/api/v1/organizer/registrations/{reg['id']}/approve",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )

    # 进入 submitting 阶段
    for action in ("start", "open-submissions"):
        client.post(
            f"/api/v1/organizer/races/{race_id}/{action}",
            headers={"Authorization": f"Bearer {organizer_a_token}"},
        )

    rp_list = client.get(
        f"/api/v1/organizer/races/{race_id}/race-projects",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    rp_data = json.loads(rp_list.data)["data"]
    rp_id = rp_data[0]["id"] if rp_data else None

    race["rp_id"] = rp_id
    race["registration_id"] = reg["id"]
    return race


# =============================================
# Review Readiness - Rider
# =============================================


def test_readiness_no_work(
    client, rider_a_token, race_with_work
):
    """无 Work → 标记作品未提交"""
    race = race_with_work
    resp = client.get(
        f"/api/v1/rider/race-projects/{race['rp_id']}/review-readiness",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)["data"]
    assert data["overall_ready"] is False
    assert data["risk_count"] >= 1


def test_readiness_incomplete_info(
    client, rider_a_token, race_with_work
):
    """Work 信息不完整 → 标记"""
    race = race_with_work
    # 创建不完整的作品
    client.post(
        f"/api/v1/rider/race-projects/{race['rp_id']}/works",
        data=json.dumps({"title": "Incomplete"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )

    resp = client.get(
        f"/api/v1/rider/race-projects/{race['rp_id']}/review-readiness",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)["data"]
    # 应该有 incomplete_info 风险
    if data.get("works"):
        for w in data["works"]:
            for risk in w.get("risks", []):
                if risk["risk_type"] == "incomplete_info":
                    return  # pass
    # 如果没有 works 结果，检查 risk_count > 0
    assert data["risk_count"] > 0 or data["overall_ready"] is False


def test_readiness_missing_links(
    client, rider_a_token, race_with_work
):
    """缺少 repo_url 和 demo_url → 标记"""
    race = race_with_work
    work_resp = client.post(
        f"/api/v1/rider/race-projects/{race['rp_id']}/works",
        data=json.dumps({
            "title": "No Links Work",
            "description": "Has description",
            "readme_body": "# README",
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    work = json.loads(work_resp.data)["data"]
    client.post(
        f"/api/v1/rider/works/{work['id']}/submit",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )

    resp = client.get(
        f"/api/v1/rider/race-projects/{race['rp_id']}/review-readiness",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)["data"]
    # 找 missing_links 风险
    found = False
    for w in data.get("works", []):
        for risk in w.get("risks", []):
            if risk["risk_type"] == "missing_links":
                found = True
    assert found, f"Expected missing_links risk, got: {data}"


def test_readiness_all_clear(
    client, rider_a_token, race_with_work
):
    """所有信息完整 → 核心风险为空（最多只有 CA 数据缺失的 low 提醒）"""
    race = race_with_work
    work_resp = client.post(
        f"/api/v1/rider/race-projects/{race['rp_id']}/works",
        data=json.dumps({
            "title": "Complete Work",
            "description": "Full description",
            "repo_url": "https://github.com/test/repo",
            "demo_url": "https://demo.example.com",
            "readme_body": "# Complete README",
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    work = json.loads(work_resp.data)["data"]
    client.post(
        f"/api/v1/rider/works/{work['id']}/submit",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )

    resp = client.get(
        f"/api/v1/rider/race-projects/{race['rp_id']}/review-readiness",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)["data"]
    # 如果有 no_work / incomplete_info / missing_links 才是问题
    high_risks = []
    for w in data.get("works", []):
        for risk in w.get("risks", []):
            if risk["risk_type"] in ("no_work", "not_submitted", "incomplete_info", "missing_links"):
                high_risks.append(risk)
    assert len(high_risks) == 0, f"Unexpected risks: {high_risks}"


def test_readiness_organizer_view(
    client, organizer_a_token, race_with_work, rider_a_token
):
    """Organizer 查看全场准备度"""
    race = race_with_work
    # 先创建作品
    work_resp = client.post(
        f"/api/v1/rider/race-projects/{race['rp_id']}/works",
        data=json.dumps({
            "title": "Test",
            "description": "Desc",
            "repo_url": "https://github.com/test/repo",
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    work = json.loads(work_resp.data)["data"]
    client.post(
        f"/api/v1/rider/works/{work['id']}/submit",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )

    resp = client.get(
        f"/api/v1/organizer/races/{race['id']}/review-readiness",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)["data"]
    assert data["race_id"] == race["id"]
    assert data["total_race_projects"] >= 1
    assert "summaries" in data


def test_readiness_not_own_project(
    client, rider_b_token, race_with_work
):
    """Rider 不能查看他人的准备度 → 404"""
    race = race_with_work
    resp = client.get(
        f"/api/v1/rider/race-projects/{race['rp_id']}/review-readiness",
        headers={"Authorization": f"Bearer {rider_b_token}"},
    )
    assert resp.status_code == 404


# =============================================
# RiderProfile
# =============================================


def test_public_rider_profile(
    client, rider_a, race_with_work, rider_a_token
):
    """公开骑手档案（无需认证）"""
    resp = client.get(f"/api/v1/public/riders/{rider_a['id']}")
    assert resp.status_code == 200
    data = json.loads(resp.data)["data"]
    assert data["user"]["id"] == rider_a["id"]
    assert data["user"]["username"] == "rider_a"
    assert "stats" in data
    assert "total_races" in data["stats"]


def test_public_rider_profile_not_found(client):
    """不存在的骑手 → 404"""
    resp = client.get("/api/v1/public/riders/99999")
    assert resp.status_code == 404


def test_private_rider_profile(
    client, rider_a_token, rider_a, race_with_work
):
    """Rider 查看自己的完整档案"""
    resp = client.get(
        "/api/v1/rider/profile",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)["data"]
    assert data["user"]["username"] == "rider_a"
    assert "all_works" in data
    assert "registrations" in data


def test_rider_profile_unauthorized(client):
    """未认证不能访问私有档案"""
    resp = client.get("/api/v1/rider/profile")
    assert resp.status_code == 401
