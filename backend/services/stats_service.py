from database import get_db
from daos import RaceDAO, SubmissionDAO


class StatsService:
    @staticmethod
    def get_stats():
        conn = get_db()
        try:
            return {
                'raceCount': RaceDAO.count(conn),
                'submissionCount': SubmissionDAO.count(conn),
                'studentCount': SubmissionDAO.distinct_student_count(conn),
                'submissionsByRace': [{
                    'raceId': row['raceId'],
                    'title': row['title'],
                    'submissionCount': row['submissionCount'],
                } for row in RaceDAO.submissions_by_race(conn)],
            }
        finally:
            conn.close()
