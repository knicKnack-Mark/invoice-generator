from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user, require_role
from app.models.base import get_db
from app.models.organization import OrganizationMember
from app.models.user import User
from app.schemas.client import ClientCreate, ClientOut, ClientUpdate
from app.services.client_service import ClientService

router = APIRouter(prefix="/clients", tags=["clients"])

# Read access: any active member of the org except the client-portal role.
# Write access: owner/admin/manager only, matching the roles table in the spec.
READ_ROLES = ("owner", "admin", "manager", "member", "accountant")
WRITE_ROLES = ("owner", "admin", "manager")


@router.post("", response_model=ClientOut, status_code=201)
async def create_client(
    payload: ClientCreate,
    membership: OrganizationMember = Depends(require_role(*WRITE_ROLES)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ClientService(db).create(
        organization_id=membership.organization_id, payload=payload, actor_user_id=current_user.id
    )


@router.get("")
async def list_clients(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=settings.default_page_size, ge=1, le=settings.max_page_size),
    search: str | None = Query(default=None, max_length=255),
    status: str | None = Query(default=None, pattern="^(active|inactive|archived)$"),
    membership: OrganizationMember = Depends(require_role(*READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    clients, total = await ClientService(db).list(
        organization_id=membership.organization_id,
        page=page,
        page_size=page_size,
        search=search,
        status=status,
    )
    return {
        "success": True,
        "data": [ClientOut.model_validate(c) for c in clients],
        "meta": {"page": page, "page_size": page_size, "total": total},
    }


@router.get("/{client_id}", response_model=ClientOut)
async def get_client(
    client_id: UUID,
    membership: OrganizationMember = Depends(require_role(*READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await ClientService(db).get(organization_id=membership.organization_id, client_id=client_id)


@router.patch("/{client_id}", response_model=ClientOut)
async def update_client(
    client_id: UUID,
    payload: ClientUpdate,
    membership: OrganizationMember = Depends(require_role(*WRITE_ROLES)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ClientService(db).update(
        organization_id=membership.organization_id, client_id=client_id, payload=payload,
        actor_user_id=current_user.id,
    )


@router.delete("/{client_id}", status_code=200)
async def delete_client(
    client_id: UUID,
    membership: OrganizationMember = Depends(require_role(*WRITE_ROLES)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ClientService(db).delete(
        organization_id=membership.organization_id, client_id=client_id, actor_user_id=current_user.id
    )
    return {"success": True, "data": {"message": "Client deleted."}}
