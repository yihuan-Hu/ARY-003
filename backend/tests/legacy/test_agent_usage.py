def test_record_agent_usage_requires_organizer(client, race, rider):
    response = client.post('/api/agent-usage', json={
        'raceId': race['id'],
        'riderId': rider['id'],
        'provider': 'codex',
        'totalTokens': 1200,
    })

    assert response.status_code == 401


def test_agent_usage_is_recorded_and_visible_in_snapshot(client, race, rider, organizer_headers):
    entry_response = client.post('/api/entries', json={
        'raceId': race['id'],
        'riderId': rider['id'],
        'projectName': 'API Meter',
        'roundProgress': 0.55,
        'overallProgress': 0.6,
        'status': 'running',
        'laneId': 'lane_1',
    }, headers=organizer_headers)
    assert entry_response.status_code == 201
    entry = entry_response.get_json()

    usage_response = client.post('/api/agent-usage', json={
        'raceId': race['id'],
        'entryId': entry['entryId'],
        'provider': 'codex',
        'model': 'gpt-5-codex',
        'apiEndpoint': '/v1/responses',
        'promptTokens': 800,
        'completionTokens': 400,
        'totalTokens': 1200,
        'costUsd': 0.42,
        'latencyMs': 950,
        'statusCode': 200,
    }, headers=organizer_headers)

    assert usage_response.status_code == 201
    usage = usage_response.get_json()
    assert usage['provider'] == 'codex'
    assert usage['totalTokens'] == 1200

    list_response = client.get(
        f"/api/agent-usage?race={race['id']}",
        headers=organizer_headers,
    )
    assert list_response.status_code == 200
    assert list_response.get_json()[0]['model'] == 'gpt-5-codex'

    snapshot = client.get(f"/api/jumbotron/snapshot?raceId={race['id']}").get_json()
    assert snapshot['kpi']['apiDetected'] is True
    assert snapshot['kpi']['apiCallCount'] == 1
    assert snapshot['kpi']['codexTokens'] == 1200
    assert snapshot['agentUsage']['totalCalls'] == 1
    assert snapshot['agentUsage']['providers'][0]['provider'] == 'codex'
    assert snapshot['recentApiCalls'][0]['apiEndpoint'] == '/v1/responses'
