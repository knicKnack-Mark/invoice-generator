from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationAppError
from app.models.time_entry import TimeEntry
from app.repositories.client_repository import ClientRepository
from app.repositories.expense_repository import ExpenseRepository
from app.repositories.log_repository import LogRepository
from app.repositories.time_entry_repository import TimeEntryRepository
from app.schemas.time_entry import TimeEntryCreate, TimeEntryUpdate


class TimeEntryService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = TimeEntryRepository(db)
        self.clients = ClientRepository(db)
        self.expenses = ExpenseRepository(db)
        self.logs = LogRepository(db)

    async def create(self, *, organization_id: UUID, payload: TimeEntryCreate, actor_user_id: UUID) -> TimeEntry:
        client = await self.clients.get_by_id(organization_id=organization_id, client_id=payload.client_id)
        if not client:
            raise ValidationAppError("client_id does not refer to a client in this organization.", error_code="INVALID_CLIENT")
        if payload.project_id and not await self.expenses.project_belongs_to_client(
            organization_id=organization_id, project_id=payload.project_id, client_id=payload.client_id
        ):
            raise ValidationAppError(
                "project_id does not belong to the given client in this organization.", error_code="INVALID_PROJECT"
            )

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

    async def update(
        self, *, organization_id: UUID, entry_id: UUID, payload: TimeEntryUpdate,
        actor_user_id: UUID, actor_role: str,
    ) -> TimeEntry:
        entry = await self.get(organization_id=organization_id, entry_id=entry_id)
        self._ensure_can_manage_entry(entry=entry, actor_user_id=actor_user_id, actor_role=actor_role)
        if entry.invoiced_at is not None:
            raise ValidationAppError("This time entry is already invoiced and can no longer be edited.", error_code="TIME_ENTRY_LOCKED")

        update_data = payload.model_dump(exclude_unset=True)
        if update_data.get("project_id") and not await self.expenses.project_belongs_to_client(
            organization_id=organization_id, project_id=update_data["project_id"], client_id=entry.client_id
        ):
            raise ValidationAppError(
                "project_id does not belong to this entry's client.", error_code="INVALID_PROJECT"
            )
        entry = await self.repo.update(entry, **update_data)
        await self.logs.record_activity(
            organization_id=organization_id, user_id=actor_user_id, action="time_entry.updated",
            entity_type="time_entry", entity_id=entry.id,
        )
        await self.db.commit()
        return entry

    async def delete(
        self, *, organization_id: UUID, entry_id: UUID, actor_user_id: UUID, actor_role: str
    ) -> None:
        entry = await self.get(organization_id=organization_id, entry_id=entry_id)
        self._ensure_can_manage_entry(entry=entry, actor_user_id=actor_user_id, actor_role=actor_role)
        if entry.invoiced_at is not None:
            raise ValidationAppError("This time entry is already invoiced and cannot be deleted.", error_code="TIME_ENTRY_LOCKED")
        await self.repo.soft_delete(entry)
        await self.logs.record_audit(
            organization_id=organization_id, user_id=actor_user_id, action="time_entry.deleted",
            entity_type="time_entry", entity_id=entry_id,
        )
        await self.db.commit()

    @staticmethod
    def _ensure_can_manage_entry(*, entry: TimeEntry, actor_user_id: UUID, actor_role: str) -> None:
        if actor_role == "member" and entry.user_id != actor_user_id:
            raise ForbiddenError(
                "Members can only modify or delete their own time entries.",
                error_code="INSUFFICIENT_ROLE",
            )
