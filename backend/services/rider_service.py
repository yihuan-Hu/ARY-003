from database import get_db
from daos import RiderDAO
from utils import next_id, now
from utils.errors import ConflictError, ValidationError

from .serializers import rider_to_dict


class RiderService:
    @staticmethod
    def list_riders():
        conn = get_db()
        try:
            return [rider_to_dict(row) for row in RiderDAO.list_all(conn)]
        finally:
            conn.close()

    @staticmethod
    def create_rider(data):
        name = (data.get('name') or '').strip()
        if not name:
            raise ValidationError('name is required')

        conn = get_db()
        try:
            rider_id = (data.get('id') or '').strip() or next_id(conn, 'riders', 'rider')
            if RiderDAO.get_by_id(conn, rider_id):
                raise ConflictError('Rider already exists')
            row = RiderDAO.create(conn, rider_id, name, now())
            conn.commit()
            return rider_to_dict(row)
        finally:
            conn.close()
