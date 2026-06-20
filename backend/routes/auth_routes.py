from flask import Blueprint, jsonify, request

from services import AuthService
from utils.errors import ValidationError

auth_bp = Blueprint('auth', __name__, url_prefix='/api/v1/auth')


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True)
    if not data:
        raise ValidationError('Request body is required')
    return jsonify(AuthService.login(data))
