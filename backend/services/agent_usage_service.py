from database import get_db
from daos import AgentUsageDAO, EntryDAO, RaceDAO, RiderDAO
from utils import as_float, as_int, next_id, now
from utils.errors import NotFoundError, ValidationError

from .constants import CA_PROVIDERS
from .serializers import agent_usage_to_dict


class AgentUsageService:
    @staticmethod
    def record_usage(data):
        race_id = (data.get('raceId') or '').strip()
        provider = (data.get('provider') or '').strip().lower()
        if not race_id:
            raise ValidationError('raceId is required')
        if provider not in CA_PROVIDERS:
            raise ValidationError('provider must be codex | claude | other')

        prompt_tokens = as_int(data.get('promptTokens'), 0)
        completion_tokens = as_int(data.get('completionTokens'), 0)
        total_tokens = as_int(data.get('totalTokens'), prompt_tokens + completion_tokens)
        if total_tokens < 0 or prompt_tokens < 0 or completion_tokens < 0:
            raise ValidationError('token counts must be non-negative')

        conn = get_db()
        try:
            if not RaceDAO.get_by_id(conn, race_id):
                raise NotFoundError('Race')

            entry_id = (data.get('entryId') or '').strip() or None
            rider_id = (data.get('riderId') or '').strip() or None

            if entry_id:
                entry = EntryDAO.get_by_id(conn, entry_id)
                if not entry or entry['race_id'] != race_id:
                    raise NotFoundError('Entry')
                rider_id = rider_id or entry['rider_id']

            if rider_id and not RiderDAO.get_by_id(conn, rider_id):
                raise NotFoundError('Rider')

            values = {
                'id': next_id(conn, 'agent_api_usage', 'usage'),
                'race_id': race_id,
                'entry_id': entry_id,
                'rider_id': rider_id,
                'provider': provider,
                'model': (data.get('model') or '').strip(),
                'api_endpoint': (data.get('apiEndpoint') or '').strip(),
                'prompt_tokens': prompt_tokens,
                'completion_tokens': completion_tokens,
                'total_tokens': total_tokens,
                'cost_usd': as_float(data.get('costUsd'), 0.0),
                'latency_ms': as_int(data.get('latencyMs'), 0),
                'status_code': as_int(data.get('statusCode'), 200),
                'detected_at': data.get('detectedAt') or now(),
            }
            row = AgentUsageDAO.create(conn, values)
            conn.commit()
            return agent_usage_to_dict(row), 201
        finally:
            conn.close()

    @staticmethod
    def list_usage(race_id, limit=100):
        if not race_id:
            raise ValidationError('race query parameter is required')
        limit = max(1, min(as_int(limit, 100), 500))
        conn = get_db()
        try:
            if not RaceDAO.get_by_id(conn, race_id):
                raise NotFoundError('Race')
            return [
                agent_usage_to_dict(row)
                for row in AgentUsageDAO.list_by_race(conn, race_id, limit)
            ]
        finally:
            conn.close()

    @staticmethod
    def summarize(conn, race_id, recent_limit=10):
        total = AgentUsageDAO.total_by_race(conn, race_id)
        provider_rows = AgentUsageDAO.provider_totals(conn, race_id)
        model_rows = AgentUsageDAO.model_totals(conn, race_id)
        models_by_provider = {}
        for row in model_rows:
            models_by_provider.setdefault(row['provider'], []).append({
                'model': row['model'] or '',
                'callCount': row['call_count'] or 0,
                'totalTokens': row['total_tokens'] or 0,
                'costUsd': round(row['cost_usd'] or 0.0, 4),
            })

        total_tokens = total['total_tokens'] or 0
        providers = []
        for row in provider_rows:
            tokens = row['total_tokens'] or 0
            providers.append({
                'provider': row['provider'],
                'callCount': row['call_count'] or 0,
                'promptTokens': row['prompt_tokens'] or 0,
                'completionTokens': row['completion_tokens'] or 0,
                'totalTokens': tokens,
                'costUsd': round(row['cost_usd'] or 0.0, 4),
                'avgLatencyMs': round(row['avg_latency_ms'] or 0),
                'errorCount': row['error_count'] or 0,
                'share': round(tokens / total_tokens, 2) if total_tokens else 0,
                'lastDetectedAt': row['last_detected_at'],
                'models': models_by_provider.get(row['provider'], []),
            })

        return {
            'apiDetected': bool(total['call_count'] or 0),
            'totalCalls': total['call_count'] or 0,
            'totalTokens': total_tokens,
            'totalCostUsd': round(total['cost_usd'] or 0.0, 4),
            'lastDetectedAt': total['last_detected_at'],
            'providers': providers,
            'recentApiCalls': [
                agent_usage_to_dict(row)
                for row in AgentUsageDAO.list_by_race(conn, race_id, recent_limit)
            ],
        }
