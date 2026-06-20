from flask import Blueprint, jsonify, request

from services import AgentUsageService
from utils.auth import require_organizer
from utils.errors import ValidationError

agent_usage_bp = Blueprint('agent_usage', __name__, url_prefix='/api/agent-usage')


@agent_usage_bp.route('', methods=['GET'])
@require_organizer
def list_agent_usage():
    race_id = (request.args.get('race') or request.args.get('raceId') or '').strip()
    limit = request.args.get('limit', 100)
    return jsonify(AgentUsageService.list_usage(race_id, limit))


@agent_usage_bp.route('', methods=['POST'])
@require_organizer
def record_agent_usage():
    data = request.get_json(silent=True)
    if not data:
        raise ValidationError('Request body is required')
    payload, status_code = AgentUsageService.record_usage(data)
    return jsonify(payload), status_code
