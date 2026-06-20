from datetime import datetime, timezone

from utils import now, parse_utc


def race_to_dict(row):
    return {
        'id': row['id'],
        'title': row['title'],
        'description': row['description'],
        'startTime': row['start_time'],
        'endTime': row['end_time'],
        'status': row['status'],
        'theme': row['theme'] or '',
        'organizer': row['organizer'] or '',
        'currentRound': row['current_round'] or 1,
        'currentPhase': row['current_phase'] or 'DEV',
        'createdAt': row['created_at'],
        'updatedAt': row['updated_at'],
    }


def rider_to_dict(row):
    return {
        'id': row['id'],
        'name': row['name'],
        'createdAt': row['created_at'],
    }


def entry_to_dict(row, rank=None, rider_name=None, last_message=None):
    data = {
        'entryId': row['id'],
        'raceId': row['race_id'],
        'riderId': row['rider_id'],
        'riderName': rider_name,
        'projectName': row['project_name'] or '',
        'cockpitId': None,
        'caProvider': row['ca_provider'] or 'codex',
        'overallProgress': row['overall_progress'] or 0.0,
        'roundProgress': row['round_progress'] or 0.0,
        'phaseProgress': row['phase_progress'] or 0.0,
        'currentPhase': row['current_phase'] or 'DEV',
        'costTokens': row['cost_tokens'] or 0,
        'costUsd': row['cost_usd'] or 0.0,
        'riskLevel': row['risk_level'] or 'none',
        'obstacleCount': row['obstacle_count'] or 0,
        'violationCount': row['violation_count'] or 0,
        'laneId': row['lane_id'],
        'status': row['status'] or 'idle',
        'lastMessage': last_message,
        'updatedAt': row['updated_at'],
    }
    if rank is not None:
        data['rank'] = rank
    return data


def submission_to_dict(row):
    return {
        'id': row['id'],
        'raceId': row['race_id'],
        'riderId': row['rider_id'],
        'studentName': row['student_name'],
        'content': row['content_public_summary'] or row['content'],
        'contentProtected': True,
        'contentCommitment': row['content_commitment'],
        'protectionMode': row['content_protection'] or 'sealed_commitment_v1',
        'msgType': row['msg_type'] or 'progress_update',
        'severity': row['severity'] or 'info',
        'submittedAt': row['submitted_at'],
    }


def submission_to_message(row, entry_id=None, source=None):
    summary = row['content_public_summary'] or row['content'] or ''
    return {
        'messageId': row['id'],
        'entryId': entry_id,
        'source': source or row['student_name'],
        'type': row['msg_type'] or 'progress_update',
        'severity': row['severity'] or 'info',
        'summary': summary[:80],
        'contentProtected': True,
        'contentCommitment': row['content_commitment'],
        'createdAt': row['submitted_at'],
        'displayMode': 'bubble' if row['severity'] == 'critical' else 'ticker',
    }


def competition_from_race(row):
    start = parse_utc(row['start_time'])
    current = datetime.now(timezone.utc)
    elapsed = max(0, int((current - start).total_seconds())) if start else 0
    return {
        'competitionId': row['id'],
        'title': row['title'],
        'subtitle': (row['description'] or '')[:100],
        'theme': row['theme'] or '',
        'organizer': row['organizer'] or '',
        'liveStatus': row['status'],
        'currentPhase': row['current_phase'] or 'DEV',
        'currentRound': row['current_round'] or 1,
        'elapsedTime': elapsed,
        'systemTime': now(),
    }


def agent_usage_to_dict(row):
    return {
        'id': row['id'],
        'raceId': row['race_id'],
        'entryId': row['entry_id'],
        'riderId': row['rider_id'],
        'riderName': row['rider_name'] if 'rider_name' in row.keys() else None,
        'provider': row['provider'],
        'model': row['model'] or '',
        'apiEndpoint': row['api_endpoint'] or '',
        'promptTokens': row['prompt_tokens'] or 0,
        'completionTokens': row['completion_tokens'] or 0,
        'totalTokens': row['total_tokens'] or 0,
        'costUsd': row['cost_usd'] or 0.0,
        'latencyMs': row['latency_ms'] or 0,
        'statusCode': row['status_code'] or 0,
        'detectedAt': row['detected_at'],
    }
