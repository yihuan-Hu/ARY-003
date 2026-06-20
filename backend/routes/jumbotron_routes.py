from flask import Blueprint, jsonify, request

from services import JumbotronService

jumbotron_bp = Blueprint('jumbotron', __name__, url_prefix='/api/jumbotron')


@jumbotron_bp.route('/snapshot', methods=['GET'])
def jumbotron_snapshot():
    race_id = (request.args.get('raceId') or '').strip()
    return jsonify(JumbotronService.snapshot(race_id))
