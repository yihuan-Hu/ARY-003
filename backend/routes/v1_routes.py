from flask import Blueprint, jsonify, request

from services import (
    AgentUsageService,
    EntryService,
    RaceService,
    RiderService,
    StatsService,
    SubmissionService,
    TrackService,
)
from utils.auth import require_contestant, require_organizer
from utils.errors import ValidationError

organizer_v1_bp = Blueprint('organizer_v1', __name__, url_prefix='/api/v1/organizer')
contestant_v1_bp = Blueprint('contestant_v1', __name__, url_prefix='/api/v1/contestant')


def request_json():
    data = request.get_json(silent=True)
    if not data:
        raise ValidationError('Request body is required')
    return data


@organizer_v1_bp.route('/races', methods=['POST'])
@require_organizer
def organizer_create_race():
    return jsonify(RaceService.create_race(request_json())), 201


@organizer_v1_bp.route('/races/<race_id>', methods=['PUT'])
@require_organizer
def organizer_update_race(race_id):
    return jsonify(RaceService.update_race(race_id, request_json()))


@organizer_v1_bp.route('/riders', methods=['GET'])
@require_organizer
def organizer_list_riders():
    return jsonify(RiderService.list_riders())


@organizer_v1_bp.route('/riders', methods=['POST'])
@require_organizer
def organizer_create_rider():
    return jsonify(RiderService.create_rider(request_json())), 201


@organizer_v1_bp.route('/entries', methods=['GET'])
@require_organizer
def organizer_list_entries():
    race_id = (request.args.get('race') or request.args.get('raceId') or '').strip()
    return jsonify(EntryService.list_entries(race_id))


@organizer_v1_bp.route('/entries', methods=['POST'])
@require_organizer
def organizer_upsert_entry():
    payload, status_code = EntryService.upsert_entry(request_json())
    return jsonify(payload), status_code


@organizer_v1_bp.route('/track-profiles', methods=['POST'])
@require_organizer
def organizer_upsert_track_profile():
    return jsonify(TrackService.upsert_track_profile(request_json())), 201


@organizer_v1_bp.route('/stats', methods=['GET'])
@require_organizer
def organizer_stats():
    return jsonify(StatsService.get_stats())


@organizer_v1_bp.route('/agent-usage', methods=['GET'])
@require_organizer
def organizer_list_agent_usage():
    race_id = (request.args.get('race') or request.args.get('raceId') or '').strip()
    limit = request.args.get('limit', 100)
    return jsonify(AgentUsageService.list_usage(race_id, limit))


@organizer_v1_bp.route('/agent-usage', methods=['POST'])
@require_organizer
def organizer_record_agent_usage():
    payload, status_code = AgentUsageService.record_usage(request_json())
    return jsonify(payload), status_code


@contestant_v1_bp.route('/races', methods=['GET'])
def contestant_list_races():
    keyword = request.args.get('keyword', '').strip()
    status = request.args.get('status', '').strip()
    return jsonify(RaceService.list_races(keyword, status))


@contestant_v1_bp.route('/races/<race_id>', methods=['GET'])
def contestant_race_detail(race_id):
    return jsonify(RaceService.get_race_detail(race_id))


@contestant_v1_bp.route('/submissions', methods=['POST'])
@require_contestant
def contestant_create_submission():
    return jsonify(SubmissionService.upsert_submission(request_json())), 201


@contestant_v1_bp.route('/submissions/verify', methods=['POST'])
@require_contestant
def contestant_verify_submission():
    return jsonify(SubmissionService.verify_submission(request_json()))
