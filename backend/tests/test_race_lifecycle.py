import json
import sqlite3

import pytest
from flask import Flask

from app.database import init_db


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


def test_race_name_cannot_be_blank(client, organizer_a_token):
    create = client.post(
        "/api/v1/organizer/races",
        json={"name": "   "},
        headers=_auth(organizer_a_token),
    )
    assert create.status_code == 400

    race = _create_race(client, organizer_a_token)
    edit = client.put(
        f"/api/v1/organizer/races/{race['id']}",
        json={"name": "\t  "},
        headers=_auth(organizer_a_token),
    )
    assert edit.status_code == 400


def test_init_db_migrates_legacy_race_status_constraint(tmp_path):
    db_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(db_path)
    connection.executescript("""
        PRAGMA foreign_keys=ON;
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE races (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT,
            status TEXT NOT NULL DEFAULT 'upcoming'
                CHECK (status IN ('upcoming', 'open', 'judging', 'ended')),
            description TEXT,
            rules TEXT,
            schedule TEXT,
            visibility TEXT DEFAULT 'private',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE registrations (
            id INTEGER PRIMARY KEY,
            race_id INTEGER NOT NULL REFERENCES races(id),
            user_id INTEGER NOT NULL REFERENCES users(id),
            status TEXT NOT NULL DEFAULT 'submitted',
            submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (race_id, user_id)
        );
        INSERT INTO users (id, username, password_hash) VALUES (10, 'legacy', 'x');
        INSERT INTO races (id, name, status) VALUES (20, 'Legacy Race', 'open');
        INSERT INTO registrations (id, race_id, user_id) VALUES (30, 20, 10);
    """)
    connection.commit()
    connection.close()

    app = Flask(__name__)
    app.config.update(DATABASE_PATH=str(db_path), TESTING=True)
    init_db(app)

    connection = sqlite3.connect(db_path)
    status = connection.execute(
        "SELECT status FROM races WHERE id=20"
    ).fetchone()[0]
    fk_targets = {
        row[2] for row in connection.execute("PRAGMA foreign_key_list(registrations)")
    }
    connection.execute("UPDATE races SET status='running' WHERE id=20")
    connection.commit()
    connection.close()

    assert status == "registration"
    assert "races" in fk_targets


def test_init_db_replaces_legacy_work_seal_trigger(tmp_path):
    db_path = tmp_path / "legacy-trigger.db"
    app = Flask(__name__)
    app.config.update(DATABASE_PATH=str(db_path), TESTING=True)
    init_db(app)

    connection = sqlite3.connect(db_path)
    connection.executescript("""
        INSERT INTO races (id, name, status, created_by_user_id)
        VALUES (1, 'Sealed Race', 'judging', 2);
        INSERT INTO registrations (id, race_id, user_id, status)
        VALUES (1, 1, 1, 'approved');
        INSERT INTO race_projects (id, registration_id) VALUES (1, 1);
        INSERT INTO works (id, race_project_id, title) VALUES (1, 1, 'Work');
        DROP TRIGGER trg_works_sealed;
        CREATE TRIGGER trg_works_sealed
        BEFORE UPDATE ON works
        WHEN (
            SELECT r.status FROM race_projects rp
            JOIN registrations reg ON rp.registration_id = reg.id
            JOIN races r ON reg.race_id = r.id
            WHERE rp.id = NEW.race_project_id
        ) IN ('judging', 'completed', 'archived')
        BEGIN
            SELECT RAISE(ABORT, 'legacy broad seal');
        END;
    """)
    connection.commit()
    connection.close()

    init_db(app)

    connection = sqlite3.connect(db_path)
    connection.execute(
        "UPDATE works SET disqualified=1, disqualify_reason='rule' WHERE id=1"
    )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute("UPDATE works SET title='Changed' WHERE id=1")
    connection.close()
