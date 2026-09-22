from app.core.config import settings
from app.integrations.redis_client import redis_client


def _key(email: str) -> str:
    return f"login_lockout:{email.lower()}"


async def is_locked_out(email: str) -> bool:
    try:
        count = await redis_client.get(_key(email))
    except Exception:
        # Redis unreachable — fail open rather than locking everyone out.
        return False
    return count is not None and int(count) >= settings.login_lockout_threshold


async def record_failed_attempt(email: str) -> None:
    try:
        key = _key(email)
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, settings.login_lockout_minutes * 60)
    except Exception:
        pass


async def clear_failed_attempts(email: str) -> None:
    try:
        await redis_client.delete(_key(email))
    except Exception:
        pass
