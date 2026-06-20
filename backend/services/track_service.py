import json

from database import get_db
from daos import RaceDAO, TrackDAO
from utils import next_id, now
from utils.errors import NotFoundError, ValidationError


class TrackService:
    @staticmethod
    def upsert_track_profile(data):
        race_id = (data.get('raceId') or '').strip()
        profile = data.get('profile')
        if not race_id or profile is None:
            raise ValidationError('raceId and profile are required')

        conn = get_db()
        try:
            if not RaceDAO.get_by_id(conn, race_id):
                raise NotFoundError('Race')

            profile_json = json.dumps(profile, ensure_ascii=False, separators=(',', ':'))
            existing = TrackDAO.get_by_race(conn, race_id)
            ts = now()
            if existing:
                row = TrackDAO.update(conn, existing['id'], profile_json, ts)
            else:
                row = TrackDAO.create(
                    conn,
                    next_id(conn, 'track_profiles', 'tprof'),
                    race_id,
                    profile_json,
                    ts,
                )

            conn.commit()
            return {
                'id': row['id'],
                'raceId': row['race_id'],
                'createdAt': row['created_at'],
            }
        finally:
            conn.close()

    @staticmethod
    def get_track_profile(profile_or_race_id):
        conn = get_db()
        try:
            row = TrackDAO.get_by_id_or_race(conn, profile_or_race_id)
            if not row:
                raise NotFoundError('Track profile')
            return json.loads(row['profile_json'])
        finally:
            conn.close()
