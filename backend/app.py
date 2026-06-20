import os

from flask import Flask
from flask_cors import CORS

from config import config
from database import init_db
from routes import register_blueprints
from utils.errors import register_error_handlers


def create_app(config_name=None):
    config_name = config_name or os.environ.get('FLASK_CONFIG', 'default')

    app = Flask(__name__)
    app.config.from_object(config[config_name])
    if os.environ.get('ORGANIZER_DB'):
        app.config['DATABASE'] = os.environ['ORGANIZER_DB']
    CORS(app)

    with app.app_context():
        init_db()

    register_blueprints(app)
    register_error_handlers(app)
    return app


app = create_app()


if __name__ == '__main__':
    app.run(debug=app.config['DEBUG'], host='127.0.0.1', port=5000)
