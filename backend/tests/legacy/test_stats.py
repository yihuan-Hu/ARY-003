def test_stats_shape(client, race):
    response = client.get('/api/stats')

    assert response.status_code == 200
    data = response.get_json()
    assert data['raceCount'] == 1
    assert data['submissionCount'] == 0
    assert data['studentCount'] == 0
    assert data['submissionsByRace'][0]['raceId'] == race['id']


def test_organizer_namespace_stats_requires_auth(client):
    response = client.get('/api/v1/organizer/stats')

    assert response.status_code == 401


def test_organizer_namespace_stats_allows_organizer(client, race, organizer_headers):
    response = client.get('/api/v1/organizer/stats', headers=organizer_headers)

    assert response.status_code == 200
    assert response.get_json()['raceCount'] == 1
