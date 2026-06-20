from flask import Blueprint, jsonify, request

from services import TrackService
from utils.auth import require_organizer
from utils.errors import ValidationError

track_bp = Blueprint('track_profiles', __name__, url_prefix='/api/track-profiles')


@track_bp.route('', methods=['POST'])
@require_organizer
def upsert_track_profile():
    data = request.get_json(silent=True)
    if not data:
        raise ValidationError('Request body is required')
    return jsonify(TrackService.upsert_track_profile(data)), 201


@track_bp.route('/<profile_or_race_id>', methods=['GET'])
def get_track_profile(profile_or_race_id):
    return jsonify(TrackService.get_track_profile(profile_or_race_id))
