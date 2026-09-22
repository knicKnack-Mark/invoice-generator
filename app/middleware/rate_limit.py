import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings
from app.integrations.redis_client import redis_client

# Paths that get a stricter limit (brute-force sensitive).
_STRICT_PREFIXES = ("/api/v1/auth/login", "/api/v1/auth/register")
# Paths excluded entirely (cheap, high-frequency, no sensitive data).
_EXEMPT_PATHS = ("/api/v1/health", "/api/v1/health/db", "/api/v1/ping")


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window limiter keyed by (client IP, minute bucket, route class).
    Fails open (lets the request through) if Redis is unreachable, so a
    cache outage never takes the whole API down."""

    async def dispatch(self, request: Request, call_next):
        if not settings.rate_limit_enabled or request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        is_strict = request.url.path.startswith(_STRICT_PREFIXES)
        limit = settings.rate_limit_auth_per_minute if is_strict else settings.rate_limit_per_minute
        bucket = int(time.time() // 60)
        key = f"ratelimit:{'strict' if is_strict else 'std'}:{_client_ip(request)}:{bucket}"

        try:
            count = await redis_client.incr(key)
            if count == 1:
                await redis_client.expire(key, 60)
        except Exception:
            # Redis unavailable — do not block traffic on a cache failure.
            return await call_next(request)

        if count > limit:
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "message": "Too many requests. Please slow down and try again shortly.",
                    "error_code": "RATE_LIMITED",
                },
                headers={"Retry-After": "60"},
            )

        return await call_next(request)
