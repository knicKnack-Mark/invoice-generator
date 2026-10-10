from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    # bcrypt has a hard 72-byte input limit; truncate defensively so an
    # unusually long passphrase fails loudly at validation time (Pydantic's
    # max_length on the schema) rather than raising deep inside this call.
    password_bytes = password.encode("utf-8")[:72]
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    password_bytes = plain_password.encode("utf-8")[:72]
    return bcrypt.checkpw(password_bytes, password_hash.encode("utf-8"))


def create_token(subject: UUID, token_type: str, expires_delta: timedelta) -> str:
    """token_type is 'access' or 'refresh'. Encoded so refresh tokens can never
    be used where an access token is required, and vice versa."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: UUID) -> str:
    return create_token(
        user_id, "access", timedelta(minutes=settings.access_token_expire_minutes)
    )


def create_refresh_token(user_id: UUID) -> str:
    return create_token(
        user_id, "refresh", timedelta(days=settings.refresh_token_expire_days)
    )


def decode_token_payload(token: str, expected_type: str) -> dict:
    """Raises JWTError on any invalid/expired/wrong-type token."""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != expected_type:
        raise JWTError("Unexpected token type")
    return payload


def decode_token(token: str, expected_type: str) -> UUID:
    """Raises JWTError (or ValueError) on any invalid token. Callers convert to a 401."""
    return UUID(decode_token_payload(token, expected_type)["sub"])


def token_issued_before(payload: dict, moment: datetime | None) -> bool:
    """True if the token was issued before `moment` (e.g. a password change).
    Compared in whole seconds, because JWT 'iat' has second precision."""
    if moment is None:
        return False
    issued_at = payload.get("iat")
    if issued_at is None:
        return True
    return int(issued_at) < int(moment.timestamp())