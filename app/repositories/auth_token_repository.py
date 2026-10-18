from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth_token import AuthToken


class AuthTokenRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, *, user_id: UUID, purpose: str, token_hash: str, expires_at: datetime) -> AuthToken:
        token = AuthToken(user_id=user_id, purpose=purpose, token_hash=token_hash, expires_at=expires_at)
        self.db.add(token)
        await self.db.flush()
        return token

    async def consume(self, *, purpose: str, token_hash: str) -> UUID | None:
        """Atomically marks a valid token as used and returns its user_id, or
        None if it's unknown, expired, or already used. One UPDATE ... WHERE
        used_at IS NULL means two simultaneous requests can't both succeed."""
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            update(AuthToken)
            .where(
                AuthToken.purpose == purpose,
                AuthToken.token_hash == token_hash,
                AuthToken.used_at.is_(None),
                AuthToken.expires_at > now,
            )
            .values(used_at=now)
            .returning(AuthToken.user_id)
        )
        row = result.first()
        return row[0] if row else None

    async def invalidate_unused(self, *, user_id: UUID, purpose: str) -> None:
        await self.db.execute(
            update(AuthToken)
            .where(AuthToken.user_id == user_id, AuthToken.purpose == purpose, AuthToken.used_at.is_(None))
            .values(used_at=datetime.now(timezone.utc))
        )

    async def has_recent(self, *, user_id: UUID, purpose: str, within: timedelta) -> bool:
        cutoff = datetime.now(timezone.utc) - within
        result = await self.db.execute(
            select(AuthToken.id)
            .where(AuthToken.user_id == user_id, AuthToken.purpose == purpose, AuthToken.created_at >= cutoff)
            .limit(1)
        )
        return result.first() is not None