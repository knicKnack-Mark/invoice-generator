from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.models.base import get_db
from app.models.user import User
from app.repositories.organization_repository import OrganizationRepository
from app.schemas.auth import OrganizationOut

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("", response_model=list[OrganizationOut])
async def list_my_organizations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    memberships = await OrganizationRepository(db).list_for_user(current_user.id)
    return [
        OrganizationOut(id=org.id, name=org.name, slug=org.slug, role=member.role.value)
        for org, member in memberships
    ]
