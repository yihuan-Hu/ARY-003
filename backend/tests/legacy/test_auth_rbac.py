def test_login_returns_role_token(client):
    response = client.post('/api/v1/auth/login', json={
        'username': 'organizer',
        'password': 'organizer123',
    })

    assert response.status_code == 200
    data = response.get_json()
    assert data['token']
    assert data['user']['role'] == 1


def test_organizer_endpoint_requires_token(client):
    response = client.post('/api/races', json={
        'title': 'Blocked',
        'description': 'No token',
        'startTime': '2026-06-13T00:00:00Z',
        'endTime': '2026-06-14T00:00:00Z',
    })

    assert response.status_code == 401


def test_contestant_cannot_call_organizer_api(client, contestant_headers):
    response = client.post('/api/v1/organizer/races', json={
        'title': 'Blocked',
        'description': 'Wrong role',
        'startTime': '2026-06-13T00:00:00Z',
        'endTime': '2026-06-14T00:00:00Z',
    }, headers=contestant_headers)

    assert response.status_code == 403


def test_organizer_namespace_creates_race(client, organizer_headers):
    response = client.post('/api/v1/organizer/races', json={
        'title': 'Organizer Race',
        'description': 'Created through namespace.',
        'startTime': '2026-06-13T00:00:00Z',
        'endTime': '2026-06-14T00:00:00Z',
        'status': 'open',
    }, headers=organizer_headers)

    assert response.status_code == 201
    assert response.get_json()['title'] == 'Organizer Race'


def test_contestant_namespace_public_race_list(client, race):
    response = client.get('/api/v1/contestant/races')

    assert response.status_code == 200
    assert response.get_json()[0]['id'] == race['id']
