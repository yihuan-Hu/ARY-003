from flask import Blueprint, jsonify, request

from services import EntryService
from utils.auth import require_organizer
from utils.errors import ValidationError

entry_bp = Blueprint('entries', __name__, url_prefix='/api/entries')


@entry_bp.route('', methods=['GET'])
@require_organizer
def list_entries():
    race_id = (request.args.get('race') or request.args.get('raceId') or '').strip()
    return jsonify(EntryService.list_entries(race_id))


@entry_bp.route('', methods=['POST'])
@require_organizer
def upsert_entry():
    data = request.get_json(silent=True)
    if not data:
        raise ValidationError('Request body is required')
    payload, status_code = EntryService.upsert_entry(data)
    return jsonify(payload), status_code
