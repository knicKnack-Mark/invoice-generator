class AppError(Exception):
    """Base app-level error. Carries an HTTP status and a stable error_code
    the frontend can branch on."""

    status_code = 400
    error_code = "APP_ERROR"

    def __init__(self, message: str, error_code: str | None = None, status_code: int | None = None):
        self.message = message
        if error_code:
            self.error_code = error_code
        if status_code:
            self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppError):
    status_code = 404
    error_code = "NOT_FOUND"


class UnauthorizedError(AppError):
    status_code = 401
    error_code = "UNAUTHORIZED"


class ForbiddenError(AppError):
    status_code = 403
    error_code = "FORBIDDEN"


class AccountLockedError(AppError):
    status_code = 423
    error_code = "ACCOUNT_LOCKED"


class ConflictError(AppError):
    status_code = 409
    error_code = "CONFLICT"


class ValidationAppError(AppError):
    status_code = 422
    error_code = "VALIDATION_ERROR"
