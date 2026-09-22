from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.logs import ActivityLog, AuditLog


class LogRepository:
    """Insert-only by design — no update/delete methods are exposed here on
    purpose, mirroring the append-only intent of these tables."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_activity(
        self,
        *,
        organization_id: UUID | None,
        user_id: UUID | None,
        action: str,
        entity_type: str,
        entity_id: UUID | None = None,
        metadata: dict | None = None,
    ) -> None:
        self.db.add(
            ActivityLog(
                organization_id=organization_id,
                user_id=user_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                log_metadata=metadata or {},
            )
        )
        await self.db.flush()

    async def record_audit(
        self,
        *,
        organization_id: UUID | None,
        user_id: UUID | None,
        action: str,
        entity_type: str,
        entity_id: UUID | None = None,
        ip_address: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        self.db.add(
            AuditLog(
                organization_id=organization_id,
                user_id=user_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                ip_address=ip_address,
                log_metadata=metadata or {},
            )
        )
        await self.db.flush()
