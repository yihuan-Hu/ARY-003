from flask import Blueprint, request

from app.dao.race_dao import RaceDAO
from app.dao.work_dao import WorkDAO
from app.dao.announcement_dao import AnnouncementDAO
from app.database import get_db
from app.services.integrity_service import verify_resource_integrity
from app.utils.errors import NotFoundError, ValidationError
from app.utils.response import success


public_bp = Blueprint("public", __name__)
race_dao = RaceDAO()
work_dao = WorkDAO()
announcement_dao = AnnouncementDAO()

PUBLIC_STATUSES = {
    "published",
    "registration",
    "running",
    "submitting",
    "judging",
    "completed",
    "archived",
}


def _pagination_args():
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(100, max(1, int(request.args.get("per_page", 20))))
    except ValueError as error:
        raise ValidationError("page and per_page must be integers") from error
    return page, per_page


@public_bp.route("/api/v1/public/races", methods=["GET"])
def list_races():
    page, per_page = _pagination_args()
    status = request.args.get("status")
    if status and status not in PUBLIC_STATUSES:
        raise ValidationError("Invalid public race status filter")
    query = (request.args.get("q") or "").strip()

    clauses = ["status != 'draft'"]
    values: list = []
    if status:
        clauses.append("status = ?")
        values.append(status)
    if query:
        clauses.append("name LIKE ?")
        values.append(f"%{query}%")
    where = " AND ".join(clauses)
    db = get_db()
    total = db.execute(
        f"SELECT COUNT(*) AS count FROM races WHERE {where}", tuple(values)
    ).fetchone()["count"]
    rows = db.execute(
        f"""SELECT * FROM races WHERE {where}
            ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?""",
        tuple(values) + (per_page, (page - 1) * per_page),
    ).fetchall()
    return success({
        "items": [dict(row) for row in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
    })


@public_bp.route("/api/v1/public/races/<int:race_id>", methods=["GET"])
def get_race(race_id):
    race = race_dao.find_by_id(race_id)
    if race is None or race["status"] == "draft":
        raise NotFoundError("Race not found")
    db = get_db()
    participant_count = db.execute(
        """SELECT COUNT(*) AS count FROM registrations
           WHERE race_id = ? AND status = 'approved'""",
        (race_id,),
    ).fetchone()["count"]
    public_work_count = db.execute(
        """SELECT COUNT(*) AS count FROM works w
           JOIN race_projects rp ON w.race_project_id = rp.id
           JOIN registrations reg ON rp.registration_id = reg.id
           WHERE reg.race_id = ? AND w.work_status = 'submitted'
             AND w.visibility = 'public' AND w.disqualified = 0""",
        (race_id,),
    ).fetchone()["count"]
    result = dict(race)
    result.update({
        "participant_count": participant_count,
        "public_work_count": public_work_count,
    })
    return success(result)


@public_bp.route("/api/v1/public/races/<int:race_id>/works", methods=["GET"])
def list_race_works(race_id):
    race = race_dao.find_by_id(race_id)
    if race is None or race["status"] == "draft":
        raise NotFoundError("Race not found")
    return success(work_dao.find_public_by_race(race_id))


@public_bp.route("/api/v1/public/stats", methods=["GET"])
def stats():
    db = get_db()
    total_races = db.execute(
        "SELECT COUNT(*) AS count FROM races WHERE status != 'draft'"
    ).fetchone()["count"]
    active_races = db.execute(
        """SELECT COUNT(*) AS count FROM races
           WHERE status NOT IN ('draft', 'completed', 'archived')"""
    ).fetchone()["count"]
    total_riders = db.execute(
        """SELECT COUNT(DISTINCT user_id) AS count FROM registrations
           WHERE status = 'approved'"""
    ).fetchone()["count"]
    total_works = db.execute(
        """SELECT COUNT(*) AS count FROM works
           WHERE work_status = 'submitted' AND disqualified = 0"""
    ).fetchone()["count"]
    return success({
        "total_races": total_races,
        "active_races": active_races,
        "total_riders": total_riders,
        "total_works": total_works,
    })


@public_bp.route("/api/v1/public/works/<int:work_id>/integrity", methods=["GET"])
def work_integrity(work_id):
    if work_dao.find_by_id(work_id) is None:
        raise NotFoundError("Work not found")
    return success(verify_resource_integrity("work", work_id, verify_commitments=False))


@public_bp.route(
    "/api/v1/public/races/<int:race_id>/announcements", methods=["GET"]
)
def list_announcements(race_id):
    race = race_dao.find_by_id(race_id)
    if race is None or race["status"] == "draft":
        raise NotFoundError("Race not found")
    return success(announcement_dao.find_by_race(race_id, "public"))
