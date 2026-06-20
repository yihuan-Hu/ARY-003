"""Create sample target-mode data through the Flask API.

Default users are seeded by init_db():
  - organizer / organizer123   (role 1)
  - contestant / contestant123  (role 0)
  - admin / admin123            (role 2)

Usage:
    python -m scripts.seed_demo
"""

import json
from pathlib import Path

from app import create_app


def login(client, username, password):
    response = client.post('/api/v1/auth/login', json={
        'username': username,
        'password': password,
    })
    if response.status_code >= 400:
        raise RuntimeError(f'login failed: {response.status_code} {response.get_json()}')
    token = response.get_json()['token']
    return {'Authorization': f'Bearer {token}'}


def post(client, path, payload, headers=None):
    response = client.post(path, json=payload, headers=headers or {})
    if response.status_code >= 400:
        raise RuntimeError(f'{path} failed: {response.status_code} {response.get_json()}')
    return response.get_json()


def main():
    app = create_app()
    with app.test_client() as client:
        org_headers = login(client, 'organizer', 'organizer123')
        con_headers = login(client, 'contestant', 'contestant123')

        race = post(client, '/api/races', {
            'title': 'ARY GRS 002 Jumbotron Challenge',
            'description': 'Target-mode race data for the live view.',
            'startTime': '2026-06-13T00:00:00Z',
            'endTime': '2026-06-20T23:59:59Z',
            'status': 'open',
            'theme': 'Ride Agents. Build the Future.',
            'organizer': 'ARY Core Team',
            'currentRound': 2,
            'currentPhase': 'DEV',
        }, org_headers)

        riders = [
            post(client, '/api/riders', {'name': 'Ada'}, org_headers),
            post(client, '/api/riders', {'name': 'Grace'}, org_headers),
            post(client, '/api/riders', {'name': 'Linus'}, org_headers),
        ]

        entries = [
            {
                'rider': riders[0],
                'projectName': 'Race Live View',
                'caProvider': 'codex',
                'overallProgress': 0.82,
                'roundProgress': 0.76,
                'phaseProgress': 0.9,
                'currentPhase': 'REL',
                'costTokens': 245000,
                'costUsd': 7.35,
                'riskLevel': 'low',
                'obstacleCount': 1,
                'violationCount': 0,
                'laneId': 'lane_1',
                'status': 'running',
                'message': 'Rendering and data adapter are connected.',
                'msgType': 'milestone',
            },
            {
                'rider': riders[1],
                'projectName': 'Track Calibrator',
                'caProvider': 'claude',
                'overallProgress': 0.64,
                'roundProgress': 0.61,
                'phaseProgress': 0.7,
                'currentPhase': 'DEV',
                'costTokens': 180000,
                'costUsd': 5.4,
                'riskLevel': 'none',
                'obstacleCount': 0,
                'violationCount': 0,
                'laneId': 'lane_2',
                'status': 'sprinting',
                'message': 'Lane profile export is ready.',
                'msgType': 'progress_update',
            },
            {
                'rider': riders[2],
                'projectName': 'Runtime KPI Bridge',
                'caProvider': 'codex',
                'overallProgress': 0.48,
                'roundProgress': 0.43,
                'phaseProgress': 0.5,
                'currentPhase': 'DEV',
                'costTokens': 122000,
                'costUsd': 3.66,
                'riskLevel': 'medium',
                'obstacleCount': 2,
                'violationCount': 1,
                'laneId': 'lane_3',
                'status': 'blocked',
                'message': 'Investigating snapshot latency.',
                'msgType': 'risk_alert',
            },
        ]

        for item in entries:
            rider = item.pop('rider')
            message = item.pop('message')
            msg_type = item.pop('msgType')
            entry = post(client, '/api/entries', {
                'raceId': race['id'],
                'riderId': rider['id'],
                **item,
            }, org_headers)
            post(client, '/api/agent-usage', {
                'raceId': race['id'],
                'entryId': entry['entryId'],
                'riderId': rider['id'],
                'provider': item['caProvider'],
                'model': 'gpt-5-codex' if item['caProvider'] == 'codex' else 'claude-sonnet',
                'apiEndpoint': '/v1/responses' if item['caProvider'] == 'codex' else '/v1/messages',
                'promptTokens': int(item['costTokens'] * 0.62),
                'completionTokens': item['costTokens'] - int(item['costTokens'] * 0.62),
                'totalTokens': item['costTokens'],
                'costUsd': item['costUsd'],
                'latencyMs': 900 + item['obstacleCount'] * 240,
                'statusCode': 200,
            }, org_headers)
            post(client, '/api/submissions', {
                'raceId': race['id'],
                'riderId': rider['id'],
                'content': message,
                'msgType': msg_type,
                'severity': 'warning' if msg_type == 'risk_alert' else 'info',
            }, con_headers)

        profile_path = Path(__file__).resolve().parent / 'fixtures' / 'track.profile.demo.json'
        track_profile = json.loads(profile_path.read_text(encoding='utf-8'))

        post(client, '/api/track-profiles', {
            'raceId': race['id'],
            'profile': track_profile,
        }, org_headers)

        snapshot = client.get(f"/api/jumbotron/snapshot?raceId={race['id']}").get_json()
        print(f"Seeded race: {race['id']}")
        print(f"Entries: {len(snapshot['entries'])}")
        print(f"Snapshot: /api/jumbotron/snapshot?raceId={race['id']}")


if __name__ == '__main__':
    main()
