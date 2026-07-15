from flask import jsonify


class AppError(Exception):
    status_code = 500
    error_code = "INTERNAL_ERROR"
    message = "Internal server error"

    def __init__(self, message=None, status_code=None, error_code=None):
        if message:
            self.message = message
        if status_code:
            self.status_code = status_code
        if error_code:
            self.error_code = error_code
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = 404
    error_code = "NOT_FOUND"
    message = "Resource not found"


class ForbiddenError(AppError):
    status_code = 403
    error_code = "FORBIDDEN"
    message = "Access denied"


class UnauthorizedError(AppError):
    status_code = 401
    error_code = "UNAUTHORIZED"
    message = "Authentication required"


class ConflictError(AppError):
    status_code = 409
    error_code = "CONFLICT"
    message = "Resource conflict"


class InvalidStateError(AppError):
    status_code = 422
    error_code = "INVALID_STATE"
    message = "Invalid state transition"


class ValidationError(AppError):
    status_code = 400
    error_code = "VALIDATION_ERROR"
    message = "Validation failed"


class RateLimitError(AppError):
    status_code = 429
    error_code = "RATE_LIMITED"
    message = "Too many requests"


def register_error_handlers(app):
    @app.errorhandler(AppError)
    def handle_app_error(error):
        from flask import g
        return (
            jsonify({
                "error": {
                    "code": error.error_code,
                    "message": error.message,
                    "request_id": getattr(g, "request_id", "unknown"),
                }
            }),
            error.status_code,
        )

    @app.errorhandler(404)
    def handle_404(error):
        from flask import g
        return (
            jsonify({
                "error": {
                    "code": "NOT_FOUND",
                    "message": "The requested URL was not found on the server.",
                    "request_id": getattr(g, "request_id", "unknown"),
                }
            }),
            404,
        )

    @app.errorhandler(500)
    def handle_500(error):
        import traceback
        from flask import g
        app.logger.error(f"[500] request_id={getattr(g, 'request_id', 'unknown')}\n{traceback.format_exc()}")
        return (
            jsonify({
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Internal server error",
                    "request_id": getattr(g, "request_id", "unknown"),
                }
            }),
            500,
        )
