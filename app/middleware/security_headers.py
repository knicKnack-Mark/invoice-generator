from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds standard defensive headers to every response. These don't replace
    input validation or auth checks — they reduce the blast radius of classes
    of client-side attacks (clickjacking, MIME sniffing, protocol downgrade)
    that are orthogonal to SQL injection / auth bypass."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"

        if settings.environment != "development":
            # Only sent over HTTPS deployments — forces HTTPS on repeat visits.
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"

        return response
