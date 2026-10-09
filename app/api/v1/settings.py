from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_role
from app.models.base import get_db
from app.models.organization import OrganizationMember
from app.repositories.settings_repository import SettingsRepository
from app.schemas.settings import SettingsOut, SettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])

READ_ROLES = ("owner", "admin", "manager", "member", "accountant")
WRITE_ROLES = ("owner", "admin")


@router.get("", response_model=SettingsOut)
async def get_settings(
    membership: OrganizationMember = Depends(require_role(*READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    settings_row = await SettingsRepository(db).get_or_create(organization_id=membership.organization_id)
    await db.commit()
    return settings_row


@router.patch("", response_model=SettingsOut)
async def update_settings(
    payload: SettingsUpdate,
    membership: OrganizationMember = Depends(require_role(*WRITE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    repo = SettingsRepository(db)
    settings_row = await repo.get_or_create(organization_id=membership.organization_id)
    update_data = payload.model_dump(exclude_unset=True)
    settings_row = await repo.update(settings_row, **update_data)
    await db.commit()
    return settings_row