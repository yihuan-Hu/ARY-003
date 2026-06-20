from flask import jsonify


class AppError(Exception):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ValidationError(AppError):
    pass


class NotFoundError(AppError):
    def __init__(self, resource='Resource'):
        super().__init__(f'{resource} not found', 404)


class ConflictError(AppError):
    def __init__(self, message):
        super().__init__(message, 409)


def register_error_handlers(app):
    @app.errorhandler(AppError)
    def handle_app_error(error):
        return jsonify({'error': error.message}), error.status_code

    @app.errorhandler(404)
    def handle_404(_error):
        return jsonify({'error': 'Not found'}), 404

    @app.errorhandler(500)
    def handle_500(_error):
        return jsonify({'error': 'Internal server error'}), 500
