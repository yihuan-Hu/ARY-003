def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _create(client, race_id, token, title="Schedule Update"):
    response = client.post(
        f"/api/v1/organizer/races/{race_id}/announcements",
        json={"title": title, "body": "Judging starts at 18:00."},
        headers=_auth(token),
    )
    assert response.status_code == 201
    return response.get_json()["data"]


def test_announcement_publish_makes_it_public(
    client, race_a, organizer_a_token
):
    announcement = _create(client, race_a["id"], organizer_a_token)
    before = client.get(
        f"/api/v1/public/races/{race_a['id']}/announcements"
    )
    assert before.get_json()["data"] == []

    published = client.post(
        f"/api/v1/organizer/announcements/{announcement['id']}/publish",
        headers=_auth(organizer_a_token),
    )

    assert published.status_code == 200
    assert published.get_json()["data"]["visibility"] == "public"
    public = client.get(
        f"/api/v1/public/races/{race_a['id']}/announcements"
    )
    assert [item["id"] for item in public.get_json()["data"]] == [
        announcement["id"]
    ]


def test_hidden_announcement_is_removed_from_public_list(
    client, race_a, organizer_a_token
):
    announcement = _create(client, race_a["id"], organizer_a_token)
    client.post(
        f"/api/v1/organizer/announcements/{announcement['id']}/publish",
        headers=_auth(organizer_a_token),
    )
    hidden = client.post(
        f"/api/v1/organizer/announcements/{announcement['id']}/hide",
        headers=_auth(organizer_a_token),
    )

    assert hidden.status_code == 200
    assert hidden.get_json()["data"]["visibility"] == "private"
    public = client.get(
        f"/api/v1/public/races/{race_a['id']}/announcements"
    )
    assert public.get_json()["data"] == []


def test_other_organizer_cannot_edit_announcement(
    client, race_a, organizer_a_token, organizer_b_token
):
    announcement = _create(client, race_a["id"], organizer_a_token)

    response = client.put(
        f"/api/v1/organizer/announcements/{announcement['id']}",
        json={"title": "Hijacked"},
        headers=_auth(organizer_b_token),
    )

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "FORBIDDEN"
