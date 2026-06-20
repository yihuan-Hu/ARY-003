import os

from flask import Blueprint, jsonify, send_from_directory

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

pages_bp = Blueprint('pages', __name__)


@pages_bp.route('/')
def index():
    return jsonify({
        'service': 'ARY GRS 001 Organizer Backend',
        'version': '2.0.0',
        'admin': '/admin',
        'public': '/public',
        'jumbotron': '/jumbotron',
        'calibrator': '/calibrator',
        'api': '/api/races',
        'snapshot': '/api/jumbotron/snapshot',
    })


@pages_bp.route('/admin')
def admin_page():
    return send_from_directory(os.path.join(BASE_DIR, '..', 'web'), 'admin.html')


@pages_bp.route('/public')
def public_page():
    return send_from_directory(os.path.join(BASE_DIR, '..', 'web'), 'public.html')


@pages_bp.route('/jumbotron')
def jumbotron_page():
    return send_from_directory(
        os.path.join(BASE_DIR, '..', 'Jumbotron', 'apps', 'race-live-view'),
        'jumbotron.html',
    )


@pages_bp.route('/calibrator')
def calibrator_page():
    return send_from_directory(
        os.path.join(BASE_DIR, '..', 'Jumbotron', 'apps', 'track-calibrator'),
        'calibrator.html',
    )


@pages_bp.route('/Jumbotron/<path:filepath>')
def jumbotron_static(filepath):
    return send_from_directory(os.path.join(BASE_DIR, '..', 'Jumbotron'), filepath)
