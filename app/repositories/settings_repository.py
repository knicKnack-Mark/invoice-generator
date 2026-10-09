from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import OrganizationSettings


class SettingsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create(self, *, organization_id: UUID) -> OrganizationSettings:
        result = await self.db.execute(
            select(OrganizationSettings).where(OrganizationSettings.organization_id == organization_id)
        )
        settings_row = result.scalar_one_or_none()
        if settings_row:
            return settings_row
        settings_row = OrganizationSettings(organization_id=organization_id)
        self.db.add(settings_row)
        await self.db.flush()
        return settings_row

    async def update(self, settings_row: OrganizationSettings, **fields) -> OrganizationSettings:
        for key, value in fields.items():
            if value is not None:
                setattr(settings_row, key, value)
        await self.db.flush()
        return settings_row