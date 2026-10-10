from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification


class NotificationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self, *, organization_id: UUID, user_id: UUID, type: str, payload: dict | None = None
    ) -> Notification:
        notif = Notification(organization_id=organization_id, user_id=user_id, type=type, payload=payload or {})
        self.db.add(notif)
        await self.db.flush()
        return notif

    async def list_for_user(
        self, *, organization_id: UUID, user_id: UUID, unread_only: bool = False
    ) -> list[Notification]:
        conditions = [Notification.organization_id == organization_id, Notification.user_id == user_id]
        if unread_only:
            conditions.append(Notification.read_at.is_(None))
        result = await self.db.execute(
            select(Notification).where(*conditions).order_by(Notification.created_at.desc())
        )
        return list(result.scalars().all())

    async def mark_read(self, *, organization_id: UUID, user_id: UUID, notification_id: UUID) -> None:
        # Scoped by org AND user, so one user can never mark another user's
        # notification as read (it simply matches zero rows).
        await self.db.execute(
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.organization_id == organization_id,
                Notification.user_id == user_id,
            )
            .values(read_at=datetime.now(timezone.utc))
        )
        await self.db.flush()

    async def mark_all_read(self, *, organization_id: UUID, user_id: UUID) -> None:
        await self.db.execute(
            update(Notification)
            .where(
                Notification.organization_id == organization_id,
                Notification.user_id == user_id,
                Notification.read_at.is_(None),
            )
            .values(read_at=datetime.now(timezone.utc))
        )
        await self.db.flush()