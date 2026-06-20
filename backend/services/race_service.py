from database import get_db
from daos import RaceDAO, SubmissionDAO
from utils import as_int, next_id, now
from utils.errors import NotFoundError, ValidationError

from .constants import RACE_STATUSES
from .serializers import race_to_dict, submission_to_dict


class RaceService:
    @staticmethod
    def list_races(keyword='', status=''):
        conn = get_db()
        try:
            rows = RaceDAO.list_all(conn, keyword, status)
            return [race_to_dict(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def create_race(data):
        title = (data.get('title') or '').strip()
        description = (data.get('description') or '').strip()
        start_time = (data.get('startTime') or '').strip()
        end_time = (data.get('endTime') or '').strip()
        status = (data.get('status') or 'upcoming').strip()

        if not title or not description or not start_time or not end_time:
            raise ValidationError('title, description, startTime, endTime are required')
        if status not in RACE_STATUSES:
            raise ValidationError('status must be upcoming | open | judging | ended')

        conn = get_db()
        try:
            ts = now()
            row = RaceDAO.create(conn, {
                'id': next_id(conn, 'races', 'race'),
                'title': title,
                'description': description,
                'start_time': start_time,
                'end_time': end_time,
                'status': status,
                'theme': (data.get('theme') or '').strip(),
                'organizer': (data.get('organizer') or '').strip(),
                'current_round': as_int(data.get('currentRound'), 1),
                'current_phase': (data.get('currentPhase') or 'DEV').strip(),
                'created_at': ts,
                'updated_at': ts,
            })
            conn.commit()
            return race_to_dict(row)
        finally:
            conn.close()

    @staticmethod
    def get_race_detail(race_id):
        conn = get_db()
        try:
            race = RaceDAO.get_by_id(conn, race_id)
            if not race:
                raise NotFoundError('Race')
            result = race_to_dict(race)
            result['submissions'] = [
                submission_to_dict(row)
                for row in SubmissionDAO.list_by_race(conn, race_id)
            ]
            return result
        finally:
            conn.close()

    @staticmethod
    def update_race(race_id, data):
        conn = get_db()
        try:
            race = RaceDAO.get_by_id(conn, race_id)
            if not race:
                raise NotFoundError('Race')

            status = data.get('status', race['status'])
            if status not in RACE_STATUSES:
                raise ValidationError('status must be upcoming | open | judging | ended')

            row = RaceDAO.update(conn, race_id, {
                'title': data.get('title', race['title']),
                'description': data.get('description', race['description']),
                'start_time': data.get('startTime', race['start_time']),
                'end_time': data.get('endTime', race['end_time']),
                'status': status,
                'theme': data.get('theme', race['theme']),
                'organizer': data.get('organizer', race['organizer']),
                'current_round': as_int(data.get('currentRound', race['current_round']), 1),
                'current_phase': data.get('currentPhase', race['current_phase']),
                'updated_at': now(),
            })
            conn.commit()
            return race_to_dict(row)
        finally:
            conn.close()

    @staticmethod
    def race_submissions(race_id):
        conn = get_db()
        try:
            if not RaceDAO.get_by_id(conn, race_id):
                raise NotFoundError('Race')
            return [submission_to_dict(row) for row in SubmissionDAO.list_by_race(conn, race_id)]
        finally:
            conn.close()
