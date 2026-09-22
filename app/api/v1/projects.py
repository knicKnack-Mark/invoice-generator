from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user, require_role
from app.models.base import get_db
from app.models.organization import OrganizationMember
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectOut, ProjectUpdate
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])

READ_ROLES = ("owner", "admin", "manager", "member", "accountant")
WRITE_ROLES = ("owner", "admin", "manager")


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(
    payload: ProjectCreate,
    membership: OrganizationMember = Depends(require_role(*WRITE_ROLES)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ProjectService(db).create(
        organization_id=membership.organization_id, payload=payload, actor_user_id=current_user.id
    )


@router.get("")
async def list_projects(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=settings.default_page_size, ge=1, le=settings.max_page_size),
    client_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None, pattern="^(active|on_hold|completed|cancelled)$"),
    search: str | None = Query(default=None, max_length=255),
    membership: OrganizationMember = Depends(require_role(*READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    projects, total = await ProjectService(db).list(
        organization_id=membership.organization_id,
        page=page,
        page_size=page_size,
        client_id=client_id,
        status=status,
        search=search,
    )
    return {
        "success": True,
        "data": [ProjectOut.model_validate(p) for p in projects],
        "meta": {"page": page, "page_size": page_size, "total": total},
    }


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: UUID,
    membership: OrganizationMember = Depends(require_role(*READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await ProjectService(db).get(organization_id=membership.organization_id, project_id=project_id)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    membership: OrganizationMember = Depends(require_role(*WRITE_ROLES)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ProjectService(db).update(
        organization_id=membership.organization_id, project_id=project_id, payload=payload,
        actor_user_id=current_user.id,
    )


@router.delete("/{project_id}")
async def delete_project(
    project_id: UUID,
    membership: OrganizationMember = Depends(require_role(*WRITE_ROLES)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ProjectService(db).delete(
        organization_id=membership.organization_id, project_id=project_id, actor_user_id=current_user.id
    )
    return {"success": True, "data": {"message": "Project deleted."}}
