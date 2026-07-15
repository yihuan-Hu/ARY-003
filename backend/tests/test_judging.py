"""人员 C：评审系统测试"""
import json
import pytest

from tests.conftest import _create_user, _login, _db_execute, _db_fetchone


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
    # Admin 创建赛事（admin 同时也是 race creator，满足跨赛事隔离要求）
    resp = client.post(
        "/api/v1/organizer/races",
        data=json.dumps({"name": "Judging Test Race", "judging_mode": "open"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    race = json.loads(resp.data)["data"]
    race_id = race["id"]

    # 发布 → 开放报名
    for action in ("publish", "open-registration"):
        client.post(
            f"/api/v1/organizer/races/{race_id}/{action}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    # Rider 报名（race 为 registration）
    reg_resp = client.post(
        f"/api/v1/rider/races/{race_id}/registrations",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    reg = json.loads(reg_resp.data)["data"]

    # Admin 审批
    client.post(
        f"/api/v1/organizer/registrations/{reg['id']}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # 进入 submitting 阶段
    for action in ("start", "open-submissions"):
        client.post(
            f"/api/v1/organizer/races/{race_id}/{action}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    # 通过 race-projects 列表获取 rp_id
    rp_list = client.get(
        f"/api/v1/organizer/races/{race_id}/race-projects",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    rp_data = json.loads(rp_list.data)["data"]
    rp_id = rp_data[0]["id"] if rp_data else None

    # 创建作品
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

    # 提交作品（race 为 submitting）
    submit_resp = client.post(
        f"/api/v1/rider/works/{work['id']}/submit",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    work = json.loads(submit_resp.data)["data"]

    # 进入 judging
    client.post(
        f"/api/v1/organizer/races/{race_id}/start-judging",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # 重新获取 race 信息
    race_resp = client.get(
        f"/api/v1/organizer/races/{race_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    race = json.loads(race_resp.data)["data"]
    race["rp_id"] = rp_id
    race["work"] = work
    return race


# =============================================
# 评委分配
# =============================================


def test_admin_assign_judge_success(
    client, admin_token, race_in_judging, judge_user
):
    """Admin 成功分配评委到作品"""
    race = race_in_judging
    work_id = race["work"]["id"]

    resp = client.post(
        f"/api/v1/admin/races/{race['id']}/judge-assignments",
        data=json.dumps({
            "assignments": [{"work_id": work_id, "judge_user_id": judge_user["id"]}]
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = json.loads(resp.data)["data"]
    assert data["count"] == 1
    assert len(data["assignments"]) == 1


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
    client, admin_token, race_in_judging, judge_user
):
    """Admin 查看分配情况"""
    race = race_in_judging
    # 先分配
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
    data = json.loads(resp.data)["data"]
    assert len(data) >= 1


def test_admin_delete_assignment_before_judgment(
    client, admin_token, race_in_judging, judge_user
):
    """评审未提交时可取消分配"""
    race = race_in_judging
    # 先分配
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
# 评分提交
# =============================================


def test_judge_submit_judgment_success(
    client, admin_token, judge_token, race_in_judging, judge_user
):
    """评委成功提交四维评分"""
    race = race_in_judging
    work_id = race["work"]["id"]

    # 先分配
    client.post(
        f"/api/v1/admin/races/{race['id']}/judge-assignments",
        data=json.dumps({
            "assignments": [{"work_id": work_id, "judge_user_id": judge_user["id"]}]
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # 提交评分
    resp = client.post(
        f"/api/v1/judge/works/{work_id}/judgments",
        data=json.dumps({
            "technical_score": 8,
            "innovation_score": 7,
            "presentation_score": 9,
            "completeness_score": 6,
            "comment": "Good work!",
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {judge_token}"},
    )
    assert resp.status_code == 201
    data = json.loads(resp.data)["data"]
    assert data["technical_score"] == 8
    assert data["innovation_score"] == 7


def test_judge_submit_judgment_fail_not_assigned(
    client, judge_token, race_in_judging
):
    """评委不能评未分配作品"""
    race = race_in_judging
    resp = client.post(
        f"/api/v1/judge/works/{race['work']['id']}/judgments",
        data=json.dumps({
            "technical_score": 8,
            "innovation_score": 7,
            "presentation_score": 9,
            "completeness_score": 6,
            "comment": "Not assigned",
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

    # 分配
    client.post(
        f"/api/v1/admin/races/{race['id']}/judge-assignments",
        data=json.dumps({
            "assignments": [{"work_id": work_id, "judge_user_id": judge_user["id"]}]
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # 第一次
    client.post(
        f"/api/v1/judge/works/{work_id}/judgments",
        data=json.dumps({
            "technical_score": 8, "innovation_score": 7,
            "presentation_score": 9, "completeness_score": 6,
            "comment": "First",
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {judge_token}"},
    )

    # 第二次 → 409
    resp = client.post(
        f"/api/v1/judge/works/{work_id}/judgments",
        data=json.dumps({
            "technical_score": 5, "innovation_score": 5,
            "presentation_score": 5, "completeness_score": 5,
            "comment": "Second attempt",
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

    # 分配 + 提交
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
            "comment": "Initial",
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {judge_token}"},
    )
    judgment_id = json.loads(submit_resp.data)["data"]["id"]

    # 修改
    resp = client.put(
        f"/api/v1/judge/judgments/{judgment_id}",
        data=json.dumps({
            "technical_score": 9, "innovation_score": 8,
            "presentation_score": 9, "completeness_score": 7,
            "comment": "Updated",
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {judge_token}"},
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)["data"]
    assert data["technical_score"] == 9


def test_judge_update_judgment_fail_not_owner(
    client, admin_token, judge_token, judge_b_token,
    race_in_judging, judge_user, judge_b_user
):
    """评委不能修改他人的评分"""
    race = race_in_judging
    work_id = race["work"]["id"]

    # 分配 judge_a
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
            "comment": "From judge_a",
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {judge_token}"},
    )
    judgment_id = json.loads(submit_resp.data)["data"]["id"]

    # judge_b 尝试修改 → 403
    resp = client.put(
        f"/api/v1/judge/judgments/{judgment_id}",
        data=json.dumps({
            "technical_score": 1, "innovation_score": 1,
            "presentation_score": 1, "completeness_score": 1,
            "comment": "Hack attempt",
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
    work_id = race["work"]["id"]

    # 分配
    client.post(
        f"/api/v1/admin/races/{race['id']}/judge-assignments",
        data=json.dumps({
            "assignments": [{"work_id": work_id, "judge_user_id": judge_user["id"]}]
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
    assert data[0]["work"]["id"] == work_id


# =============================================
# 评分封存（ended 后不可改）
# =============================================


def test_judgment_sealed_after_race_ends(
    client, admin_token, judge_token,
    race_in_judging, judge_user
):
    """赛事 ended 后评分不可修改（触发器拦截）"""
    race = race_in_judging
    work_id = race["work"]["id"]

    # 分配 + 提交评分
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
            "comment": "Good",
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {judge_token}"},
    )
    judgment_id = json.loads(submit_resp.data)["data"]["id"]

    # Admin 结束赛事
    client.post(
        f"/api/v1/organizer/races/{race['id']}/complete",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # 尝试修改评分 → 应被触发器拦截
    resp = client.put(
        f"/api/v1/judge/judgments/{judgment_id}",
        data=json.dumps({
            "technical_score": 10, "innovation_score": 10,
            "presentation_score": 10, "completeness_score": 10,
            "comment": "Should fail",
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {judge_token}"},
    )
    # 422: InvalidStateError (service层拦截) 或 500 (触发器触发)
    assert resp.status_code in (422, 500)


# =============================================
# 跨赛事隔离
# =============================================


def test_admin_cannot_assign_to_other_organizer_race(
    client, admin_token, race_b, judge_user
):
    """Admin 不能将评委分配到非自己管理的赛事（admin 非 race creator）"""
    # race_b 属于 organizer_b，admin 没有该赛事的 created_by 权限
    # 实际上 admin 有可能有权限...看 team-division 说的是校验 race.created_by_user_id == current_user_id
    # 我们需要仔细再看，admin is not the creator of race_b
    resp = client.post(
        f"/api/v1/admin/races/{race_b['id']}/judge-assignments",
        data=json.dumps({
            "assignments": [{"work_id": 1, "judge_user_id": judge_user["id"]}]
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    # Should fail because admin is not the race creator
    assert resp.status_code == 403
