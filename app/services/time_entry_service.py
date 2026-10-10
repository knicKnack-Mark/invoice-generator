from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.time_entry import TimeEntry
from app.repositories.client_repository import ClientRepository
from app.repositories.log_repository import LogRepository
from app.repositories.time_entry_repository import TimeEntryRepository
from app.schemas.time_entry import TimeEntryCreate, TimeEntryUpdate


class TimeEntryService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = TimeEntryRepository(db)
        self.clients = ClientRepository(db)
        self.logs = LogRepository(db)

    async def create(self, *, organization_id: UUID, payload: TimeEntryCreate, actor_user_id: UUID) -> TimeEntry:
        client = await self.clients.get_by_id(organization_id=organization_id, client_id=payload.client_id)
        if not client:
            raise ValidationAppError("client_id does not refer to a client in this organization.", error_code="INVALID_CLIENT")

        entry = await self.repo.create(organization_id=organization_id, user_id=actor_user_id, **payload.model_dump())
        await self.logs.record_activity(
            organization_id=organization_id, user_id=actor_user_id, action="time_entry.created",
            entity_type="time_entry", entity_id=entry.id,
        )
        await self.db.commit()
        return entry

    async def get(self, *, organization_id: UUID, entry_id: UUID) -> TimeEntry:
        entry = await self.repo.get_by_id(organization_id=organization_id, entry_id=entry_id)
        if not entry:
            raise NotFoundError("Time entry not found.", error_code="TIME_ENTRY_NOT_FOUND")
        return entry

    async def list(self, *, organization_id: UUID, page: int, page_size: int, **filters):
        page = max(page, 1)
        page_size = min(max(page_size, 1), settings.max_page_size)
        return await self.repo.list(organization_id=organization_id, page=page, page_size=page_size, **filters)

    async def update(self, *, organization_id: UUID, entry_id: UUID, payload: TimeEntryUpdate, actor_user_id: UUID) -> TimeEntry:
        entry = await self.get(organization_id=organization_id, entry_id=entry_id)
        if entry.invoiced_at is not None:
            raise ValidationAppError("This time entry is already invoiced and can no longer be edited.", error_code="TIME_ENTRY_LOCKED")
        entry = await self.repo.update(entry, **payload.model_dump(exclude_unset=True))
        await self.logs.record_activity(
            organization_id=organization_id, user_id=actor_user_id, action="time_entry.updated",
            entity_type="time_entry", entity_id=entry.id,
        )
        await self.db.commit()
        return entry

    async def delete(self, *, organization_id: UUID, entry_id: UUID, actor_user_id: UUID) -> None:
        entry = await self.get(organization_id=organization_id, entry_id=entry_id)
        if entry.invoiced_at is not None:
            raise ValidationAppError("This time entry is already invoiced and cannot be deleted.", error_code="TIME_ENTRY_LOCKED")
        await self.repo.soft_delete(entry)
        await self.logs.record_audit(
            organization_id=organization_id, user_id=actor_user_id, action="time_entry.deleted",
            entity_type="time_entry", entity_id=entry_id,
        )
        await self.db.commit()