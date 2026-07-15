def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _advance(client, token, race_id, *actions):
    race = None
    for action in actions:
        response = client.post(
            f"/api/v1/organizer/races/{race_id}/{action}", headers=_auth(token)
        )
        assert response.status_code == 200
        race = response.get_json()["data"]
    return race


def _approved_project(
    client, race_a, rider_a_token, organizer_a_token
):
    registration = client.post(
        f"/api/v1/rider/races/{race_a['id']}/registrations",
        headers=_auth(rider_a_token),
    ).get_json()["data"]
    approved = client.post(
        f"/api/v1/organizer/registrations/{registration['id']}/approve",
        headers=_auth(organizer_a_token),
    )
    return approved.get_json()["data"]["race_project"]


def _create_work(client, token, race_project_id):
    response = client.post(
        f"/api/v1/rider/race-projects/{race_project_id}/works",
        json={
            "title": "Hash Chain Work",
            "description": "First version",
            "repo_url": "https://example.com/repo",
            "demo_url": "https://example.com/demo",
            "readme_body": "# Work",
            "visibility": "public",
        },
        headers=_auth(token),
    )
    assert response.status_code == 201
    return response.get_json()["data"]


def test_work_submit_creates_hash_commitment_and_integrity_event(
    app, client, race_a, rider_a_token, organizer_a_token
):
    project = _approved_project(
        client, race_a, rider_a_token, organizer_a_token
    )
    _advance(
        client, organizer_a_token, race_a["id"], "start", "open-submissions"
    )
    work = _create_work(client, rider_a_token, project["id"])

    response = client.post(
        f"/api/v1/rider/works/{work['id']}/submit",
        headers=_auth(rider_a_token),
    )

    assert response.status_code == 200
    submitted = response.get_json()["data"]
    assert submitted["work_status"] == "submitted"
    assert submitted["version"] == 1
    assert len(submitted["content_hash"]) == 64
    assert len(submitted["content_commitment"]) == 64
    assert submitted["prev_hash"] is None

    from app.database import get_db

    with app.app_context():
        event = get_db().execute(
            "SELECT * FROM integrity_log WHERE resource_type='work' AND resource_id=?",
            (work["id"],),
        ).fetchone()
    assert event is not None
    assert event["content_hash"] == submitted["content_hash"]


def test_edit_and_resubmit_creates_version_two_hash_chain(
    client, race_a, rider_a_token, organizer_a_token
):
    project = _approved_project(
        client, race_a, rider_a_token, organizer_a_token
    )
    _advance(
        client, organizer_a_token, race_a["id"], "start", "open-submissions"
    )
    work = _create_work(client, rider_a_token, project["id"])
    first = client.post(
        f"/api/v1/rider/works/{work['id']}/submit",
        headers=_auth(rider_a_token),
    ).get_json()["data"]

    edited_response = client.put(
        f"/api/v1/rider/works/{work['id']}",
        json={
            "title": "Hash Chain Work v2",
            "description": "Second version",
            "repo_url": "https://example.com/repo",
            "demo_url": "https://example.com/demo-v2",
            "readme_body": "# Work v2",
            "visibility": "public",
        },
        headers=_auth(rider_a_token),
    )
    assert edited_response.status_code == 200
    assert edited_response.get_json()["data"]["work_status"] == "draft"

    second = client.post(
        f"/api/v1/rider/works/{work['id']}/submit",
        headers=_auth(rider_a_token),
    ).get_json()["data"]

    assert second["version"] == 2
    assert second["prev_hash"] == first["content_hash"]
    assert second["content_hash"] != first["content_hash"]


def test_judging_seals_rider_submit_edit_and_delete(
    client, race_a, rider_a_token, organizer_a_token
):
    project = _approved_project(
        client, race_a, rider_a_token, organizer_a_token
    )
    _advance(
        client, organizer_a_token, race_a["id"], "start", "open-submissions"
    )
    work = _create_work(client, rider_a_token, project["id"])
    _advance(client, organizer_a_token, race_a["id"], "start-judging")

    submit = client.post(
        f"/api/v1/rider/works/{work['id']}/submit",
        headers=_auth(rider_a_token),
    )
    edit = client.put(
        f"/api/v1/rider/works/{work['id']}",
        json={"title": "Sealed"},
        headers=_auth(rider_a_token),
    )
    delete = client.delete(
        f"/api/v1/rider/works/{work['id']}", headers=_auth(rider_a_token)
    )

    for response in (submit, edit, delete):
        assert response.status_code == 422
        assert response.get_json()["error"]["code"] == "INVALID_STATE"


def test_other_rider_cannot_edit_work(
    client, race_a, rider_a_token, rider_b_token, organizer_a_token
):
    project = _approved_project(
        client, race_a, rider_a_token, organizer_a_token
    )
    work = _create_work(client, rider_a_token, project["id"])

    response = client.put(
        f"/api/v1/rider/works/{work['id']}",
        json={"title": "Stolen"},
        headers=_auth(rider_b_token),
    )

    assert response.status_code == 404
