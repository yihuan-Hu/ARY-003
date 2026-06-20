def test_entry_create_and_list(client, race, rider, organizer_headers):
    create = client.post('/api/entries', json={
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
    listed = client.get(f"/api/entries?race={race['id']}", headers=organizer_headers)

    assert create.status_code == 201
    assert listed.status_code == 200
    assert listed.get_json()[0]['entryId'] == create.get_json()['entryId']
    assert listed.get_json()[0]['rank'] == 1
