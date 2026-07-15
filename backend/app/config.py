import os
import secrets
import sys

basedir = os.path.abspath(os.path.dirname(__file__))


def _require_env(key: str) -> str:
    """强制读取环境变量，缺失则打印错误并退出"""
    value = os.environ.get(key, "").strip()
    if not value:
        print(f"[ARY] FATAL: Environment variable '{key}' is required but not set.", file=sys.stderr)
        print(f"[ARY] Example: export {key}=$(python -c 'import secrets; print(secrets.token_hex(32))')", file=sys.stderr)
        sys.exit(1)
    return value


def _require_cors_origins() -> list[str]:
    """读取 CORS 白名单，未配置则退出"""
    raw = os.environ.get("ARY_CORS_ORIGINS", "").strip()
    if not raw:
        print("[ARY] FATAL: ARY_CORS_ORIGINS is required but not set.", file=sys.stderr)
        print("[ARY] Example: export ARY_CORS_ORIGINS=http://localhost:3000,https://your-domain.com", file=sys.stderr)
        sys.exit(1)
    return [o.strip() for o in raw.split(",") if o.strip()]


class Config:
    # JWT
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRATION_HOURS = int(os.environ.get("ARY_JWT_EXPIRATION_HOURS", "1"))

    # 数据库
    DATABASE_PATH = os.environ.get("ARY_DATABASE_PATH", os.path.join(basedir, "..", "ary.db"))

    # 必填 secret（生产环境强制，测试环境跳过）
    @classmethod
    def init_secrets(cls, testing: bool = False):
        if testing:
            cls.SECRET_KEY = os.environ.get("ARY_SECRET_KEY", "test-secret-key-for-pytest-only")
            cls.SUBMISSION_SECRET = os.environ.get("ARY_SUBMISSION_SECRET", "test-submission-secret-for-pytest-only")
            cls.CORS_ORIGINS = os.environ.get("ARY_CORS_ORIGINS", "*")
        else:
            cls.SECRET_KEY = _require_env("ARY_SECRET_KEY")
            cls.SUBMISSION_SECRET = _require_env("ARY_SUBMISSION_SECRET")
            cls.CORS_ORIGINS = _require_cors_origins()

    # 默认开发账号（本地测试用，生产环境通过环境变量覆盖）
    DEV_ADMIN_USERNAME = os.environ.get("ARY_DEV_ADMIN_USERNAME", "admin")
    DEV_ADMIN_PASSWORD = os.environ.get("ARY_DEV_ADMIN_PASSWORD", "")

    # 请求体大小限制 1MB
    MAX_CONTENT_LENGTH = 1 * 1024 * 1024

    # OAuth（可选）
    GITHUB_OAUTH_CLIENT_ID = os.environ.get("GITHUB_OAUTH_CLIENT_ID", "")
    GITHUB_OAUTH_CLIENT_SECRET = os.environ.get("GITHUB_OAUTH_CLIENT_SECRET", "")


class TestConfig(Config):
    TESTING = True
    DATABASE_PATH = os.path.join(os.path.dirname(basedir), "test_ary.db")

    @classmethod
    def init_secrets(cls):
        super().init_secrets(testing=True)
