from flask import Blueprint, jsonify, request

from services import RiderService
from utils.auth import require_organizer
from utils.errors import ValidationError

rider_bp = Blueprint('riders', __name__, url_prefix='/api/riders')


@rider_bp.route('', methods=['GET'])
@require_organizer
def list_riders():
    return jsonify(RiderService.list_riders())


@rider_bp.route('', methods=['POST'])
@require_organizer
def create_rider():
    data = request.get_json(silent=True)
    if not data:
        raise ValidationError('Request body is required')
    return jsonify(RiderService.create_rider(data)), 201
