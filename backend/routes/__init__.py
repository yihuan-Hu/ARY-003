def register_blueprints(app):
    from .agent_usage_routes import agent_usage_bp
    from .auth_routes import auth_bp
    from .entry_routes import entry_bp
    from .export_routes import export_bp
    from .jumbotron_routes import jumbotron_bp
    from .pages import pages_bp
    from .race_routes import race_bp
    from .rider_routes import rider_bp
    from .stats_routes import stats_bp
    from .submission_routes import submission_bp
    from .track_routes import track_bp

    from .v1_routes import contestant_v1_bp, organizer_v1_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(agent_usage_bp)
    app.register_blueprint(organizer_v1_bp)
    app.register_blueprint(contestant_v1_bp)
    app.register_blueprint(race_bp)
    app.register_blueprint(submission_bp)
    app.register_blueprint(rider_bp)
    app.register_blueprint(entry_bp)
    app.register_blueprint(track_bp)
    app.register_blueprint(jumbotron_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(stats_bp)
