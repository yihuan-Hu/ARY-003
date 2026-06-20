from database import get_db
from daos import RaceDAO, RiderDAO, SubmissionDAO
from utils import next_id, now
from utils.content_security import protect_content, verify_content
from utils.errors import ConflictError, NotFoundError, ValidationError

from .constants import MESSAGE_TYPES, SEVERITIES
from .serializers import submission_to_dict


class SubmissionService:
    @staticmethod
    def upsert_submission(data):
        race_id = (data.get('raceId') or '').strip()
        rider_id = (data.get('riderId') or '').strip() or None
        student_name = (data.get('studentName') or '').strip()
        content = (data.get('content') or '').strip()
        summary = data.get('publicSummary')
        msg_type = (data.get('msgType') or 'progress_update').strip()
        severity = (data.get('severity') or 'info').strip()

        if not race_id or not content or (not student_name and not rider_id):
            raise ValidationError('raceId, content, and studentName or riderId are required')
        if msg_type not in MESSAGE_TYPES:
            raise ValidationError('msgType is invalid')
        if severity not in SEVERITIES:
            raise ValidationError('severity must be info | warning | critical')

        conn = get_db()
        try:
            if not RaceDAO.get_by_id(conn, race_id):
                raise NotFoundError('Race')
            if rider_id:
                rider = RiderDAO.get_by_id(conn, rider_id)
                if not rider:
                    raise NotFoundError('Rider')
                if not student_name:
                    student_name = rider['name']

            ts = now()
            protected = protect_content(content, summary)
            values = {
                'race_id': race_id,
                'rider_id': rider_id,
                'student_name': student_name,
                **protected,
                'msg_type': msg_type,
                'severity': severity,
                'submitted_at': ts,
            }
            existing = SubmissionDAO.get_by_race_student(conn, race_id, student_name)
            if existing:
                raise ConflictError('Submission already exists and cannot be modified')

            values['id'] = next_id(conn, 'submissions', 'sub')
            row = SubmissionDAO.create(conn, values)
            conn.commit()
            return submission_to_dict(row)
        finally:
            conn.close()

    @staticmethod
    def verify_submission(data):
        submission_id = (data.get('submissionId') or '').strip()
        content = (data.get('content') or '').strip()
        if not submission_id or not content:
            raise ValidationError('submissionId and content are required')

        conn = get_db()
        try:
            row = SubmissionDAO.get_by_id(conn, submission_id)
            if not row:
                raise NotFoundError('Submission')
            return {
                'submissionId': row['id'],
                'matched': verify_content(content, row['content_commitment']),
                'contentCommitment': row['content_commitment'],
                'protectionMode': row['content_protection'],
            }
        finally:
            conn.close()
