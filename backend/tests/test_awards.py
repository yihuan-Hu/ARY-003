"""人员 C：奖项榜单测试"""
import json
import pytest

from tests.conftest import _create_user, _login


# =============================================
# Fixtures
# =============================================


@pytest.fixture
def race_for_awards(client, organizer_a, organizer_a_token, rider_a, rider_a_token):
    """创建赛事 → 报名（registration） → 审批 → 作品（submitting） → judging"""
    # 创建赛事
    resp = client.post(
        "/api/v1/organizer/races",
        data=json.dumps({"name": "Awards Test Race"}),
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

    # 获取 RaceProject
    rp_list = client.get(
        f"/api/v1/organizer/races/{race_id}/race-projects",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    rp_data = json.loads(rp_list.data)["data"]
    rp_id = rp_data[0]["id"] if rp_data else None

    # 创建并提交作品
    work_resp = client.post(
        f"/api/v1/rider/race-projects/{rp_id}/works",
        data=json.dumps({
            "title": "Award Winning Work",
            "description": "Great project",
            "repo_url": "https://github.com/test/award",
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    work = json.loads(work_resp.data)["data"]
    submit_resp = client.post(
        f"/api/v1/rider/works/{work['id']}/submit",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    work = json.loads(submit_resp.data)["data"]

    # 进入 judging
    client.post(
        f"/api/v1/organizer/races/{race_id}/start-judging",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )

    race["rp_id"] = rp_id
    race["work"] = work
    race["registration_id"] = reg["id"]
    return race


# =============================================
# 奖项 CRUD
# =============================================


def test_create_award_success(
    client, organizer_a_token, race_for_awards
):
    """Organizer 成功创建奖项"""
    race = race_for_awards
    resp = client.post(
        f"/api/v1/organizer/races/{race['id']}/awards",
        data=json.dumps({
            "title": "冠军",
            "position": 1,
            "work_id": race["work"]["id"],
            "registration_id": race["registration_id"],
            "description": "First place",
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    assert resp.status_code == 201
    data = json.loads(resp.data)["data"]
    assert data["title"] == "冠军"
    assert data["position"] == 1


def test_create_award_fail_not_owner(
    client, organizer_b_token, race_for_awards
):
    """非赛事创建者不能创建奖项 → 403"""
    race = race_for_awards
    resp = client.post(
        f"/api/v1/organizer/races/{race['id']}/awards",
        data=json.dumps({
            "title": "Hack Award",
            "position": 1,
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_b_token}"},
    )
    assert resp.status_code == 403


def test_list_awards(
    client, organizer_a_token, race_for_awards
):
    """Organizer 查看奖项列表"""
    race = race_for_awards
    # 创建两个奖项
    client.post(
        f"/api/v1/organizer/races/{race['id']}/awards",
        data=json.dumps({"title": "冠军", "position": 1}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    client.post(
        f"/api/v1/organizer/races/{race['id']}/awards",
        data=json.dumps({"title": "亚军", "position": 2}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )

    resp = client.get(
        f"/api/v1/organizer/races/{race['id']}/awards",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)["data"]
    assert len(data) == 2
    assert data[0]["position"] == 1


def test_update_award(
    client, organizer_a_token, race_for_awards
):
    """Organizer 编辑奖项"""
    race = race_for_awards
    create_resp = client.post(
        f"/api/v1/organizer/races/{race['id']}/awards",
        data=json.dumps({"title": "冠军", "position": 1}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    award_id = json.loads(create_resp.data)["data"]["id"]

    resp = client.put(
        f"/api/v1/organizer/awards/{award_id}",
        data=json.dumps({"title": "特等奖", "position": 1}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    assert resp.status_code == 200
    assert json.loads(resp.data)["data"]["title"] == "特等奖"


def test_delete_award(
    client, organizer_a_token, race_for_awards
):
    """Organizer 删除奖项"""
    race = race_for_awards
    create_resp = client.post(
        f"/api/v1/organizer/races/{race['id']}/awards",
        data=json.dumps({"title": "冠军", "position": 1}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    award_id = json.loads(create_resp.data)["data"]["id"]

    resp = client.delete(
        f"/api/v1/organizer/awards/{award_id}",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    assert resp.status_code == 200
    assert json.loads(resp.data)["data"]["deleted"] is True


def test_delete_award_fail_after_race_ended(
    client, organizer_a_token, race_for_awards
):
    """赛事结束后不能删除奖项"""
    race = race_for_awards
    create_resp = client.post(
        f"/api/v1/organizer/races/{race['id']}/awards",
        data=json.dumps({"title": "冠军", "position": 1}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    award_id = json.loads(create_resp.data)["data"]["id"]

    # 结束赛事
    client.post(
        f"/api/v1/organizer/races/{race['id']}/complete",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )

    resp = client.delete(
        f"/api/v1/organizer/awards/{award_id}",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    assert resp.status_code == 422


# =============================================
# 公开榜单
# =============================================


def test_public_leaderboard(
    client, organizer_a_token, race_for_awards
):
    """公开榜单按 position 排列"""
    race = race_for_awards
    # 创建奖项
    client.post(
        f"/api/v1/organizer/races/{race['id']}/awards",
        data=json.dumps({
            "title": "冠军",
            "position": 1,
            "work_id": race["work"]["id"],
            "registration_id": race["registration_id"],
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    client.post(
        f"/api/v1/organizer/races/{race['id']}/awards",
        data=json.dumps({"title": "亚军", "position": 2}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )

    resp = client.get(f"/api/v1/public/races/{race['id']}/leaderboard")
    assert resp.status_code == 200
    data = json.loads(resp.data)["data"]
    assert len(data) == 2
    assert data[0]["position"] == 1
    assert data[0]["award_title"] == "冠军"
    assert "winner_username" in data[0]


def test_public_leaderboard_no_auth_required(client, race_for_awards):
    """榜单无需认证"""
    resp = client.get(f"/api/v1/public/races/{race_for_awards['id']}/leaderboard")
    assert resp.status_code == 200
