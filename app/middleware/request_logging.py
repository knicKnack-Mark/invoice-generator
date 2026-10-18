import logging
from time import perf_counter

from starlette.routing import Match
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("app.request")


def _route_path(scope: Scope) -> str:
    app = scope.get("app")
    router = getattr(app, "router", None)
    routes = getattr(router, "routes", ())
    partial_match = None
    for route in routes:
        match, _ = route.matches(scope)
        if match is Match.FULL:
            return getattr(route, "path", "<unmatched>")
        if match is Match.PARTIAL and partial_match is None:
            partial_match = getattr(route, "path", "<unmatched>")
    return partial_match or "<unmatched>"


class RequestLoggingMiddleware:
    """Logs each request's route, status, and duration without request data."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started_at = perf_counter()
        status_code = 500

        async def send_with_status(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        method = scope["method"]
        route_path = _route_path(scope)
        try:
            await self.app(scope, receive, send_with_status)
        except Exception:
            logger.exception("HTTP %s %s failed", method, route_path)
            raise

        duration_ms = (perf_counter() - started_at) * 1000
        logger.info(
            "HTTP %s %s -> %d (%.1f ms)",
            method,
            route_path,
            status_code,
            duration_ms,
        )
