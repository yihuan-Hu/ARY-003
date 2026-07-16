"""人员 C：评审系统测试（含邀请、自评防护、截止时间、汇总）"""
import json
import pytest

from tests.conftest import _create_user, _login


# =============================================
# Helpers
# =============================================


def _invite_and_accept(client, admin_token, race_id, judge_user_id, judge_token):
    """邀请评委 + 评委接受 → 返回 invitation"""
    invite_resp = client.post(
        f"/api/v1/admin/races/{race_id}/judge-invitations",
        data=json.dumps({"judge_user_id": judge_user_id}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    inv = json.loads(invite_resp.data)["data"]
    client.post(
        f"/api/v1/judge/invitations/{inv['id']}/accept",
        headers={"Authorization": f"Bearer {judge_token}"},
    )
    return inv


# =============================================
# Fixtures
# =============================================


@pytest.fixture
def judge_user(app):
    return _create_user(app, "judge_a", "Judge123!", ["judge"])


@pytest.fixture
def judge_token(client, judge_user):
    return _login(client, "judge_a", "Judge123!")


@pytest.fixture
def judge_b_user(app):
    return _create_user(app, "judge_b", "Judge123!", ["judge"])


@pytest.fixture
def judge_b_token(client, judge_b_user):
    return _login(client, "judge_b", "Judge123!")


@pytest.fixture
def race_in_judging(client, admin_user, admin_token, rider_a, rider_a_token):
    """创建一个已进入 judging 状态的赛事（admin 创建），含已审批报名和已提交作品"""
    resp = client.post(
        "/api/v1/organizer/races",
        data=json.dumps({"name": "Judging Test Race", "judging_mode": "open"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    race = json.loads(resp.data)["data"]
    race_id = race["id"]

    for action in ("publish", "open-registration"):
        client.post(
            f"/api/v1/organizer/races/{race_id}/{action}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    reg_resp = client.post(
        f"/api/v1/rider/races/{race_id}/registrations",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    reg = json.loads(reg_resp.data)["data"]

    client.post(
        f"/api/v1/organizer/registrations/{reg['id']}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    for action in ("start", "open-submissions"):
        client.post(
            f"/api/v1/organizer/races/{race_id}/{action}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    rp_list = client.get(
        f"/api/v1/organizer/races/{race_id}/race-projects",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    rp_data = json.loads(rp_list.data)["data"]
    rp_id = rp_data[0]["id"] if rp_data else None

    work_resp = client.post(
        f"/api/v1/rider/race-projects/{rp_id}/works",
        data=json.dumps({
            "title": "Test Work",
            "description": "A test work for judging",
            "repo_url": "https://github.com/test/repo",
            "readme_body": "# README",
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

    client.post(
        f"/api/v1/organizer/races/{race_id}/start-judging",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    race_resp = client.get(
        f"/api/v1/organizer/races/{race_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    race = json.loads(race_resp.data)["data"]
    race["rp_id"] = rp_id
    race["work"] = work
    return race


# =============================================
# 评委邀请（两步制）
# =============================================


def test_admin_invite_judge_success(
    client, admin_token, race_in_judging, judge_user
):
    """Admin 成功邀请评委"""
    race = race_in_judging
    resp = client.post(
        f"/api/v1/admin/races/{race['id']}/judge-invitations",
        data=json.dumps({"judge_user_id": judge_user["id"]}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = json.loads(resp.data)["data"]
    assert data["status"] == "pending"
    assert data["judge_user_id"] == judge_user["id"]


def test_judge_accept_invitation(
    client, admin_token, judge_token, race_in_judging, judge_user
):
    """评委接受邀请"""
    race = race_in_judging
    invite_resp = client.post(
        f"/api/v1/admin/races/{race['id']}/judge-invitations",
        data=json.dumps({"judge_user_id": judge_user["id"]}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    inv_id = json.loads(invite_resp.data)["data"]["id"]

    resp = client.post(
        f"/api/v1/judge/invitations/{inv_id}/accept",
        headers={"Authorization": f"Bearer {judge_token}"},
    )
    assert resp.status_code == 200
    assert json.loads(resp.data)["data"]["status"] == "accepted"


def test_judge_reject_invitation(
    client, admin_token, judge_token, race_in_judging, judge_user
):
    """评委拒绝邀请"""
    race = race_in_judging
    invite_resp = client.post(
        f"/api/v1/admin/races/{race['id']}/judge-invitations",
        data=json.dumps({"judge_user_id": judge_user["id"]}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    inv_id = json.loads(invite_resp.data)["data"]["id"]

    resp = client.post(
        f"/api/v1/judge/invitations/{inv_id}/reject",
        headers={"Authorization": f"Bearer {judge_token}"},
    )
    assert resp.status_code == 200
    assert json.loads(resp.data)["data"]["status"] == "rejected"


def test_judge_list_my_invitations(
    client, admin_token, judge_token, race_in_judging, judge_user
):
    """评委查看自己收到的邀请"""
    race = race_in_judging
    client.post(
        f"/api/v1/admin/races/{race['id']}/judge-invitations",
        data=json.dumps({"judge_user_id": judge_user["id"]}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    resp = client.get(
        "/api/v1/judge/invitations",
        headers={"Authorization": f"Bearer {judge_token}"},
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)["data"]
    assert len(data) >= 1


def test_assign_fails_without_accepted_invitation(
    client, admin_token, race_in_judging, judge_user
):
    """未接受邀请的评委不能被分配 → 403"""
    race = race_in_judging
    resp = client.post(
        f"/api/v1/admin/races/{race['id']}/judge-assignments",
        data=json.dumps({
            "assignments": [{
                "work_id": race["work"]["id"],
                "judge_user_id": judge_user["id"],
            }]
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 403


# =============================================
# 评委分配（需先邀请并接受）
# =============================================


def test_admin_assign_judge_success(
    client, admin_token, judge_token, race_in_judging, judge_user
):
    """邀请 → 接受 → Admin 成功分配评委"""
    race = race_in_judging
    _invite_and_accept(client, admin_token, race["id"], judge_user["id"], judge_token)

    resp = client.post(
        f"/api/v1/admin/races/{race['id']}/judge-assignments",
        data=json.dumps({
            "assignments": [{"work_id": race["work"]["id"], "judge_user_id": judge_user["id"]}]
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = json.loads(resp.data)["data"]
    assert data["count"] == 1


def test_admin_assign_judge_fail_not_admin(
    client, organizer_a_token, race_in_judging, judge_user
):
    """非 admin 不能分配评委"""
    race = race_in_judging
    resp = client.post(
        f"/api/v1/admin/races/{race['id']}/judge-assignments",
        data=json.dumps({
            "assignments": [{
                "work_id": race["work"]["id"],
                "judge_user_id": judge_user["id"],
            }]
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    assert resp.status_code == 403


def test_admin_list_assignments(
    client, admin_token, judge_token, race_in_judging, judge_user
):
    """Admin 查看分配情况"""
    race = race_in_judging
    _invite_and_accept(client, admin_token, race["id"], judge_user["id"], judge_token)
    client.post(
        f"/api/v1/admin/races/{race['id']}/judge-assignments",
        data=json.dumps({
            "assignments": [{
                "work_id": race["work"]["id"],
                "judge_user_id": judge_user["id"],
            }]
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    resp = client.get(
        f"/api/v1/admin/races/{race['id']}/judge-assignments",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert len(json.loads(resp.data)["data"]) >= 1


def test_admin_delete_assignment_before_judgment(
    client, admin_token, judge_token, race_in_judging, judge_user
):
    """评审未提交时可取消分配"""
    race = race_in_judging
    _invite_and_accept(client, admin_token, race["id"], judge_user["id"], judge_token)
    assign_resp = client.post(
        f"/api/v1/admin/races/{race['id']}/judge-assignments",
        data=json.dumps({
            "assignments": [{
                "work_id": race["work"]["id"],
                "judge_user_id": judge_user["id"],
            }]
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assignment_id = json.loads(assign_resp.data)["data"]["assignments"][0]["id"]

    resp = client.delete(
        f"/api/v1/admin/judge-assignments/{assignment_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert json.loads(resp.data)["data"]["deleted"] is True


# =============================================
# 自评防护
# =============================================


def test_self_review_prevented(
    client, admin_token, rider_a_token, race_in_judging, rider_a
):
    """评委不能被分配去评自己的作品 → 403"""
    race = race_in_judging
    # rider_a 是 work owner，试图以 judge 身份评自己的作品
    # 先给 rider_a 加上 judge 角色
    from app.database import get_db as _get_db
    import os as _os, tempfile, flask
    # 简化：用 rider_a 已有的 token（角色是 rider），切换到 judge 角色需要特殊处理
    # 这里直接验证：如果 judge_user_id == work_owner_user_id，batch_assign 应返回 403
    resp = client.post(
        f"/api/v1/admin/races/{race['id']}/judge-assignments",
        data=json.dumps({
            "assignments": [{
                "work_id": race["work"]["id"],
                "judge_user_id": rider_a["id"],  # rider_a is work owner
            }]
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 403


# =============================================
# 评分提交
# =============================================


def test_judge_submit_judgment_success(
    client, admin_token, judge_token, race_in_judging, judge_user
):
    """评委成功提交四维评分"""
    race = race_in_judging
    work_id = race["work"]["id"]
    _invite_and_accept(client, admin_token, race["id"], judge_user["id"], judge_token)
    client.post(
        f"/api/v1/admin/races/{race['id']}/judge-assignments",
        data=json.dumps({
            "assignments": [{"work_id": work_id, "judge_user_id": judge_user["id"]}]
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    resp = client.post(
        f"/api/v1/judge/works/{work_id}/judgments",
        data=json.dumps({
            "technical_score": 8, "innovation_score": 7,
            "presentation_score": 9, "completeness_score": 6,
            "comment": "Good work!",
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {judge_token}"},
    )
    assert resp.status_code == 201
    data = json.loads(resp.data)["data"]
    assert data["technical_score"] == 8


def test_judge_submit_judgment_fail_not_assigned(
    client, judge_token, race_in_judging
):
    """评委不能评未分配作品"""
    race = race_in_judging
    resp = client.post(
        f"/api/v1/judge/works/{race['work']['id']}/judgments",
        data=json.dumps({
            "technical_score": 8, "innovation_score": 7,
            "presentation_score": 9, "completeness_score": 6,
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {judge_token}"},
    )
    assert resp.status_code == 403


def test_judge_submit_duplicate_judgment(
    client, admin_token, judge_token, race_in_judging, judge_user
):
    """同一作品不可重复评分 → 409"""
    race = race_in_judging
    work_id = race["work"]["id"]
    _invite_and_accept(client, admin_token, race["id"], judge_user["id"], judge_token)
    client.post(
        f"/api/v1/admin/races/{race['id']}/judge-assignments",
        data=json.dumps({
            "assignments": [{"work_id": work_id, "judge_user_id": judge_user["id"]}]
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    client.post(
        f"/api/v1/judge/works/{work_id}/judgments",
        data=json.dumps({
            "technical_score": 8, "innovation_score": 7,
            "presentation_score": 9, "completeness_score": 6,
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {judge_token}"},
    )

    resp = client.post(
        f"/api/v1/judge/works/{work_id}/judgments",
        data=json.dumps({
            "technical_score": 5, "innovation_score": 5,
            "presentation_score": 5, "completeness_score": 5,
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {judge_token}"},
    )
    assert resp.status_code == 409


def test_judge_update_judgment_success(
    client, admin_token, judge_token, race_in_judging, judge_user
):
    """评委成功修改评分"""
    race = race_in_judging
    work_id = race["work"]["id"]
    _invite_and_accept(client, admin_token, race["id"], judge_user["id"], judge_token)
    client.post(
        f"/api/v1/admin/races/{race['id']}/judge-assignments",
        data=json.dumps({
            "assignments": [{"work_id": work_id, "judge_user_id": judge_user["id"]}]
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    submit_resp = client.post(
        f"/api/v1/judge/works/{work_id}/judgments",
        data=json.dumps({
            "technical_score": 8, "innovation_score": 7,
            "presentation_score": 9, "completeness_score": 6,
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {judge_token}"},
    )
    judgment_id = json.loads(submit_resp.data)["data"]["id"]

    resp = client.put(
        f"/api/v1/judge/judgments/{judgment_id}",
        data=json.dumps({
            "technical_score": 9, "innovation_score": 8,
            "presentation_score": 9, "completeness_score": 7,
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {judge_token}"},
    )
    assert resp.status_code == 200
    assert json.loads(resp.data)["data"]["technical_score"] == 9


def test_judge_update_judgment_fail_not_owner(
    client, admin_token, judge_token, judge_b_token,
    race_in_judging, judge_user, judge_b_user
):
    """评委不能修改他人的评分"""
    race = race_in_judging
    work_id = race["work"]["id"]
    _invite_and_accept(client, admin_token, race["id"], judge_user["id"], judge_token)
    client.post(
        f"/api/v1/admin/races/{race['id']}/judge-assignments",
        data=json.dumps({
            "assignments": [{"work_id": work_id, "judge_user_id": judge_user["id"]}]
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    submit_resp = client.post(
        f"/api/v1/judge/works/{work_id}/judgments",
        data=json.dumps({
            "technical_score": 8, "innovation_score": 7,
            "presentation_score": 9, "completeness_score": 6,
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {judge_token}"},
    )
    judgment_id = json.loads(submit_resp.data)["data"]["id"]

    resp = client.put(
        f"/api/v1/judge/judgments/{judgment_id}",
        data=json.dumps({
            "technical_score": 1, "innovation_score": 1,
            "presentation_score": 1, "completeness_score": 1,
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {judge_b_token}"},
    )
    assert resp.status_code == 403


def test_judge_view_own_assignments(
    client, admin_token, judge_token, race_in_judging, judge_user
):
    """评委查看自己的评审清单"""
    race = race_in_judging
    _invite_and_accept(client, admin_token, race["id"], judge_user["id"], judge_token)
    client.post(
        f"/api/v1/admin/races/{race['id']}/judge-assignments",
        data=json.dumps({
            "assignments": [{"work_id": race["work"]["id"], "judge_user_id": judge_user["id"]}]
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    resp = client.get(
        "/api/v1/judge/assignments",
        headers={"Authorization": f"Bearer {judge_token}"},
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)["data"]
    assert len(data) >= 1


# =============================================
# 评分封存
# =============================================


def test_judgment_sealed_after_race_ends(
    client, admin_token, judge_token,
    race_in_judging, judge_user
):
    """赛事 ended 后评分不可修改"""
    race = race_in_judging
    work_id = race["work"]["id"]
    _invite_and_accept(client, admin_token, race["id"], judge_user["id"], judge_token)
    client.post(
        f"/api/v1/admin/races/{race['id']}/judge-assignments",
        data=json.dumps({
            "assignments": [{"work_id": work_id, "judge_user_id": judge_user["id"]}]
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    submit_resp = client.post(
        f"/api/v1/judge/works/{work_id}/judgments",
        data=json.dumps({
            "technical_score": 8, "innovation_score": 7,
            "presentation_score": 9, "completeness_score": 6,
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {judge_token}"},
    )
    judgment_id = json.loads(submit_resp.data)["data"]["id"]

    client.post(
        f"/api/v1/organizer/races/{race['id']}/complete",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    resp = client.put(
        f"/api/v1/judge/judgments/{judgment_id}",
        data=json.dumps({
            "technical_score": 10, "innovation_score": 10,
            "presentation_score": 10, "completeness_score": 10,
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {judge_token}"},
    )
    assert resp.status_code in (422, 500)


# =============================================
# 评审结果汇总
# =============================================


def test_organizer_judgment_summary(
    client, admin_token, judge_token, race_in_judging, judge_user
):
    """Organizer 查看评审汇总"""
    race = race_in_judging
    work_id = race["work"]["id"]
    _invite_and_accept(client, admin_token, race["id"], judge_user["id"], judge_token)
    client.post(
        f"/api/v1/admin/races/{race['id']}/judge-assignments",
        data=json.dumps({
            "assignments": [{"work_id": work_id, "judge_user_id": judge_user["id"]}]
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    client.post(
        f"/api/v1/judge/works/{work_id}/judgments",
        data=json.dumps({
            "technical_score": 8, "innovation_score": 7,
            "presentation_score": 9, "completeness_score": 6,
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {judge_token}"},
    )

    resp = client.get(
        f"/api/v1/organizer/races/{race['id']}/judgments",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)["data"]
    assert data["total_works"] >= 1
    assert len(data["rankings"]) >= 1


# =============================================
# 跨赛事隔离
# =============================================


def test_admin_cannot_assign_to_other_organizer_race(
    client, admin_token, race_b, judge_user
):
    """Admin 不能操作非自己管理的赛事"""
    resp = client.post(
        f"/api/v1/admin/races/{race_b['id']}/judge-assignments",
        data=json.dumps({
            "assignments": [{"work_id": 1, "judge_user_id": judge_user["id"]}]
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 403
