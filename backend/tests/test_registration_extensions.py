def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_registration_requires_registration_race_status(
    client, organizer_a_token, rider_a_token
):
    race = client.post(
        "/api/v1/organizer/races",
        json={"name": "Draft Race"},
        headers=_auth(organizer_a_token),
    ).get_json()["data"]

    response = client.post(
        f"/api/v1/rider/races/{race['id']}/registrations",
        headers=_auth(rider_a_token),
    )

    assert response.status_code == 422
    assert response.get_json()["error"]["message"] == (
        "Registration is not open for this race"
    )


def test_rider_registration_list_supports_status_filter_and_pagination(
    client, race_a, rider_a_token
):
    created = client.post(
        f"/api/v1/rider/races/{race_a['id']}/registrations",
        headers=_auth(rider_a_token),
    )
    assert created.status_code == 201

    response = client.get(
        "/api/v1/rider/registrations?status=submitted&page=1&per_page=1",
        headers=_auth(rider_a_token),
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["total"] == 1
    assert data["page"] == 1
    assert data["per_page"] == 1
    assert data["items"][0]["status"] == "submitted"


def test_rider_can_list_registered_races(client, race_a, rider_a_token):
    client.post(
        f"/api/v1/rider/races/{race_a['id']}/registrations",
        headers=_auth(rider_a_token),
    )

    response = client.get(
        "/api/v1/rider/races", headers=_auth(rider_a_token)
    )

    assert response.status_code == 200
    assert response.get_json()["data"] == [{
        "race_id": race_a["id"],
        "name": race_a["name"],
        "status": "registration",
    }]


def test_registration_writes_audit_log(app, client, race_a, rider_a, rider_a_token):
    response = client.post(
        f"/api/v1/rider/races/{race_a['id']}/registrations",
        headers=_auth(rider_a_token),
    )
    registration_id = response.get_json()["data"]["id"]

    from app.database import get_db

    with app.app_context():
        row = get_db().execute(
            """SELECT * FROM audit_logs
               WHERE action = 'registration.submit' AND target_id = ?""",
            (registration_id,),
        ).fetchone()

    assert row is not None
    assert row["actor_user_id"] == rider_a["id"]
