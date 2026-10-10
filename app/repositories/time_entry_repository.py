from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.time_entry import TimeEntry


class TimeEntryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, *, organization_id: UUID, user_id: UUID, **fields) -> TimeEntry:
        entry = TimeEntry(organization_id=organization_id, user_id=user_id, **fields)
        self.db.add(entry)
        await self.db.flush()
        return entry

    async def get_by_id(self, *, organization_id: UUID, entry_id: UUID) -> TimeEntry | None:
        result = await self.db.execute(
            select(TimeEntry).where(
                TimeEntry.id == entry_id, TimeEntry.organization_id == organization_id, TimeEntry.deleted_at.is_(None)
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self, *, organization_id: UUID, page: int, page_size: int,
        client_id: UUID | None = None, project_id: UUID | None = None,
        billable: bool | None = None, date_from: date | None = None, date_to: date | None = None,
    ) -> tuple[list[TimeEntry], int]:
        conditions = [TimeEntry.organization_id == organization_id, TimeEntry.deleted_at.is_(None)]
        if client_id:
            conditions.append(TimeEntry.client_id == client_id)
        if project_id:
            conditions.append(TimeEntry.project_id == project_id)
        if billable is not None:
            conditions.append(TimeEntry.billable == billable)
        if date_from:
            conditions.append(TimeEntry.entry_date >= date_from)
        if date_to:
            conditions.append(TimeEntry.entry_date <= date_to)

        count_result = await self.db.execute(select(func.count()).select_from(TimeEntry).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(TimeEntry).where(*conditions)
            .order_by(TimeEntry.entry_date.desc(), TimeEntry.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size)
        )
        return list(result.scalars().all()), total

    async def list_unbilled(self, *, organization_id: UUID, client_id: UUID) -> list[TimeEntry]:
        result = await self.db.execute(
            select(TimeEntry).where(
                TimeEntry.organization_id == organization_id,
                TimeEntry.client_id == client_id,
                TimeEntry.billable.is_(True),
                TimeEntry.invoiced_at.is_(None),
                TimeEntry.deleted_at.is_(None),
            ).order_by(TimeEntry.entry_date.asc())
        )
        return list(result.scalars().all())

    async def update(self, entry: TimeEntry, **fields) -> TimeEntry:
        for key, value in fields.items():
            if value is not None:
                setattr(entry, key, value)
        await self.db.flush()
        return entry

    async def soft_delete(self, entry: TimeEntry) -> None:
        entry.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()