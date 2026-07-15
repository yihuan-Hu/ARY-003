from app.database import get_db


def _create_approved_race_project(db, race_id: int, user_id: int) -> int:
    reg_id = db.execute(
        "INSERT INTO registrations (race_id, user_id, status) VALUES (?, ?, 'approved')",
        (race_id, user_id),
    ).lastrowid
    race_project_id = db.execute(
        "INSERT INTO race_projects (registration_id) VALUES (?)",
        (reg_id,),
    ).lastrowid
    db.commit()
    return race_project_id


def test_works_table_contract_exists(app):
    with app.app_context():
        db = get_db()
        columns = {
            row["name"]: row
            for row in db.execute("PRAGMA table_info(works)").fetchall()
        }

    assert "race_project_id" in columns
    assert "title" in columns
    assert "repo_url" in columns
    assert "demo_url" in columns
    assert "video_url" in columns
    assert "cover_image_url" in columns
    assert "screenshot_urls" in columns
    assert "readme_body" in columns
    assert "work_status" in columns
    assert "content_hash" in columns
    assert "content_commitment" in columns
    assert "prev_hash" in columns
    assert "version" in columns
    assert "submitted_at" in columns
    assert "disqualified" in columns
    assert "disqualify_reason" in columns


def test_work_dao_contract_creates_and_submits_work(app, race_a, rider_a):
    from app.dao.work_dao import WorkDAO

    with app.app_context():
        db = get_db()
        race_project_id = _create_approved_race_project(db, race_a["id"], rider_a["id"])

        dao = WorkDAO()
        draft = dao.create_draft(
            race_project_id,
            "Frozen Work Contract",
            repo_url="https://example.test/repo",
            demo_url="https://example.test/demo",
        )

        assert draft["race_project_id"] == race_project_id
        assert draft["title"] == "Frozen Work Contract"
        assert draft["work_status"] == "draft"
        assert draft["version"] == 1

        submitted = dao.mark_submitted(draft["id"], "hash-v1", "commitment-v1")

        assert submitted["work_status"] == "submitted"
        assert submitted["content_hash"] == "hash-v1"
        assert submitted["content_commitment"] == "commitment-v1"
        assert submitted["submitted_at"] is not None
        assert dao.find_by_race_project(race_project_id)[0]["id"] == draft["id"]
        assert dao.find_submitted_by_race(race_a["id"])[0]["id"] == draft["id"]


def test_work_dao_contract_filters_public_and_disqualified_works(app, race_a, rider_a):
    from app.dao.work_dao import WorkDAO

    with app.app_context():
        db = get_db()
        race_project_id = _create_approved_race_project(db, race_a["id"], rider_a["id"])

        dao = WorkDAO()
        work = dao.create_draft(
            race_project_id,
            "Public Work",
            visibility="public",
        )
        dao.mark_submitted(work["id"], "hash-v1", "commitment-v1")

        public_works = dao.find_public_by_race(race_a["id"])
        assert [item["id"] for item in public_works] == [work["id"]]

        disqualified = dao.set_disqualified(work["id"], "rules violation")
        assert disqualified["disqualified"] == 1
        assert disqualified["disqualify_reason"] == "rules violation"
        assert dao.find_public_by_race(race_a["id"]) == []

        restored = dao.restore(work["id"])
        assert restored["disqualified"] == 0
        assert restored["disqualify_reason"] == ""
        assert [item["id"] for item in dao.find_public_by_race(race_a["id"])] == [work["id"]]


def test_d_can_keep_using_race_project_dao_contract(app, race_a, rider_a):
    from app.dao.race_project_dao import RaceProjectDAO

    with app.app_context():
        db = get_db()
        race_project_id = _create_approved_race_project(db, race_a["id"], rider_a["id"])

        dao = RaceProjectDAO()
        by_id = dao.find_by_id(race_project_id)

        assert by_id["id"] == race_project_id
        assert dao.find_by_registration(by_id["registration_id"])["id"] == race_project_id
        assert dao.find_by_race(race_a["id"])[0]["id"] == race_project_id
        assert dao.find_by_user(rider_a["id"])[0]["id"] == race_project_id
