from flask import Blueprint, jsonify, request

from services import RaceService
from utils.auth import require_organizer
from utils.errors import ValidationError

race_bp = Blueprint('races', __name__, url_prefix='/api/races')


def request_json():
    data = request.get_json(silent=True)
    if not data:
        raise ValidationError('Request body is required')
    return data


@race_bp.route('', methods=['GET'])
def list_races():
    keyword = request.args.get('keyword', '').strip()
    status = request.args.get('status', '').strip()
    return jsonify(RaceService.list_races(keyword, status))


@race_bp.route('', methods=['POST'])
@require_organizer
def create_race():
    return jsonify(RaceService.create_race(request_json())), 201


@race_bp.route('/<race_id>', methods=['GET'])
def race_detail(race_id):
    return jsonify(RaceService.get_race_detail(race_id))


@race_bp.route('/<race_id>', methods=['PUT'])
@require_organizer
def update_race(race_id):
    return jsonify(RaceService.update_race(race_id, request_json()))


@race_bp.route('/<race_id>/submissions', methods=['GET'])
def race_submissions(race_id):
    return jsonify(RaceService.race_submissions(race_id))
