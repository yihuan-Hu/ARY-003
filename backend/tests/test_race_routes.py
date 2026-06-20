def test_create_and_get_race_detail(client, race):
    response = client.get(f"/api/races/{race['id']}")

    assert response.status_code == 200
    data = response.get_json()
    assert data['id'] == race['id']
    assert data['theme'] == 'Target mode'
    assert data['submissions'] == []


def test_update_race(client, race, organizer_headers):
    response = client.put(
        f"/api/races/{race['id']}",
        json={'status': 'judging'},
        headers=organizer_headers,
    )

    assert response.status_code == 200
    assert response.get_json()['status'] == 'judging'
