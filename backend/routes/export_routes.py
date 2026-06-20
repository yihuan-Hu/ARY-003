import csv
import io

from flask import Blueprint, Response

from database import get_db
from daos import RaceDAO, SubmissionDAO
from utils.auth import require_organizer

export_bp = Blueprint('exports', __name__, url_prefix='/api/export')

# Intentional architecture exception:
# CSV export is a thin streaming adapter, so it reads DAO rows directly instead
# of adding a pass-through ExportService. Add a service if export permissions,
# field selection, or transformations become non-trivial.

@export_bp.route('/races', methods=['GET'])
@require_organizer
def export_races():
    conn = get_db()
    try:
        rows = RaceDAO.list_for_export(conn)
    finally:
        conn.close()

    out = io.StringIO()
    out.write('\ufeff')
    writer = csv.writer(out)
    writer.writerow([
        'id', 'title', 'description', 'startTime', 'endTime', 'status',
        'theme', 'organizer', 'currentRound', 'currentPhase',
        'createdAt', 'updatedAt',
    ])
    for row in rows:
        writer.writerow([
            row['id'], row['title'], row['description'], row['start_time'],
            row['end_time'], row['status'], row['theme'], row['organizer'],
            row['current_round'], row['current_phase'],
            row['created_at'], row['updated_at'],
        ])

    return Response(
        out.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename=races.csv'},
    )


@export_bp.route('/submissions', methods=['GET'])
@require_organizer
def export_submissions():
    conn = get_db()
    try:
        rows = SubmissionDAO.list_for_export(conn)
    finally:
        conn.close()

    out = io.StringIO()
    out.write('\ufeff')
    writer = csv.writer(out)
    writer.writerow([
        'id', 'raceId', 'raceTitle', 'riderId', 'studentName',
        'content', 'publicSummary', 'contentCommitment', 'protectionMode',
        'msgType', 'severity', 'submittedAt',
    ])
    for row in rows:
        writer.writerow([
            row['id'], row['race_id'], row['race_title'], row['rider_id'],
            row['student_name'], row['content'], row['content'],
            row['content_commitment'], row['content_protection'], row['msg_type'],
            row['severity'], row['submitted_at'],
        ])

    return Response(
        out.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename=submissions.csv'},
    )
