import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    DATABASE = os.environ.get('ORGANIZER_DB', os.path.join(BASE_DIR, 'organizer.db'))
    JWT_SECRET = os.environ.get('ARY_JWT_SECRET', 'dev-jwt-change-me')
    JSON_AS_ASCII = False
    DEBUG = False
    TESTING = False


class DevelopmentConfig(Config):
    DEBUG = True


class TestConfig(Config):
    TESTING = True
    DATABASE = os.environ.get('ORGANIZER_DB', ':memory:')


class ProductionConfig(Config):
    pass


config = {
    'development': DevelopmentConfig,
    'test': TestConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
