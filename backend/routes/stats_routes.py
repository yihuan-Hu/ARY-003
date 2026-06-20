from flask import Blueprint, jsonify

from services import StatsService

stats_bp = Blueprint('stats', __name__, url_prefix='/api')


@stats_bp.route('/stats', methods=['GET'])
def stats():
    return jsonify(StatsService.get_stats())
