import json

from database import get_db
from daos import EntryDAO, RaceDAO, SubmissionDAO, TrackDAO
from utils.errors import NotFoundError, ValidationError

from .serializers import competition_from_race, entry_to_dict, submission_to_message
from .agent_usage_service import AgentUsageService


class JumbotronService:
    @staticmethod
    def snapshot(race_id):
        if not race_id:
            raise ValidationError('raceId query parameter is required')

        conn = get_db()
        try:
            race = RaceDAO.get_by_id(conn, race_id)
            if not race:
                raise NotFoundError('Race')

            entries = []
            for index, entry in enumerate(EntryDAO.list_by_race(conn, race_id)):
                last_msg = SubmissionDAO.latest_for_entry(
                    conn, race_id, entry['rider_id'], entry['rider_name']
                )
                message = (
                    submission_to_message(last_msg, entry['id'], entry['rider_name'])
                    if last_msg else None
                )
                entries.append(entry_to_dict(
                    entry,
                    rank=index + 1,
                    rider_name=entry['rider_name'],
                    last_message=message,
                ))

            profile = TrackDAO.get_by_race(conn, race_id)
            agent_usage = AgentUsageService.summarize(conn, race_id)
            return {
                'competition': competition_from_race(race),
                'entries': entries,
                'kpi': JumbotronService._compute_kpi(conn, race_id, agent_usage),
                'messages': [
                    submission_to_message(row, row['entry_id'], row['source_name'])
                    for row in SubmissionDAO.recent_messages(conn, race_id)
                ],
                'agentUsage': agent_usage,
                'recentApiCalls': agent_usage['recentApiCalls'],
                'trackProfile': json.loads(profile['profile_json']) if profile else None,
            }
        finally:
            conn.close()

    @staticmethod
    def _compute_kpi(conn, race_id, agent_usage=None):
        row = EntryDAO.kpi_by_race(conn, race_id)
        active_cockpits = RaceDAO.count_open(conn)
        if agent_usage and agent_usage['apiDetected']:
            total_tokens = agent_usage['totalTokens']
            by_provider = {
                provider['provider']: provider['totalTokens']
                for provider in agent_usage['providers']
            }
            codex_tokens = by_provider.get('codex', 0)
            claude_tokens = by_provider.get('claude', 0)
        else:
            total_tokens = row['total_tokens'] or 0
            codex_tokens = row['codex_tokens'] or 0
            claude_tokens = row['claude_tokens'] or 0
        return {
            'completionRate': round(row['completion_rate'] or 0, 2),
            'totalTokens': total_tokens,
            'apiCallCount': agent_usage['totalCalls'] if agent_usage else 0,
            'apiDetected': bool(agent_usage and agent_usage['apiDetected']),
            'apiLastDetectedAt': agent_usage['lastDetectedAt'] if agent_usage else None,
            'activeRiders': row['active_riders'] or 0,
            'onlineRiders': row['online_riders'] or 0,
            'activeCockpits': active_cockpits,
            'codexTokens': codex_tokens,
            'claudeTokens': claude_tokens,
            'codexShare': round(codex_tokens / total_tokens, 2) if total_tokens else 0,
            'claudeShare': round(claude_tokens / total_tokens, 2) if total_tokens else 0,
            'riskCount': row['risk_count'] or 0,
            'obstacleCount': row['obstacle_count'] or 0,
            'violationCount': row['violation_count'] or 0,
        }
