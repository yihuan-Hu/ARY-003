from flask import Blueprint, jsonify, request

from services import SubmissionService
from utils.auth import require_contestant
from utils.errors import ValidationError

submission_bp = Blueprint('submissions', __name__, url_prefix='/api/submissions')


@submission_bp.route('', methods=['POST'])
@require_contestant
def create_submission():
    data = request.get_json(silent=True)
    if not data:
        raise ValidationError('Request body is required')
    return jsonify(SubmissionService.upsert_submission(data)), 201


@submission_bp.route('/verify', methods=['POST'])
@require_contestant
def verify_submission():
    data = request.get_json(silent=True)
    if not data:
        raise ValidationError('Request body is required')
    return jsonify(SubmissionService.verify_submission(data))
