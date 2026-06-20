import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("ARY_SECRET_KEY", "dev-ary-secret-change-in-production")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRATION_HOURS = 24

    DATABASE_PATH = os.environ.get("ARY_DATABASE_PATH", os.path.join(basedir, "..", "ary.db"))

    CORS_ORIGINS = os.environ.get("ARY_CORS_ORIGINS", "*")

    # 默认开发账号（本地测试用）
    DEV_ADMIN_USERNAME = "admin"
    DEV_ADMIN_PASSWORD = "admin"

    # Submission HMAC secret（旧能力保留）
    SUBMISSION_SECRET = os.environ.get("ARY_SUBMISSION_SECRET", "dev-submission-secret")


class TestConfig(Config):
    TESTING = True
    DATABASE_PATH = os.path.join(os.path.dirname(basedir), "test_ary.db")
