"""人员 C 整改验收测试

覆盖 P0/P1/P2 所有必须测试用例。
"""
import json
import pytest
from tests.conftest import _create_user, _login


# =============================================
# Helpers
# =============================================

def _invite_and_accept_organizer(client, organizer_token, race_id, judge_user_id, judge_token):
    """通过 Organizer 路由邀请评委 + 评委接受"""
    invite_resp = client.post(
        f"/api/v1/organizer/races/{race_id}/judge-invitations",
        data=json.dumps({"judge_user_id": judge_user_id}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_token}"},
    )
    inv = json.loads(invite_resp.data)["data"]
    client.post(
        f"/api/v1/judge-invitations/{inv['id']}/accept",
        headers={"Authorization": f"Bearer {judge_token}"},
    )
    return inv


# =============================================
# P0-1: Organizer 主控评审流程
# =============================================


def test_organizer_invite_judge_success(
    client, organizer_a, organizer_a_token, rider_a, rider_a_token
):
    """Organizer 可以给自己赛事发送评审邀请"""
    # 创建赛事
    resp = client.post(
        "/api/v1/organizer/races",
        data=json.dumps({"name": "Org Judge Test"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    race = json.loads(resp.data)["data"]
    race_id = race["id"]
    for action in ("publish", "open-registration"):
        client.post(
            f"/api/v1/organizer/races/{race_id}/{action}",
            headers={"Authorization": f"Bearer {organizer_a_token}"},
        )

    # Organizer 邀请 rider
    resp = client.post(
        f"/api/v1/organizer/races/{race_id}/judge-invitations",
        data=json.dumps({"judge_user_id": rider_a["id"], "message": "Please judge!"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    assert resp.status_code == 201
    inv = json.loads(resp.data)["data"]
    assert inv["status"] == "pending"
    assert inv["judge_user_id"] == rider_a["id"]


def test_non_owner_cannot_invite_judge(
    client, organizer_a, organizer_a_token, organizer_b, organizer_b_token,
    rider_a
):
    """非赛事创建者访问邀请接口返回 403"""
    # organizer_a 创建赛事
    resp = client.post(
        "/api/v1/organizer/races",
        data=json.dumps({"name": "Cross Org Test"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    race = json.loads(resp.data)["data"]
    race_id = race["id"]
    for action in ("publish", "open-registration"):
        client.post(
            f"/api/v1/organizer/races/{race_id}/{action}",
            headers={"Authorization": f"Bearer {organizer_a_token}"},
        )

    # organizer_b 尝试邀请（非创建者）
    resp = client.post(
        f"/api/v1/organizer/races/{race_id}/judge-invitations",
        data=json.dumps({"judge_user_id": rider_a["id"]}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_b_token}"},
    )
    assert resp.status_code == 403


# =============================================
# P0-2: 受邀用户接受邀请 + 自动追加 judge 角色
# =============================================


def test_rider_accept_invitation_and_gets_judge_role(
    client, app, organizer_a, organizer_a_token, rider_a, rider_a_token
):
    """只有 rider 角色的用户收到邀请后，可以接受邀请并获得 judge 权限"""
    # 创建赛事
    resp = client.post(
        "/api/v1/organizer/races",
        data=json.dumps({"name": "Role Test"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    race = json.loads(resp.data)["data"]
    race_id = race["id"]
    for action in ("publish", "open-registration"):
        client.post(
            f"/api/v1/organizer/races/{race_id}/{action}",
            headers={"Authorization": f"Bearer {organizer_a_token}"},
        )

    # Organizer 邀请 rider
    invite_resp = client.post(
        f"/api/v1/organizer/races/{race_id}/judge-invitations",
        data=json.dumps({"judge_user_id": rider_a["id"]}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    inv = json.loads(invite_resp.data)["data"]

    # Rider 查看自己的邀请（只需登录）
    list_resp = client.get(
        "/api/v1/judge-invitations",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    assert list_resp.status_code == 200
    assert len(json.loads(list_resp.data)["data"]) >= 1

    # Rider 接受邀请（只需登录，不需要 judge 角色）
    accept_resp = client.post(
        f"/api/v1/judge-invitations/{inv['id']}/accept",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    assert accept_resp.status_code == 200
    assert json.loads(accept_resp.data)["data"]["status"] == "accepted"

    # 验证 role 被追加：重新登录获取新 token
    new_token = _login(client, "rider_a", "Rider123!")

    # 用新 token 访问 judge 端点验证有 judge 角色
    resp = client.get(
        "/api/v1/judge/assignments",
        headers={"Authorization": f"Bearer {new_token}"},
    )
    assert resp.status_code == 200  # 不再是 403


def test_assign_unaccepted_invitation_returns_422(
    client, organizer_a, organizer_a_token, rider_a, rider_a_token
):
    """未接受邀请的评委不能被分配 → 422"""
    # 创建赛事 + 作品 + judging
    resp = client.post(
        "/api/v1/organizer/races",
        data=json.dumps({"name": "Unaccepted Test", "judging_mode": "open"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    race = json.loads(resp.data)["data"]
    race_id = race["id"]
    for action in ("publish", "open-registration"):
        client.post(
            f"/api/v1/organizer/races/{race_id}/{action}",
            headers={"Authorization": f"Bearer {organizer_a_token}"},
        )

    # rider 报名
    reg_resp = client.post(
        f"/api/v1/rider/races/{race_id}/registrations",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    reg = json.loads(reg_resp.data)["data"]
    client.post(
        f"/api/v1/organizer/registrations/{reg['id']}/approve",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    for action in ("start", "open-submissions"):
        client.post(
            f"/api/v1/organizer/races/{race_id}/{action}",
            headers={"Authorization": f"Bearer {organizer_a_token}"},
        )

    rp_list = client.get(
        f"/api/v1/organizer/races/{race_id}/race-projects",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    rp_id = json.loads(rp_list.data)["data"][0]["id"]

    work_resp = client.post(
        f"/api/v1/rider/race-projects/{rp_id}/works",
        data=json.dumps({"title": "W", "description": "D", "repo_url": "https://x.com"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    work = json.loads(work_resp.data)["data"]
    client.post(
        f"/api/v1/rider/works/{work['id']}/submit",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    client.post(
        f"/api/v1/organizer/races/{race_id}/start-judging",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )

    # 邀请 rider 但 rider 未接受
    client.post(
        f"/api/v1/organizer/races/{race_id}/judge-invitations",
        data=json.dumps({"judge_user_id": rider_a["id"]}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )

    # 尝试分配（未接受）→ 422
    resp = client.post(
        f"/api/v1/organizer/races/{race_id}/judge-assignments",
        data=json.dumps({"assignments": [{"work_id": work["id"], "judge_user_id": rider_a["id"]}]}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    assert resp.status_code == 422


# =============================================
# P1-5: 自评防护返回 422
# =============================================


def test_self_review_returns_422(
    client, organizer_a, organizer_a_token, rider_a, rider_a_token
):
    """自评分配返回 422 而非 403"""
    resp = client.post(
        "/api/v1/organizer/races",
        data=json.dumps({"name": "Self Review Test", "judging_mode": "open"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    race = json.loads(resp.data)["data"]
    race_id = race["id"]
    for action in ("publish", "open-registration"):
        client.post(
            f"/api/v1/organizer/races/{race_id}/{action}",
            headers={"Authorization": f"Bearer {organizer_a_token}"},
        )

    reg_resp = client.post(
        f"/api/v1/rider/races/{race_id}/registrations",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    reg = json.loads(reg_resp.data)["data"]
    client.post(
        f"/api/v1/organizer/registrations/{reg['id']}/approve",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    for action in ("start", "open-submissions"):
        client.post(
            f"/api/v1/organizer/races/{race_id}/{action}",
            headers={"Authorization": f"Bearer {organizer_a_token}"},
        )

    rp_list = client.get(
        f"/api/v1/organizer/races/{race_id}/race-projects",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    rp_id = json.loads(rp_list.data)["data"][0]["id"]

    work_resp = client.post(
        f"/api/v1/rider/race-projects/{rp_id}/works",
        data=json.dumps({"title": "My Work"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    work = json.loads(work_resp.data)["data"]
    client.post(
        f"/api/v1/rider/works/{work['id']}/submit",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    client.post(
        f"/api/v1/organizer/races/{race_id}/start-judging",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )

    # 然后接受邀请
    invite_resp = client.post(
        f"/api/v1/organizer/races/{race_id}/judge-invitations",
        data=json.dumps({"judge_user_id": rider_a["id"]}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    inv = json.loads(invite_resp.data)["data"]
    new_token = _login(client, "rider_a", "Rider123!")
    client.post(
        f"/api/v1/judge-invitations/{inv['id']}/accept",
        headers={"Authorization": f"Bearer {new_token}"},
    )

    # 尝试分配自己 → 422
    resp = client.post(
        f"/api/v1/organizer/races/{race_id}/judge-assignments",
        data=json.dumps({"assignments": [{"work_id": work["id"], "judge_user_id": rider_a["id"]}]}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    assert resp.status_code == 422


# =============================================
# P1-11: Judge assignments 含 readiness risks
# =============================================


def test_judge_assignment_contains_readiness_risks(
    client, app, organizer_a, organizer_a_token, rider_a, rider_a_token, rider_b, rider_b_token
):
    """评委 assignment 列表附带 readiness risks"""
    resp = client.post(
        "/api/v1/organizer/races",
        data=json.dumps({"name": "Readiness Assign Test", "judging_mode": "open"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    race = json.loads(resp.data)["data"]
    race_id = race["id"]
    for action in ("publish", "open-registration"):
        client.post(
            f"/api/v1/organizer/races/{race_id}/{action}",
            headers={"Authorization": f"Bearer {organizer_a_token}"},
        )

    reg_resp = client.post(
        f"/api/v1/rider/races/{race_id}/registrations",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    reg = json.loads(reg_resp.data)["data"]
    client.post(
        f"/api/v1/organizer/registrations/{reg['id']}/approve",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    for action in ("start", "open-submissions"):
        client.post(
            f"/api/v1/organizer/races/{race_id}/{action}",
            headers={"Authorization": f"Bearer {organizer_a_token}"},
        )

    rp_list = client.get(
        f"/api/v1/organizer/races/{race_id}/race-projects",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    rp_id = json.loads(rp_list.data)["data"][0]["id"]

    # 创建不完整的 work（缺少 readme_body）
    work_resp = client.post(
        f"/api/v1/rider/race-projects/{rp_id}/works",
        data=json.dumps({"title": "Incomplete Work"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    work = json.loads(work_resp.data)["data"]
    client.post(
        f"/api/v1/rider/works/{work['id']}/submit",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    client.post(
        f"/api/v1/organizer/races/{race_id}/start-judging",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )

    # rider_b 作为 judge
    _create_user(app, "judge_rr", "Judge123!", ["judge"])
    judge_tok = _login(client, "judge_rr", "Judge123!")

    # 邀请 + 接受
    invite_resp = client.post(
        f"/api/v1/organizer/races/{race_id}/judge-invitations",
        data=json.dumps({"judge_user_id": rider_b["id"]}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    inv = json.loads(invite_resp.data)["data"]
    client.post(
        f"/api/v1/judge-invitations/{inv['id']}/accept",
        headers={"Authorization": f"Bearer {rider_b_token}"},
    )

    # 分配
    client.post(
        f"/api/v1/organizer/races/{race_id}/judge-assignments",
        data=json.dumps({"assignments": [{"work_id": work["id"], "judge_user_id": rider_b["id"]}]}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )

    # 重新登录 rider_b 获取 judge 角色
    new_token = _login(client, "rider_b", "Rider123!")

    # 查看 assignment 列表
    resp = client.get(
        "/api/v1/judge/assignments",
        headers={"Authorization": f"Bearer {new_token}"},
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)["data"]
    assert len(data) >= 1
    # 检查 readiness_risks 字段存在
    entry = data[0]
    assert "readiness_risks" in entry
    # 因为 work 没有 description/readme_body/repo_url，应有 incomplete_info 或 missing_links 风险
    risk_types = [r.get("risk_type") for r in entry.get("readiness_risks", [])]
    assert any(rt in risk_types for rt in ["incomplete_info", "missing_links", "not_submitted"])


# =============================================
# P0-3: Leaderboard 实时评分排名
# =============================================


def test_leaderboard_shows_rankings_before_awards(
    client, app, organizer_a, organizer_a_token, rider_a, rider_a_token, rider_b, rider_b_token
):
    """未创建奖项时，已有评分作品仍出现在 leaderboard 中"""
    resp = client.post(
        "/api/v1/organizer/races",
        data=json.dumps({"name": "LB No Award", "judging_mode": "open", "judging_tiebreaker": "avg"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    race = json.loads(resp.data)["data"]
    race_id = race["id"]
    for action in ("publish", "open-registration"):
        client.post(
            f"/api/v1/organizer/races/{race_id}/{action}",
            headers={"Authorization": f"Bearer {organizer_a_token}"},
        )

    reg_resp = client.post(
        f"/api/v1/rider/races/{race_id}/registrations",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    reg = json.loads(reg_resp.data)["data"]
    client.post(
        f"/api/v1/organizer/registrations/{reg['id']}/approve",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    for action in ("start", "open-submissions"):
        client.post(
            f"/api/v1/organizer/races/{race_id}/{action}",
            headers={"Authorization": f"Bearer {organizer_a_token}"},
        )

    rp_list = client.get(
        f"/api/v1/organizer/races/{race_id}/race-projects",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    rp_id = json.loads(rp_list.data)["data"][0]["id"]

    work_resp = client.post(
        f"/api/v1/rider/race-projects/{rp_id}/works",
        data=json.dumps({"title": "Leaderboard Work", "description": "D", "repo_url": "https://x.com"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    work = json.loads(work_resp.data)["data"]
    client.post(
        f"/api/v1/rider/works/{work['id']}/submit",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    client.post(
        f"/api/v1/organizer/races/{race_id}/start-judging",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )

    # 邀请 rider_b 作为 judge 并分配
    invite_resp = client.post(
        f"/api/v1/organizer/races/{race_id}/judge-invitations",
        data=json.dumps({"judge_user_id": rider_b["id"]}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    inv = json.loads(invite_resp.data)["data"]
    client.post(
        f"/api/v1/judge-invitations/{inv['id']}/accept",
        headers={"Authorization": f"Bearer {rider_b_token}"},
    )
    new_token = _login(client, "rider_b", "Rider123!")
    client.post(
        f"/api/v1/organizer/races/{race_id}/judge-assignments",
        data=json.dumps({"assignments": [{"work_id": work["id"], "judge_user_id": rider_b["id"]}]}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    # 提交评分
    client.post(
        f"/api/v1/judge/works/{work['id']}/judgments",
        data=json.dumps({"technical_score": 8, "innovation_score": 7, "presentation_score": 9, "completeness_score": 6}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {new_token}"},
    )

    # 公开榜单：未创建奖项时也应有 rankings
    resp = client.get(f"/api/v1/public/races/{race_id}/leaderboard")
    assert resp.status_code == 200
    lb = json.loads(resp.data)["data"]
    assert "rankings" in lb
    assert len(lb["rankings"]) >= 1
    assert lb["rankings"][0]["award_title"] is None  # 无奖项


def test_leaderboard_award_does_not_change_rank(
    client, app, organizer_a, organizer_a_token, rider_a, rider_a_token, rider_b, rider_b_token
):
    """创建奖项后，排名不变，只补充 award_title"""
    resp = client.post(
        "/api/v1/organizer/races",
        data=json.dumps({"name": "LB Award Test", "judging_mode": "open", "judging_tiebreaker": "avg"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    race = json.loads(resp.data)["data"]
    race_id = race["id"]
    for action in ("publish", "open-registration"):
        client.post(
            f"/api/v1/organizer/races/{race_id}/{action}",
            headers={"Authorization": f"Bearer {organizer_a_token}"},
        )

    reg_resp = client.post(
        f"/api/v1/rider/races/{race_id}/registrations",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    reg = json.loads(reg_resp.data)["data"]
    client.post(
        f"/api/v1/organizer/registrations/{reg['id']}/approve",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    for action in ("start", "open-submissions"):
        client.post(
            f"/api/v1/organizer/races/{race_id}/{action}",
            headers={"Authorization": f"Bearer {organizer_a_token}"},
        )

    rp_list = client.get(
        f"/api/v1/organizer/races/{race_id}/race-projects",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    rp_id = json.loads(rp_list.data)["data"][0]["id"]

    work_resp = client.post(
        f"/api/v1/rider/race-projects/{rp_id}/works",
        data=json.dumps({"title": "Award Work", "description": "D", "repo_url": "https://x.com"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    work = json.loads(work_resp.data)["data"]
    client.post(
        f"/api/v1/rider/works/{work['id']}/submit",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    client.post(
        f"/api/v1/organizer/races/{race_id}/start-judging",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )

    # judge
    invite_resp = client.post(
        f"/api/v1/organizer/races/{race_id}/judge-invitations",
        data=json.dumps({"judge_user_id": rider_b["id"]}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    inv = json.loads(invite_resp.data)["data"]
    client.post(
        f"/api/v1/judge-invitations/{inv['id']}/accept",
        headers={"Authorization": f"Bearer {rider_b_token}"},
    )
    new_token = _login(client, "rider_b", "Rider123!")
    client.post(
        f"/api/v1/organizer/races/{race_id}/judge-assignments",
        data=json.dumps({"assignments": [{"work_id": work["id"], "judge_user_id": rider_b["id"]}]}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    client.post(
        f"/api/v1/judge/works/{work['id']}/judgments",
        data=json.dumps({"technical_score": 9, "innovation_score": 9, "presentation_score": 9, "completeness_score": 9}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {new_token}"},
    )

    # 先看 leaderboard
    before = client.get(f"/api/v1/public/races/{race_id}/leaderboard")
    before_score = json.loads(before.data)["data"]["rankings"][0]["total_score"]

    # 创建奖项
    client.post(
        f"/api/v1/organizer/races/{race_id}/awards",
        data=json.dumps({"title": "Gold", "position": 1, "work_id": work["id"]}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )

    # 再看 leaderboard
    after = client.get(f"/api/v1/public/races/{race_id}/leaderboard")
    after_data = json.loads(after.data)["data"]
    assert after_data["rankings"][0]["total_score"] == before_score  # 分数不变
    assert after_data["rankings"][0]["award_title"] == "Gold"  # 补充了 award_title


def test_leaderboard_excludes_disqualified_work(
    client, app, organizer_a, organizer_a_token, rider_a, rider_a_token, rider_b, rider_b_token
):
    """disqualified 作品不出现在 rankings，但出现在 disqualified 列表"""
    resp = client.post(
        "/api/v1/organizer/races",
        data=json.dumps({"name": "LB Disq Test", "judging_mode": "open", "judging_tiebreaker": "avg"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    race = json.loads(resp.data)["data"]
    race_id = race["id"]
    for action in ("publish", "open-registration"):
        client.post(
            f"/api/v1/organizer/races/{race_id}/{action}",
            headers={"Authorization": f"Bearer {organizer_a_token}"},
        )

    reg_resp = client.post(
        f"/api/v1/rider/races/{race_id}/registrations",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    reg = json.loads(reg_resp.data)["data"]
    client.post(
        f"/api/v1/organizer/registrations/{reg['id']}/approve",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    for action in ("start", "open-submissions"):
        client.post(
            f"/api/v1/organizer/races/{race_id}/{action}",
            headers={"Authorization": f"Bearer {organizer_a_token}"},
        )

    rp_list = client.get(
        f"/api/v1/organizer/races/{race_id}/race-projects",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    rp_id = json.loads(rp_list.data)["data"][0]["id"]

    work_resp = client.post(
        f"/api/v1/rider/race-projects/{rp_id}/works",
        data=json.dumps({"title": "Disq Work", "description": "D", "repo_url": "https://x.com"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    work = json.loads(work_resp.data)["data"]
    client.post(
        f"/api/v1/rider/works/{work['id']}/submit",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )

    # Disqualify
    client.post(
        f"/api/v1/organizer/works/{work['id']}/disqualify",
        data=json.dumps({"reason": "Violation"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )

    # 榜单
    resp = client.get(f"/api/v1/public/races/{race_id}/leaderboard")
    assert resp.status_code == 200
    lb = json.loads(resp.data)["data"]
    rankings_ids = [r["work_id"] for r in lb["rankings"]]
    assert work["id"] not in rankings_ids
    disq_ids = [d["work_id"] for d in lb["disqualified"]]
    assert work["id"] in disq_ids


def test_leaderboard_median_tiebreaker(
    client, app, organizer_a, organizer_a_token, rider_a, rider_a_token, rider_b, rider_b_token
):
    """median tiebreaker 排行榜"""
    resp = client.post(
        "/api/v1/organizer/races",
        data=json.dumps({"name": "LB Median", "judging_mode": "open", "judging_tiebreaker": "median"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    race = json.loads(resp.data)["data"]
    race_id = race["id"]
    for action in ("publish", "open-registration"):
        client.post(f"/api/v1/organizer/races/{race_id}/{action}", headers={"Authorization": f"Bearer {organizer_a_token}"})

    reg_resp = client.post(f"/api/v1/rider/races/{race_id}/registrations",
                           headers={"Authorization": f"Bearer {rider_a_token}"})
    reg = json.loads(reg_resp.data)["data"]
    client.post(f"/api/v1/organizer/registrations/{reg['id']}/approve",
                headers={"Authorization": f"Bearer {organizer_a_token}"})
    for action in ("start", "open-submissions"):
        client.post(f"/api/v1/organizer/races/{race_id}/{action}", headers={"Authorization": f"Bearer {organizer_a_token}"})

    rp_list = client.get(f"/api/v1/organizer/races/{race_id}/race-projects",
                         headers={"Authorization": f"Bearer {organizer_a_token}"})
    rp_id = json.loads(rp_list.data)["data"][0]["id"]
    work_resp = client.post(
        f"/api/v1/rider/race-projects/{rp_id}/works",
        data=json.dumps({"title": "Median Work", "description": "D", "repo_url": "https://x.com"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    work = json.loads(work_resp.data)["data"]
    client.post(f"/api/v1/rider/works/{work['id']}/submit", headers={"Authorization": f"Bearer {rider_a_token}"})
    client.post(f"/api/v1/organizer/races/{race_id}/start-judging", headers={"Authorization": f"Bearer {organizer_a_token}"})

    # 分配 + 评分
    invite_resp = client.post(
        f"/api/v1/organizer/races/{race_id}/judge-invitations",
        data=json.dumps({"judge_user_id": rider_b["id"]}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    inv = json.loads(invite_resp.data)["data"]
    client.post(f"/api/v1/judge-invitations/{inv['id']}/accept", headers={"Authorization": f"Bearer {rider_b_token}"})
    new_token = _login(client, "rider_b", "Rider123!")
    client.post(
        f"/api/v1/organizer/races/{race_id}/judge-assignments",
        data=json.dumps({"assignments": [{"work_id": work["id"], "judge_user_id": rider_b["id"]}]}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    client.post(
        f"/api/v1/judge/works/{work['id']}/judgments",
        data=json.dumps({"technical_score": 5, "innovation_score": 8, "presentation_score": 9, "completeness_score": 7}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {new_token}"},
    )

    resp = client.get(f"/api/v1/public/races/{race_id}/leaderboard")
    assert resp.status_code == 200
    lb = json.loads(resp.data)["data"]
    assert lb["tiebreaker"] == "median"
    assert len(lb["rankings"]) >= 1


def test_leaderboard_trimmed_mean_tiebreaker(
    client, app, organizer_a, organizer_a_token, rider_a, rider_a_token, rider_b, rider_b_token
):
    """trimmed_mean tiebreaker 排行榜"""
    resp = client.post(
        "/api/v1/organizer/races",
        data=json.dumps({"name": "LB Trimmed", "judging_mode": "open", "judging_tiebreaker": "trimmed_mean"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    race = json.loads(resp.data)["data"]
    race_id = race["id"]
    for action in ("publish", "open-registration"):
        client.post(f"/api/v1/organizer/races/{race_id}/{action}", headers={"Authorization": f"Bearer {organizer_a_token}"})

    reg_resp = client.post(f"/api/v1/rider/races/{race_id}/registrations",
                           headers={"Authorization": f"Bearer {rider_a_token}"})
    reg = json.loads(reg_resp.data)["data"]
    client.post(f"/api/v1/organizer/registrations/{reg['id']}/approve",
                headers={"Authorization": f"Bearer {organizer_a_token}"})
    for action in ("start", "open-submissions"):
        client.post(f"/api/v1/organizer/races/{race_id}/{action}", headers={"Authorization": f"Bearer {organizer_a_token}"})

    rp_list = client.get(f"/api/v1/organizer/races/{race_id}/race-projects",
                         headers={"Authorization": f"Bearer {organizer_a_token}"})
    rp_id = json.loads(rp_list.data)["data"][0]["id"]
    work_resp = client.post(
        f"/api/v1/rider/race-projects/{rp_id}/works",
        data=json.dumps({"title": "Trimmed Work", "description": "D", "repo_url": "https://x.com"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    work = json.loads(work_resp.data)["data"]
    client.post(f"/api/v1/rider/works/{work['id']}/submit", headers={"Authorization": f"Bearer {rider_a_token}"})
    client.post(f"/api/v1/organizer/races/{race_id}/start-judging", headers={"Authorization": f"Bearer {organizer_a_token}"})

    invite_resp = client.post(
        f"/api/v1/organizer/races/{race_id}/judge-invitations",
        data=json.dumps({"judge_user_id": rider_b["id"]}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    inv = json.loads(invite_resp.data)["data"]
    client.post(f"/api/v1/judge-invitations/{inv['id']}/accept", headers={"Authorization": f"Bearer {rider_b_token}"})
    new_token = _login(client, "rider_b", "Rider123!")
    client.post(
        f"/api/v1/organizer/races/{race_id}/judge-assignments",
        data=json.dumps({"assignments": [{"work_id": work["id"], "judge_user_id": rider_b["id"]}]}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    client.post(
        f"/api/v1/judge/works/{work['id']}/judgments",
        data=json.dumps({"technical_score": 6, "innovation_score": 7, "presentation_score": 8, "completeness_score": 9}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {new_token}"},
    )

    resp = client.get(f"/api/v1/public/races/{race_id}/leaderboard")
    assert resp.status_code == 200
    lb = json.loads(resp.data)["data"]
    assert lb["tiebreaker"] == "trimmed_mean"
    assert len(lb["rankings"]) >= 1


# =============================================
# P0-4: Report 模块
# =============================================


def test_report_generate_draft(
    client, organizer_a, organizer_a_token
):
    """Organizer 可生成 draft 报告"""
    resp = client.post(
        "/api/v1/organizer/races",
        data=json.dumps({"name": "Report Test Race"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    race = json.loads(resp.data)["data"]
    race_id = race["id"]

    resp = client.post(
        f"/api/v1/organizer/races/{race_id}/reports/generate",
        data=json.dumps({"report_type": "race_report"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    assert resp.status_code == 201
    report = json.loads(resp.data)["data"]
    assert report["visibility"] == "draft"
    assert report["report_type"] == "race_report"


def test_report_publish_and_public_list(
    client, organizer_a, organizer_a_token
):
    """发布报告后 public 可查看"""
    resp = client.post(
        "/api/v1/organizer/races",
        data=json.dumps({"name": "Pub Report Race"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    race = json.loads(resp.data)["data"]
    race_id = race["id"]
    for action in ("publish",):
        client.post(
            f"/api/v1/organizer/races/{race_id}/{action}",
            headers={"Authorization": f"Bearer {organizer_a_token}"},
        )

    # 生成 draft
    gen_resp = client.post(
        f"/api/v1/organizer/races/{race_id}/reports/generate",
        data=json.dumps({"report_type": "race_report"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    report_id = json.loads(gen_resp.data)["data"]["id"]

    # 发布前 public 不可见
    pub_before = client.get(f"/api/v1/public/races/{race_id}/reports")
    assert pub_before.status_code == 200
    assert len(json.loads(pub_before.data)["data"]) == 0

    # 发布
    client.post(
        f"/api/v1/organizer/reports/{report_id}/publish",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )

    # 发布后 public 可见
    pub_after = client.get(f"/api/v1/public/races/{race_id}/reports")
    assert pub_after.status_code == 200
    assert len(json.loads(pub_after.data)["data"]) >= 1


def test_report_hide_removes_from_public(
    client, organizer_a, organizer_a_token
):
    """隐藏报告后 public 不可见"""
    resp = client.post(
        "/api/v1/organizer/races",
        data=json.dumps({"name": "Hide Report Race"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    race = json.loads(resp.data)["data"]
    race_id = race["id"]
    for action in ("publish",):
        client.post(
            f"/api/v1/organizer/races/{race_id}/{action}",
            headers={"Authorization": f"Bearer {organizer_a_token}"},
        )

    gen_resp = client.post(
        f"/api/v1/organizer/races/{race_id}/reports/generate",
        data=json.dumps({"report_type": "race_report"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    report_id = json.loads(gen_resp.data)["data"]["id"]

    # 发布
    client.post(
        f"/api/v1/organizer/reports/{report_id}/publish",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    assert len(json.loads(client.get(f"/api/v1/public/races/{race_id}/reports").data)["data"]) >= 1

    # 隐藏
    client.post(
        f"/api/v1/organizer/reports/{report_id}/hide",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    assert len(json.loads(client.get(f"/api/v1/public/races/{race_id}/reports").data)["data"]) == 0


def test_rider_can_view_own_published_rider_report(
    client, app, organizer_a, organizer_a_token, rider_a, rider_a_token
):
    """Rider 只能看到自己 registration 的已发布 rider_report"""
    resp = client.post(
        "/api/v1/organizer/races",
        data=json.dumps({"name": "Rider Report Race"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    race = json.loads(resp.data)["data"]
    race_id = race["id"]
    for action in ("publish", "open-registration"):
        client.post(
            f"/api/v1/organizer/races/{race_id}/{action}",
            headers={"Authorization": f"Bearer {organizer_a_token}"},
        )

    reg_resp = client.post(
        f"/api/v1/rider/races/{race_id}/registrations",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    reg = json.loads(reg_resp.data)["data"]

    # Organizer 为 rider 生成 rider_report
    gen_resp = client.post(
        f"/api/v1/organizer/races/{race_id}/reports/generate",
        data=json.dumps({
            "report_type": "rider_report",
            "subject_registration_id": reg["id"],
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    report_id = json.loads(gen_resp.data)["data"]["id"]

    # 发布前 rider 看不到
    resp = client.get(
        f"/api/v1/rider/registrations/{reg['id']}/report",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    assert resp.status_code == 404

    # 发布
    client.post(
        f"/api/v1/organizer/reports/{report_id}/publish",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )

    # 发布后 rider 可查看
    resp = client.get(
        f"/api/v1/rider/registrations/{reg['id']}/report",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    assert resp.status_code == 200


def test_rider_cannot_view_other_rider_report(
    client, app, organizer_a, organizer_a_token, rider_a, rider_a_token, rider_b, rider_b_token
):
    """Rider 不能查看其他 rider 的报告"""
    resp = client.post(
        "/api/v1/organizer/races",
        data=json.dumps({"name": "Cross Rider Report"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    race = json.loads(resp.data)["data"]
    race_id = race["id"]
    for action in ("publish", "open-registration"):
        client.post(
            f"/api/v1/organizer/races/{race_id}/{action}",
            headers={"Authorization": f"Bearer {organizer_a_token}"},
        )

    reg_resp = client.post(
        f"/api/v1/rider/races/{race_id}/registrations",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    reg = json.loads(reg_resp.data)["data"]

    gen_resp = client.post(
        f"/api/v1/organizer/races/{race_id}/reports/generate",
        data=json.dumps({
            "report_type": "rider_report",
            "subject_registration_id": reg["id"],
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    report_id = json.loads(gen_resp.data)["data"]["id"]
    client.post(
        f"/api/v1/organizer/reports/{report_id}/publish",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )

    # rider_b 尝试查看 rider_a 的报告
    resp = client.get(
        f"/api/v1/rider/registrations/{reg['id']}/report",
        headers={"Authorization": f"Bearer {rider_b_token}"},
    )
    assert resp.status_code == 403


# =============================================
# P1/P2: CSV injection, notifications, accounts, disqualify
# =============================================


def test_csv_injection_prefix_for_dangerous_cells(
    client, organizer_a, organizer_a_token
):
    """CSV 注入防护为危险前缀加单引号"""
    # 测试 _sanitize_csv_cell 函数
    from app.routes.organizer import _sanitize_csv_cell
    assert _sanitize_csv_cell("=SUM(A1:A10)") == "'=SUM(A1:A10)"
    assert _sanitize_csv_cell("+malicious") == "'+malicious"
    assert _sanitize_csv_cell("-malicious") == "'-malicious"
    assert _sanitize_csv_cell("@malicious") == "'@malicious"
    assert _sanitize_csv_cell("normal text") == "normal text"
    assert _sanitize_csv_cell(None) == ""


def test_invite_and_assignment_send_notifications(
    client, app, organizer_a, organizer_a_token, rider_a, rider_a_token, rider_b, rider_b_token
):
    """邀请和分配发送通知"""
    resp = client.post(
        "/api/v1/organizer/races",
        data=json.dumps({"name": "Notif Test", "judging_mode": "open"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    race = json.loads(resp.data)["data"]
    race_id = race["id"]
    for action in ("publish", "open-registration"):
        client.post(
            f"/api/v1/organizer/races/{race_id}/{action}",
            headers={"Authorization": f"Bearer {organizer_a_token}"},
        )

    # rider 报名并提交 work
    reg_resp = client.post(
        f"/api/v1/rider/races/{race_id}/registrations",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    reg = json.loads(reg_resp.data)["data"]
    client.post(
        f"/api/v1/organizer/registrations/{reg['id']}/approve",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    for action in ("start", "open-submissions"):
        client.post(
            f"/api/v1/organizer/races/{race_id}/{action}",
            headers={"Authorization": f"Bearer {organizer_a_token}"},
        )
    rp_list = client.get(
        f"/api/v1/organizer/races/{race_id}/race-projects",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    rp_id = json.loads(rp_list.data)["data"][0]["id"]
    work_resp = client.post(
        f"/api/v1/rider/race-projects/{rp_id}/works",
        data=json.dumps({"title": "Notif Work", "description": "D", "repo_url": "https://x.com"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    work = json.loads(work_resp.data)["data"]
    client.post(f"/api/v1/rider/works/{work['id']}/submit", headers={"Authorization": f"Bearer {rider_a_token}"})
    client.post(f"/api/v1/organizer/races/{race_id}/start-judging", headers={"Authorization": f"Bearer {organizer_a_token}"})

    # 邀请 rider_b → 应发送通知给 rider_b
    invite_resp = client.post(
        f"/api/v1/organizer/races/{race_id}/judge-invitations",
        data=json.dumps({"judge_user_id": rider_b["id"]}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    inv = json.loads(invite_resp.data)["data"]
    client.post(
        f"/api/v1/judge-invitations/{inv['id']}/accept",
        headers={"Authorization": f"Bearer {rider_b_token}"},
    )

    # 分配 → 应发送通知给 judge
    new_token = _login(client, "rider_b", "Rider123!")
    assign_resp = client.post(
        f"/api/v1/organizer/races/{race_id}/judge-assignments",
        data=json.dumps({"assignments": [{"work_id": work["id"], "judge_user_id": rider_b["id"]}]}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    assert assign_resp.status_code == 201

    # 验证通知记录存在
    from app.database import get_db as _get_db
    with app.app_context():
        db = _get_db()
        count = db.execute("SELECT COUNT(*) AS cnt FROM notifications").fetchone()["cnt"]
        assert count >= 1, "Expected at least 1 notification"


def test_organizer_accounts_search(
    client, organizer_a, organizer_a_token, rider_a, rider_b
):
    """GET /api/v1/organizer/accounts 搜索评委"""
    # 不带参数
    resp = client.get(
        "/api/v1/organizer/accounts",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)["data"]
    assert "items" in data
    assert len(data["items"]) >= 1

    # 带搜索关键词
    resp = client.get(
        "/api/v1/organizer/accounts?q=rider",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)["data"]
    assert len(data["items"]) >= 1
    item = data["items"][0]
    assert "id" in item
    assert "username" in item


def test_disqualify_and_restore_work(
    client, organizer_a, organizer_a_token, rider_a, rider_a_token
):
    """取消/恢复作品资格"""
    resp = client.post(
        "/api/v1/organizer/races",
        data=json.dumps({"name": "Disq Restore Test"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    race = json.loads(resp.data)["data"]
    race_id = race["id"]
    for action in ("publish", "open-registration"):
        client.post(
            f"/api/v1/organizer/races/{race_id}/{action}",
            headers={"Authorization": f"Bearer {organizer_a_token}"},
        )

    reg_resp = client.post(
        f"/api/v1/rider/races/{race_id}/registrations",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    reg = json.loads(reg_resp.data)["data"]
    client.post(
        f"/api/v1/organizer/registrations/{reg['id']}/approve",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    for action in ("start", "open-submissions"):
        client.post(
            f"/api/v1/organizer/races/{race_id}/{action}",
            headers={"Authorization": f"Bearer {organizer_a_token}"},
        )

    rp_list = client.get(
        f"/api/v1/organizer/races/{race_id}/race-projects",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    rp_id = json.loads(rp_list.data)["data"][0]["id"]

    work_resp = client.post(
        f"/api/v1/rider/race-projects/{rp_id}/works",
        data=json.dumps({"title": "DisqRestore Work", "description": "D", "repo_url": "https://x.com"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    work = json.loads(work_resp.data)["data"]

    # Disqualify
    disq_resp = client.post(
        f"/api/v1/organizer/works/{work['id']}/disqualify",
        data=json.dumps({"reason": "Test violation"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    assert disq_resp.status_code == 200
    assert json.loads(disq_resp.data)["data"]["disqualified"] == 1

    # Restore
    restore_resp = client.post(
        f"/api/v1/organizer/works/{work['id']}/restore",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    assert restore_resp.status_code == 200
    assert json.loads(restore_resp.data)["data"]["disqualified"] == 0


def test_non_owner_cannot_disqualify(
    client, organizer_a, organizer_a_token, organizer_b, organizer_b_token, rider_a, rider_a_token
):
    """非赛事创建者不能取消作品资格"""
    resp = client.post(
        "/api/v1/organizer/races",
        data=json.dumps({"name": "Cross Disq Test"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    race = json.loads(resp.data)["data"]
    race_id = race["id"]
    for action in ("publish", "open-registration"):
        client.post(
            f"/api/v1/organizer/races/{race_id}/{action}",
            headers={"Authorization": f"Bearer {organizer_a_token}"},
        )

    reg_resp = client.post(
        f"/api/v1/rider/races/{race_id}/registrations",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    reg = json.loads(reg_resp.data)["data"]
    client.post(
        f"/api/v1/organizer/registrations/{reg['id']}/approve",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    for action in ("start", "open-submissions"):
        client.post(
            f"/api/v1/organizer/races/{race_id}/{action}",
            headers={"Authorization": f"Bearer {organizer_a_token}"},
        )

    rp_list = client.get(
        f"/api/v1/organizer/races/{race_id}/race-projects",
        headers={"Authorization": f"Bearer {organizer_a_token}"},
    )
    rp_id = json.loads(rp_list.data)["data"][0]["id"]
    work_resp = client.post(
        f"/api/v1/rider/race-projects/{rp_id}/works",
        data=json.dumps({"title": "XDisq W"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {rider_a_token}"},
    )
    work = json.loads(work_resp.data)["data"]

    # organizer_b 尝试取消
    resp = client.post(
        f"/api/v1/organizer/works/{work['id']}/disqualify",
        data=json.dumps({"reason": "evil"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {organizer_b_token}"},
    )
    assert resp.status_code == 403
