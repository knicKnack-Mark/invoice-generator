"""Shared cache client, used for rate limiting and login-lockout counters.

Two ways to configure it (pick whichever is easier to obtain):
  1. UPSTASH_REDIS_REST_URL + UPSTASH_REDIS_REST_TOKEN — Upstash's REST API,
     works over plain HTTPS, no TCP/TLS connection string needed. This is
     what you get immediately from the Upstash dashboard's default view.
  2. REDIS_URL — a standard redis:// or rediss:// connection string, for
     any other Redis provider or a local Redis instance.

Both expose the same async interface (get/set/incr/expire/delete) used by
app/middleware/rate_limit.py and app/integrations/login_lockout.py, so the
rest of the app never needs to know which one is active.
"""
from app.core.config import settings

if settings.upstash_redis_rest_url and settings.upstash_redis_rest_token:
    from upstash_redis.asyncio import Redis as UpstashRedis

    redis_client = UpstashRedis(
        url=settings.upstash_redis_rest_url,
        token=settings.upstash_redis_rest_token,
    )
else:
    import redis.asyncio as redis

    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
