def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_coach_returns_waiting_for_approval_for_submitted_registration(
    app, client, race_a, rider_a, rider_a_token
):
    registration = client.post(
        f"/api/v1/rider/races/{race_a['id']}/registrations",
        headers=_auth(rider_a_token),
    ).get_json()["data"]

    from app.database import get_db

    with app.app_context():
        db = get_db()
        project_id = db.execute(
            "INSERT INTO race_projects (registration_id) VALUES (?)",
            (registration["id"],),
        ).lastrowid
        db.commit()

    response = client.get(
        f"/api/v1/rider/race-projects/{project_id}/next-actions",
        headers=_auth(rider_a_token),
    )

    assert response.status_code == 200
    assert response.get_json()["data"] == [{
        "action_label": "等待审批",
        "description": "报名已提交，等待主办方审批",
        "target_url": f"/rider/registrations/{registration['id']}",
    }]


def test_coach_recommends_ca_and_work_after_approval(
    client, race_a, rider_a_token, organizer_a_token
):
    registration = client.post(
        f"/api/v1/rider/races/{race_a['id']}/registrations",
        headers=_auth(rider_a_token),
    ).get_json()["data"]
    project = client.post(
        f"/api/v1/organizer/registrations/{registration['id']}/approve",
        headers=_auth(organizer_a_token),
    ).get_json()["data"]["race_project"]

    response = client.get(
        f"/api/v1/rider/race-projects/{project['id']}/next-actions",
        headers=_auth(rider_a_token),
    )

    assert response.status_code == 200
    labels = [item["action_label"] for item in response.get_json()["data"]]
    assert labels == ["接入编码助手", "提交作品"]
