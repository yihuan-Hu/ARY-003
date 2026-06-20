import os
import tempfile

import pytest

from app import create_app


@pytest.fixture
def client():
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    os.unlink(db_path)
    os.environ['ORGANIZER_DB'] = db_path

    app = create_app('test')
    with app.test_client() as client:
        yield client

    os.environ.pop('ORGANIZER_DB', None)
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def organizer_headers(client):
    response = client.post('/api/v1/auth/login', json={
        'username': 'organizer',
        'password': 'organizer123',
    })
    assert response.status_code == 200
    return {'Authorization': 'Bearer ' + response.get_json()['token']}


@pytest.fixture
def contestant_headers(client):
    response = client.post('/api/v1/auth/login', json={
        'username': 'contestant',
        'password': 'contestant123',
    })
    assert response.status_code == 200
    return {'Authorization': 'Bearer ' + response.get_json()['token']}


@pytest.fixture
def race(client, organizer_headers):
    response = client.post('/api/races', json={
        'title': 'Test Race',
        'description': 'Endpoint verification race.',
        'startTime': '2026-06-13T00:00:00Z',
        'endTime': '2026-06-14T00:00:00Z',
        'status': 'open',
        'theme': 'Target mode',
        'organizer': 'ARY',
        'currentRound': 2,
        'currentPhase': 'DEV',
    }, headers=organizer_headers)
    assert response.status_code == 201
    return response.get_json()


@pytest.fixture
def rider(client, organizer_headers):
    response = client.post('/api/riders', json={'name': 'Ada'}, headers=organizer_headers)
    assert response.status_code == 201
    return response.get_json()
