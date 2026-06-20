from database import get_db
from daos import EntryDAO, RaceDAO, RiderDAO
from utils import as_float, as_int, clamp, next_id, now
from utils.errors import NotFoundError, ValidationError

from .constants import CA_PROVIDERS, ENTRY_STATUSES, RISK_LEVELS
from .serializers import entry_to_dict


class EntryService:
    @staticmethod
    def list_entries(race_id):
        if not race_id:
            raise ValidationError('race query parameter is required')
        conn = get_db()
        try:
            if not RaceDAO.get_by_id(conn, race_id):
                raise NotFoundError('Race')
            return [
                entry_to_dict(row, rank=index + 1, rider_name=row['rider_name'])
                for index, row in enumerate(EntryDAO.list_by_race(conn, race_id))
            ]
        finally:
            conn.close()

    @staticmethod
    def upsert_entry(data):
        race_id = (data.get('raceId') or '').strip()
        rider_id = (data.get('riderId') or '').strip()
        if not race_id or not rider_id:
            raise ValidationError('raceId and riderId are required')

        ca_provider = (data.get('caProvider') or 'codex').strip()
        risk_level = (data.get('riskLevel') or 'none').strip()
        status = (data.get('status') or 'idle').strip()
        if ca_provider not in CA_PROVIDERS:
            raise ValidationError('caProvider must be codex | claude | other')
        if risk_level not in RISK_LEVELS:
            raise ValidationError('riskLevel must be none | low | medium | high')
        if status not in ENTRY_STATUSES:
            raise ValidationError('status is invalid')

        conn = get_db()
        try:
            race = RaceDAO.get_by_id(conn, race_id)
            if not race:
                raise NotFoundError('Race')
            if not RiderDAO.get_by_id(conn, rider_id):
                raise NotFoundError('Rider')

            existing = EntryDAO.get_by_race_rider(conn, race_id, rider_id)
            values = EntryService._entry_values(data, race, ca_provider, risk_level, status)
            values['race_id'] = race_id
            values['rider_id'] = rider_id
            values['updated_at'] = now()

            if existing:
                EntryService._preserve_missing_fields(data, values, existing)
                row = EntryDAO.update(conn, existing['id'], values)
                status_code = 200
            else:
                values['id'] = next_id(conn, 'racing_entries', 'entry')
                row = EntryDAO.create(conn, values)
                status_code = 201

            conn.commit()
            return entry_to_dict(row, rider_name=row['rider_name']), status_code
        finally:
            conn.close()

    @staticmethod
    def _entry_values(data, race, ca_provider, risk_level, status):
        return {
            'project_name': data.get('projectName') or '',
            'ca_provider': ca_provider,
            'overall_progress': clamp(data.get('overallProgress')),
            'round_progress': clamp(data.get('roundProgress')),
            'phase_progress': clamp(data.get('phaseProgress')),
            'current_phase': data.get('currentPhase') or race['current_phase'] or 'DEV',
            'cost_tokens': as_int(data.get('costTokens'), 0),
            'cost_usd': as_float(data.get('costUsd'), 0.0),
            'risk_level': risk_level,
            'obstacle_count': as_int(data.get('obstacleCount'), 0),
            'violation_count': as_int(data.get('violationCount'), 0),
            'lane_id': data.get('laneId'),
            'status': status,
        }

    @staticmethod
    def _preserve_missing_fields(data, values, existing):
        for api_key, db_key in (
            ('projectName', 'project_name'),
            ('caProvider', 'ca_provider'),
            ('overallProgress', 'overall_progress'),
            ('roundProgress', 'round_progress'),
            ('phaseProgress', 'phase_progress'),
            ('currentPhase', 'current_phase'),
            ('costTokens', 'cost_tokens'),
            ('costUsd', 'cost_usd'),
            ('riskLevel', 'risk_level'),
            ('obstacleCount', 'obstacle_count'),
            ('violationCount', 'violation_count'),
            ('laneId', 'lane_id'),
            ('status', 'status'),
        ):
            if api_key not in data:
                values[db_key] = existing[db_key]
