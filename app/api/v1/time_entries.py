from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user, require_role
from app.models.base import get_db
from app.models.organization import OrganizationMember
from app.models.user import User
from app.repositories.time_entry_repository import TimeEntryRepository
from app.schemas.time_entry import TimeEntryCreate, TimeEntryOut, TimeEntryUpdate
from app.services.time_entry_service import TimeEntryService

router = APIRouter(prefix="/time-entries", tags=["time-entries"])

READ_ROLES = ("owner", "admin", "manager", "member", "accountant")
WRITE_ROLES = ("owner", "admin", "manager", "member")


@router.post("", response_model=TimeEntryOut, status_code=201)
async def create_time_entry(
    payload: TimeEntryCreate,
    membership: OrganizationMember = Depends(require_role(*WRITE_ROLES)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await TimeEntryService(db).create(
        organization_id=membership.organization_id, payload=payload, actor_user_id=current_user.id
    )


@router.get("")
async def list_time_entries(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=settings.default_page_size, ge=1, le=settings.max_page_size),
    client_id: UUID | None = Query(default=None),
    project_id: UUID | None = Query(default=None),
    billable: bool | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    membership: OrganizationMember = Depends(require_role(*READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    entries, total = await TimeEntryService(db).list(
        organization_id=membership.organization_id, page=page, page_size=page_size,
        client_id=client_id, project_id=project_id, billable=billable, date_from=date_from, date_to=date_to,
    )
    return {
        "success": True,
        "data": [TimeEntryOut.model_validate(e) for e in entries],
        "meta": {"page": page, "page_size": page_size, "total": total},
    }


# Must stay above "/{entry_id}" so "unbilled" isn't parsed as an entry id.
@router.get("/unbilled", response_model=list[TimeEntryOut])
async def unbilled_time_entries(
    client_id: UUID = Query(...),
    membership: OrganizationMember = Depends(require_role(*READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await TimeEntryRepository(db).list_unbilled(
        organization_id=membership.organization_id, client_id=client_id
    )


@router.get("/{entry_id}", response_model=TimeEntryOut)
async def get_time_entry(
    entry_id: UUID,
    membership: OrganizationMember = Depends(require_role(*READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await TimeEntryService(db).get(organization_id=membership.organization_id, entry_id=entry_id)


@router.patch("/{entry_id}", response_model=TimeEntryOut)
async def update_time_entry(
    entry_id: UUID,
    payload: TimeEntryUpdate,
    membership: OrganizationMember = Depends(require_role(*WRITE_ROLES)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await TimeEntryService(db).update(
        organization_id=membership.organization_id, entry_id=entry_id, payload=payload,
        actor_user_id=current_user.id,
    )


@router.delete("/{entry_id}")
async def delete_time_entry(
    entry_id: UUID,
    membership: OrganizationMember = Depends(require_role(*WRITE_ROLES)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await TimeEntryService(db).delete(
        organization_id=membership.organization_id, entry_id=entry_id, actor_user_id=current_user.id
    )
    return {"success": True, "data": {"message": "Time entry deleted."}}