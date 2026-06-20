def test_jumbotron_snapshot(client, race, rider, organizer_headers, contestant_headers):
    client.post('/api/entries', json={
        'raceId': race['id'],
        'riderId': rider['id'],
        'projectName': 'Live View',
        'roundProgress': 0.72,
        'overallProgress': 0.8,
        'phaseProgress': 0.9,
        'status': 'running',
        'riskLevel': 'low',
        'laneId': 'lane_1',
        'costTokens': 1000,
    }, headers=organizer_headers)
    client.post('/api/submissions', json={
        'raceId': race['id'],
        'riderId': rider['id'],
        'content': 'Milestone reached.',
        'msgType': 'milestone',
        'severity': 'info',
    }, headers=contestant_headers)
    client.post('/api/track-profiles', json={
        'raceId': race['id'],
        'profile': {'schemaVersion': '1.0', 'trackId': 'track_001'},
    }, headers=organizer_headers)

    response = client.get(f"/api/jumbotron/snapshot?raceId={race['id']}")

    assert response.status_code == 200
    data = response.get_json()
    assert data['competition']['competitionId'] == race['id']
    assert data['entries'][0]['lastMessage']['type'] == 'milestone'
    assert data['kpi']['totalTokens'] == 1000
    assert data['kpi']['apiDetected'] is False
    assert data['agentUsage']['totalCalls'] == 0
    assert data['recentApiCalls'] == []
    assert data['trackProfile']['trackId'] == 'track_001'
