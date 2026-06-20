from flask import Flask

from app.config import Config
from app.database import init_db, close_db
from app.utils.errors import register_error_handlers


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # 数据库初始化
    with app.app_context():
        init_db(app)

    # 注册 teardown
    app.teardown_appcontext(close_db)

    # 注册错误处理
    register_error_handlers(app)

    # 注册蓝图
    from app.routes.auth import auth_bp
    from app.routes.rider import rider_bp
    from app.routes.organizer import organizer_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(rider_bp)
    app.register_blueprint(organizer_bp)

    return app
