import json


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _create_race(client, token, name="Lifecycle Race"):
    response = client.post(
        "/api/v1/organizer/races",
        data=json.dumps({"name": name, "status": "archived"}),
        content_type="application/json",
        headers=_auth(token),
    )
    assert response.status_code == 201
    return response.get_json()["data"]


def _transition(client, token, race_id, action):
    return client.post(
        f"/api/v1/organizer/races/{race_id}/{action}",
        headers=_auth(token),
    )


def test_race_is_created_as_draft_and_follows_complete_lifecycle(
    client, organizer_a_token
):
    race = _create_race(client, organizer_a_token)
    assert race["status"] == "draft"

    transitions = [
        ("publish", "published"),
        ("open-registration", "registration"),
        ("start", "running"),
        ("open-submissions", "submitting"),
        ("start-judging", "judging"),
        ("complete", "completed"),
        ("archive", "archived"),
    ]
    for action, expected_status in transitions:
        response = _transition(client, organizer_a_token, race["id"], action)
        assert response.status_code == 200
        assert response.get_json()["data"]["status"] == expected_status


def test_race_rejects_invalid_transition(client, organizer_a_token):
    race = _create_race(client, organizer_a_token)

    response = _transition(
        client, organizer_a_token, race["id"], "open-registration"
    )

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "INVALID_STATE"


def test_other_organizer_cannot_transition_race(
    client, organizer_a_token, organizer_b_token
):
    race = _create_race(client, organizer_a_token)

    response = _transition(client, organizer_b_token, race["id"], "publish")

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "FORBIDDEN"


def test_race_edit_is_allowed_before_running_and_rejected_afterward(
    client, organizer_a_token
):
    race = _create_race(client, organizer_a_token)
    response = client.put(
        f"/api/v1/organizer/races/{race['id']}",
        data=json.dumps({
            "name": "Edited Race",
            "ca_policy": "organizer_specified",
            "ca_policy_config": '{"allowed_ca_types":["cursor"]}',
            "judging_mode": "open",
        }),
        content_type="application/json",
        headers=_auth(organizer_a_token),
    )
    assert response.status_code == 200
    assert response.get_json()["data"]["name"] == "Edited Race"

    for action in ("publish", "open-registration", "start"):
        assert _transition(
            client, organizer_a_token, race["id"], action
        ).status_code == 200

    response = client.put(
        f"/api/v1/organizer/races/{race['id']}",
        data=json.dumps({"name": "Too Late"}),
        content_type="application/json",
        headers=_auth(organizer_a_token),
    )
    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "INVALID_STATE"


def test_organizer_race_list_is_paginated(client, organizer_a_token):
    _create_race(client, organizer_a_token, "Race One")
    _create_race(client, organizer_a_token, "Race Two")

    response = client.get(
        "/api/v1/organizer/races?page=1&per_page=1",
        headers=_auth(organizer_a_token),
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["total"] == 2
    assert data["page"] == 1
    assert data["per_page"] == 1
    assert len(data["items"]) == 1
