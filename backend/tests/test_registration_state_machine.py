"""角色 3：Registration API 与业务状态机测试。"""

import json

import pytest

from app.dao.race_project_dao import RaceProjectDAO
from app.database import get_db
from app.services.registration_service import RegistrationService
from app.utils.errors import ConflictError, InvalidStateError


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _submit(client, race_id, rider_token):
    response = client.post(
        f"/api/v1/rider/races/{race_id}/registrations",
        headers=_auth(rider_token),
    )
    assert response.status_code == 201
    return json.loads(response.data)["data"]


def _review(client, registration_id, action, organizer_token):
    return client.post(
        f"/api/v1/organizer/registrations/{registration_id}/{action}",
        headers=_auth(organizer_token),
    )


@pytest.mark.parametrize("target_action", ["approve", "reject"])
def test_rejected_registration_rejects_all_further_review_transitions(
    client,
    race_a,
    rider_a_token,
    organizer_a_token,
    target_action,
):
    registration = _submit(client, race_a["id"], rider_a_token)
    assert _review(
        client,
        registration["id"],
        "reject",
        organizer_a_token,
    ).status_code == 200

    response = _review(
        client,
        registration["id"],
        target_action,
        organizer_a_token,
    )

    assert response.status_code == 422
    body = json.loads(response.data)
    assert body["error"]["code"] == "INVALID_STATE"
    assert "rejected" in body["error"]["message"]


def test_rejected_registration_cannot_be_withdrawn(
    client,
    race_a,
    rider_a_token,
    organizer_a_token,
):
    registration = _submit(client, race_a["id"], rider_a_token)
    assert _review(
        client,
        registration["id"],
        "reject",
        organizer_a_token,
    ).status_code == 200

    response = client.post(
        f"/api/v1/rider/registrations/{registration['id']}/withdraw",
        headers=_auth(rider_a_token),
    )

    assert response.status_code == 422
    assert json.loads(response.data)["error"]["code"] == "INVALID_STATE"


def test_approved_registration_cannot_be_rejected(
    client,
    race_a,
    rider_a_token,
    organizer_a_token,
):
    registration = _submit(client, race_a["id"], rider_a_token)
    assert _review(
        client,
        registration["id"],
        "approve",
        organizer_a_token,
    ).status_code == 200

    response = _review(
        client,
        registration["id"],
        "reject",
        organizer_a_token,
    )

    assert response.status_code == 422
    assert json.loads(response.data)["error"]["code"] == "INVALID_STATE"


@pytest.mark.parametrize("target_action", ["approve", "reject"])
def test_withdrawn_registration_rejects_organizer_review(
    client,
    race_a,
    rider_a_token,
    organizer_a_token,
    target_action,
):
    registration = _submit(client, race_a["id"], rider_a_token)
    withdraw = client.post(
        f"/api/v1/rider/registrations/{registration['id']}/withdraw",
        headers=_auth(rider_a_token),
    )
    assert withdraw.status_code == 200

    response = _review(
        client,
        registration["id"],
        target_action,
        organizer_a_token,
    )

    assert response.status_code == 422
    assert json.loads(response.data)["error"]["code"] == "INVALID_STATE"


def test_approval_rolls_back_when_race_project_creation_fails(
    app,
    race_a,
    rider_a,
    organizer_a,
    monkeypatch,
):
    """approved 与 RaceProject 创建必须处于同一真实事务。"""
    with app.app_context():
        service = RegistrationService()
        registration = service.submit(race_a["id"], rider_a["id"])

        def fail_create(*args, **kwargs):
            raise RuntimeError("simulated RaceProject failure")

        monkeypatch.setattr(service.race_project_dao, "create", fail_create)

        with pytest.raises(RuntimeError, match="simulated RaceProject failure"):
            service.approve_registration(registration["id"], organizer_a["id"])

        persisted = service.dao.find_by_id(registration["id"])
        assert persisted["status"] == "submitted"
        assert service.race_project_dao.find_by_registration(registration["id"]) is None


def test_database_duplicate_is_translated_to_explicit_conflict(
    app,
    race_a,
    rider_a,
    monkeypatch,
):
    """即使并发请求绕过预检查，UNIQUE 冲突也必须映射为 409 语义。"""
    with app.app_context():
        service = RegistrationService()
        service.submit(race_a["id"], rider_a["id"])

        original_find = service.dao.find_by_race_and_user
        calls = {"count": 0}

        def simulate_concurrent_insert(race_id, user_id):
            calls["count"] += 1
            # 事务外和事务内两次读取都模拟“尚未看到并发写入”，让 UNIQUE 兜底触发。
            if calls["count"] <= 2:
                return None
            return original_find(race_id, user_id)

        monkeypatch.setattr(
            service.dao,
            "find_by_race_and_user",
            simulate_concurrent_insert,
        )

        with pytest.raises(ConflictError, match="already registered"):
            service.submit(race_a["id"], rider_a["id"])


def test_ca_ingestion_status_never_withdraws_registration(
    app,
    client,
    race_a,
    rider_a_token,
    organizer_a_token,
):
    """CA 接入健康度不进入 Registration 状态机。"""
    registration = _submit(client, race_a["id"], rider_a_token)
    approval = _review(
        client,
        registration["id"],
        "approve",
        organizer_a_token,
    )
    race_project = json.loads(approval.data)["data"]["race_project"]

    with app.app_context():
        db = get_db()
        db.execute(
            """UPDATE race_projects
               SET aggregate_ingestion_status = 'failed',
                   connection_health = 'no_signal'
               WHERE id = ?""",
            (race_project["id"],),
        )
        db.commit()

        persisted_registration = db.execute(
            "SELECT status FROM registrations WHERE id = ?",
            (registration["id"],),
        ).fetchone()
        assert persisted_registration["status"] == "approved"

        persisted_project = RaceProjectDAO().find_by_id(race_project["id"])
        assert persisted_project["aggregate_ingestion_status"] == "failed"

    response = client.get(
        f"/api/v1/rider/registrations/{registration['id']}",
        headers=_auth(rider_a_token),
    )
    assert response.status_code == 200
    assert json.loads(response.data)["data"]["status"] == "approved"


def test_withdraw_preserves_prior_review_audit_fields(
    client,
    race_a,
    rider_a_token,
    organizer_a_token,
    organizer_a,
):
    registration = _submit(client, race_a["id"], rider_a_token)
    approval = _review(
        client,
        registration["id"],
        "approve",
        organizer_a_token,
    )
    approved = json.loads(approval.data)["data"]["registration"]
    assert approved["reviewed_by_user_id"] == organizer_a["id"]
    assert approved["reviewed_at"] is not None

    withdrawal = client.post(
        f"/api/v1/rider/registrations/{registration['id']}/withdraw",
        headers=_auth(rider_a_token),
    )
    withdrawn = json.loads(withdrawal.data)["data"]["registration"]

    assert withdrawn["status"] == "withdrawn"
    assert withdrawn["reviewed_by_user_id"] == organizer_a["id"]
    assert withdrawn["reviewed_at"] == approved["reviewed_at"]


def test_withdraw_rechecks_state_inside_transaction(
    app,
    race_a,
    rider_a,
    monkeypatch,
):
    """事务外通过校验后，事务内状态变化必须被重新检查。"""
    with app.app_context():
        service = RegistrationService()
        registration = service.submit(race_a["id"], rider_a["id"])
        original_find = service.dao.find_by_id
        reads = {"count": 0}

        def simulate_concurrent_terminal_transition(registration_id):
            reads["count"] += 1
            current = original_find(registration_id)
            if reads["count"] == 1:
                return current
            changed = dict(current)
            changed["status"] = "rejected"
            return changed

        monkeypatch.setattr(
            service.dao,
            "find_by_id",
            simulate_concurrent_terminal_transition,
        )

        with pytest.raises(InvalidStateError):
            service.withdraw(registration["id"], rider_a["id"])

        assert original_find(registration["id"])["status"] == "submitted"


def test_submit_rechecks_race_status_inside_transaction(
    app,
    race_a,
    rider_a,
    monkeypatch,
):
    """预检查后 Race 若已关闭，事务内重读必须拒绝创建报名。"""
    with app.app_context():
        service = RegistrationService()
        original_find = service.race_dao.find_by_id
        reads = {"count": 0}

        def simulate_race_closing(race_id):
            reads["count"] += 1
            race = original_find(race_id)
            if reads["count"] == 1:
                return race
            closed = dict(race)
            closed["status"] = "ended"
            return closed

        monkeypatch.setattr(service.race_dao, "find_by_id", simulate_race_closing)

        with pytest.raises(InvalidStateError, match="ended"):
            service.submit(race_a["id"], rider_a["id"])

        assert service.dao.find_by_race_and_user(race_a["id"], rider_a["id"]) is None


def test_other_rider_cannot_distinguish_existing_registration_from_missing(
    client,
    race_a,
    rider_a_token,
    rider_b_token,
):
    registration = _submit(client, race_a["id"], rider_a_token)

    existing_other = client.get(
        f"/api/v1/rider/registrations/{registration['id']}",
        headers=_auth(rider_b_token),
    )
    missing = client.get(
        "/api/v1/rider/registrations/999999",
        headers=_auth(rider_b_token),
    )

    assert existing_other.status_code == 404
    assert missing.status_code == 404
    assert json.loads(existing_other.data)["error"] == json.loads(missing.data)["error"]


def test_other_rider_cannot_distinguish_existing_race_project_from_missing(
    client,
    race_a,
    rider_a_token,
    rider_b_token,
    organizer_a_token,
):
    registration = _submit(client, race_a["id"], rider_a_token)
    approval = _review(
        client,
        registration["id"],
        "approve",
        organizer_a_token,
    )
    race_project = json.loads(approval.data)["data"]["race_project"]

    existing_other = client.get(
        f"/api/v1/rider/race-projects/{race_project['id']}",
        headers=_auth(rider_b_token),
    )
    missing = client.get(
        "/api/v1/rider/race-projects/999999",
        headers=_auth(rider_b_token),
    )

    assert existing_other.status_code == 404
    assert missing.status_code == 404
    assert json.loads(existing_other.data)["error"] == json.loads(missing.data)["error"]
