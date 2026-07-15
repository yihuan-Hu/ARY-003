def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_public_races_hide_drafts_and_support_search_and_pagination(
    client, race_a, organizer_a_token
):
    client.post(
        "/api/v1/organizer/races",
        json={"name": "Hidden Draft"},
        headers=_auth(organizer_a_token),
    )

    response = client.get("/api/v1/public/races?q=Race&page=1&per_page=1")

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["total"] == 1
    assert data["per_page"] == 1
    assert data["items"][0]["id"] == race_a["id"]
    assert all(item["status"] != "draft" for item in data["items"])


def test_public_race_detail_includes_participant_and_work_counts(
    app, client, race_a, rider_a, rider_a_token
):
    registration = client.post(
        f"/api/v1/rider/races/{race_a['id']}/registrations",
        headers=_auth(rider_a_token),
    ).get_json()["data"]
    from app.database import get_db

    with app.app_context():
        db = get_db()
        db.execute(
            "UPDATE registrations SET status='approved' WHERE id=?",
            (registration["id"],),
        )
        project_id = db.execute(
            "INSERT INTO race_projects (registration_id) VALUES (?)",
            (registration["id"],),
        ).lastrowid
        db.execute(
            """INSERT INTO works
               (race_project_id, title, work_status, visibility, submitted_at)
               VALUES (?, 'Public Work', 'submitted', 'public', datetime('now'))""",
            (project_id,),
        )
        db.commit()

    response = client.get(f"/api/v1/public/races/{race_a['id']}")

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["participant_count"] == 1
    assert data["public_work_count"] == 1


def test_public_works_exclude_private_and_disqualified_entries(
    app, client, race_a, rider_a_token
):
    from app.database import get_db

    with app.app_context():
        db = get_db()
        user_id = db.execute(
            "SELECT id FROM users WHERE username='rider_a'"
        ).fetchone()["id"]
        registration_id = db.execute(
            """INSERT INTO registrations (race_id, user_id, status)
               VALUES (?, ?, 'approved')""",
            (race_a["id"], user_id),
        ).lastrowid
        project_id = db.execute(
            "INSERT INTO race_projects (registration_id) VALUES (?)",
            (registration_id,),
        ).lastrowid
        db.executemany(
            """INSERT INTO works
               (race_project_id, title, work_status, visibility, disqualified)
               VALUES (?, ?, 'submitted', ?, ?)""",
            [
                (project_id, "Visible", "public", 0),
                (project_id, "Private", "private", 0),
                (project_id, "Disqualified", "public", 1),
            ],
        )
        db.commit()

    response = client.get(f"/api/v1/public/races/{race_a['id']}/works")

    assert response.status_code == 200
    assert [work["title"] for work in response.get_json()["data"]] == ["Visible"]


def test_public_stats_and_integrity_endpoint_need_no_auth(
    app, client, race_a
):
    from app.database import get_db

    with app.app_context():
        db = get_db()
        user_id = db.execute("SELECT id FROM users LIMIT 1").fetchone()["id"]
        registration_id = db.execute(
            """INSERT INTO registrations (race_id, user_id, status)
               VALUES (?, ?, 'approved')""",
            (race_a["id"], user_id),
        ).lastrowid
        project_id = db.execute(
            "INSERT INTO race_projects (registration_id) VALUES (?)",
            (registration_id,),
        ).lastrowid
        work_id = db.execute(
            """INSERT INTO works
               (race_project_id, title, work_status, content_hash, content_commitment)
               VALUES (?, 'Counted', 'submitted', 'abc', 'def')""",
            (project_id,),
        ).lastrowid
        db.execute(
            """INSERT INTO integrity_log
               (event_type, resource_type, resource_id, actor_user_id,
                content_hash, commitment)
               VALUES ('work.submit', 'work', ?, ?, 'abc', 'def')""",
            (work_id, user_id),
        )
        db.commit()

    stats = client.get("/api/v1/public/stats")
    integrity = client.get(f"/api/v1/public/works/{work_id}/integrity")

    assert stats.status_code == 200
    assert stats.get_json()["data"]["total_races"] == 1
    assert stats.get_json()["data"]["total_works"] == 1
    assert integrity.status_code == 200
    integrity_data = integrity.get_json()["data"]
    assert integrity_data["chain_length"] == 1
    assert integrity_data["valid"] is True
    assert integrity_data["verification"]["commitments"] == "skipped"
