import uuid

from flask import Flask, g, request, jsonify
from flask_cors import CORS

from app.config import Config
from app.database import init_db, close_db
from app.utils.errors import register_error_handlers


def create_app(config_class=Config):
    # 初始化 secret（非 testing 模式会强制读取环境变量）
    config_class.init_secrets()

    app = Flask(__name__)
    app.config.from_object(config_class)

    # 请求体大小限制
    app.config["MAX_CONTENT_LENGTH"] = config_class.MAX_CONTENT_LENGTH

    # CORS 白名单
    origins = (
        config_class.CORS_ORIGINS
        if isinstance(config_class.CORS_ORIGINS, list)
        else [o.strip() for o in str(config_class.CORS_ORIGINS).split(",") if o.strip()]
    )
    CORS(
        app,
        origins=origins,
        supports_credentials=True,
        allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
    )

    # 数据库
    with app.app_context():
        init_db(app)
        # 启动时从 DB 恢复 token 黑名单（logout 持久化）
        from app.utils.auth import _load_blacklist_from_db
        _load_blacklist_from_db()

    app.teardown_appcontext(close_db)

    # 错误处理
    register_error_handlers(app)

    # ---- 安全中间件 ----

    @app.before_request
    def enforce_content_type():
        """强制 Content-Type: application/json（GET/OPTIONS/HEAD 及空 body 除外）"""
        if request.method in ("GET", "OPTIONS", "HEAD"):
            return None
        # 空 body 的 POST（无 Content-Length 或长度为 0）不要求 Content-Type
        cl = request.headers.get("Content-Length", "")
        if not cl or cl == "0":
            return None
        ct = request.headers.get("Content-Type", "")
        if not ct.startswith("application/json"):
            return jsonify({
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Content-Type must be application/json",
                    "request_id": getattr(g, "request_id", "unknown"),
                }
            }), 415

    @app.before_request
    def inject_request_id():
        """每个请求生成唯一 request_id"""
        g.request_id = uuid.uuid4().hex[:12]

    @app.before_request
    def record_request_start():
        """记录请求开始时间"""
        from app.utils.logging import request_start
        request_start()

    @app.before_request
    def csrf_check():
        """
        CSRF 保护：POST/PUT/PATCH/DELETE 校验 X-CSRF-Token header。
        CSRF token 由前端从 csrf_token cookie 读取并回传。
        测试模式 / 登录 / CA ingest 路径豁免。
        """
        if app.config.get("TESTING", False):
            return None
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return None
        # 豁免路径：登录使用用户名密码，CA ingest 使用 API Key
        if request.path.startswith("/api/v1/auth/login"):
            return None
        if request.path.startswith("/api/v1/ca-connections/") and request.path.endswith("/ingest"):
            return None
        csrf_cookie = request.cookies.get("csrf_token", "")
        csrf_header = request.headers.get("X-CSRF-Token", "")
        if not csrf_cookie or csrf_header != csrf_cookie:
            return jsonify({
                "error": {
                    "code": "FORBIDDEN",
                    "message": "CSRF token mismatch",
                    "request_id": getattr(g, "request_id", "unknown"),
                }
            }), 403

    @app.after_request
    def add_csrf_cookie(response):
        """为 GET 请求设置 CSRF token cookie"""
        if request.method == "GET" and not request.path.startswith("/api/v1/public"):
            csrf_token = getattr(g, "request_id", uuid.uuid4().hex[:12])
            response.set_cookie(
                "csrf_token",
                csrf_token,
                httponly=False,  # 前端 JS 需要读取此值
                secure=False,   # 生产设为 True
                samesite="Strict",
                max_age=86400,
            )
            # 同时注入到 HEAD 响应头，方便前端直接读取
        return response

    @app.after_request
    def add_security_headers(response):
        """安全响应头 + 请求日志"""
        g._response_status = response.status_code

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["X-Request-ID"] = getattr(g, "request_id", "unknown")

        # HSTS（非 debug 模式下启用）
        if not app.config.get("DEBUG", False):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # 结构化请求日志
        from app.utils.logging import request_log
        request_log()
        return response

    # ---- 健康检查 ----

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.route("/health/ready")
    def health_ready():
        try:
            db = get_db()
            db.execute("SELECT 1").fetchone()
            return jsonify({"status": "ready", "database": "ok"})
        except Exception:
            return jsonify({"status": "not_ready", "database": "error"}), 503

    # 确保 get_db 可用
    from app.database import get_db

    # ---- 蓝图 ----

    from app.routes.auth import auth_bp
    from app.routes.rider import rider_bp
    from app.routes.organizer import organizer_bp
    from app.routes.public import public_bp
    from app.routes.notification import notification_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(rider_bp)
    app.register_blueprint(organizer_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(notification_bp)

    return app
