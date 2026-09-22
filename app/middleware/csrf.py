import hmac

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_EXEMPT_PATHS = (
    "/api/v1/ping",
    "/api/v1/health",
    "/api/v1/health/db",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
)


class CSRFMiddleware(BaseHTTPMiddleware):
    """Double-submit cookie CSRF protection.

    The access/refresh tokens live in httpOnly cookies so JavaScript can't
    read them — which is good for XSS, but it means a malicious site can
    still make the browser *send* those cookies on a cross-site request. The
    CSRF token is deliberately NOT httpOnly: legitimate frontend JS reads it
    from the cookie and echoes it back in a header. A cross-site attacker's
    browser will send the session cookie automatically but cannot read the
    CSRF cookie's value (same-origin policy) to put it in the header, so the
    two values won't match on a forged request.

    Login/register/refresh are exempt because they don't rely on an existing
    authenticated session cookie to have effect; they issue a fresh CSRF
    token on success (see app/api/v1/auth.py).
    """

    async def dispatch(self, request: Request, call_next):
        if request.method in _SAFE_METHODS or request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
        header_token = request.headers.get(CSRF_HEADER_NAME)

        if not cookie_token or not header_token or not hmac.compare_digest(cookie_token, header_token):
            return JSONResponse(
                status_code=403,
                content={
                    "success": False,
                    "message": "Missing or invalid CSRF token.",
                    "error_code": "CSRF_VALIDATION_FAILED",
                },
            )

        return await call_next(request)
