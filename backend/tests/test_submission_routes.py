def test_create_submission_by_rider(client, race, rider, contestant_headers):
    response = client.post('/api/submissions', json={
        'raceId': race['id'],
        'riderId': rider['id'],
        'content': 'Milestone reached.',
        'msgType': 'milestone',
        'severity': 'info',
    }, headers=contestant_headers)

    assert response.status_code == 201
    data = response.get_json()
    assert data['riderId'] == rider['id']
    assert data['studentName'] == rider['name']
    assert data['msgType'] == 'milestone'
    assert data['contentProtected'] is True
    assert data['content'] == '[protected submission]'
    assert data['contentCommitment']


def test_submission_verify_commitment(client, race, rider, contestant_headers):
    response = client.post('/api/submissions', json={
        'raceId': race['id'],
        'riderId': rider['id'],
        'content': 'private code payload',
        'publicSummary': 'sealed',
    }, headers=contestant_headers)
    submission_id = response.get_json()['id']

    verify = client.post('/api/submissions/verify', json={
        'submissionId': submission_id,
        'content': 'private code payload',
    }, headers=contestant_headers)
    wrong = client.post('/api/submissions/verify', json={
        'submissionId': submission_id,
        'content': 'other payload',
    }, headers=contestant_headers)

    assert verify.status_code == 200
    assert verify.get_json()['matched'] is True
    assert wrong.status_code == 200
    assert wrong.get_json()['matched'] is False


def test_submission_private_content_is_not_stored_in_plaintext(client, race, rider, contestant_headers):
    private_content = 'super secret source code'
    response = client.post('/api/submissions', json={
        'raceId': race['id'],
        'riderId': rider['id'],
        'content': private_content,
    }, headers=contestant_headers)
    submission_id = response.get_json()['id']

    from database import get_db

    conn = get_db()
    try:
        row = conn.execute(
            'SELECT content, content_commitment FROM submissions WHERE id = ?',
            (submission_id,),
        ).fetchone()
    finally:
        conn.close()

    assert row['content'] != private_content
    assert row['content'] == '[protected submission]'
    assert row['content_commitment']


def test_duplicate_submission_is_rejected(client, race, rider, contestant_headers):
    payload = {
        'raceId': race['id'],
        'riderId': rider['id'],
        'content': 'first private payload',
    }

    first = client.post('/api/submissions', json=payload, headers=contestant_headers)
    second = client.post('/api/submissions', json={
        **payload,
        'content': 'attempted replacement',
    }, headers=contestant_headers)

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.get_json()['error'] == 'Submission already exists and cannot be modified'


def test_submission_update_is_blocked_at_database_layer(client, race, rider, contestant_headers):
    response = client.post('/api/submissions', json={
        'raceId': race['id'],
        'riderId': rider['id'],
        'content': 'immutable private payload',
    }, headers=contestant_headers)
    submission_id = response.get_json()['id']

    from database import get_db

    conn = get_db()
    try:
        try:
            conn.execute(
                'UPDATE submissions SET content = ? WHERE id = ?',
                ('tampered', submission_id),
            )
            conn.commit()
            blocked = False
        except Exception as exc:
            blocked = 'immutable' in str(exc)
    finally:
        conn.close()

    assert blocked is True


def test_submission_export_keeps_content_column_without_private_content(
    client, race, rider, contestant_headers, organizer_headers
):
    private_content = 'private export payload'
    client.post('/api/submissions', json={
        'raceId': race['id'],
        'riderId': rider['id'],
        'content': private_content,
    }, headers=contestant_headers)

    response = client.get('/api/export/submissions', headers=organizer_headers)
    csv_text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'content,publicSummary,contentCommitment,protectionMode' in csv_text
    assert private_content not in csv_text
    assert '[protected submission]' in csv_text
