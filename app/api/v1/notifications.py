from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.models.base import get_db
from app.models.organization import OrganizationMember
from app.models.user import User
from app.repositories.notification_repository import NotificationRepository
from app.schemas.notification import NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])

READ_ROLES = ("owner", "admin", "manager", "member", "accountant")


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    unread_only: bool = Query(default=False),
    membership: OrganizationMember = Depends(require_role(*READ_ROLES)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await NotificationRepository(db).list_for_user(
        organization_id=membership.organization_id,
        user_id=current_user.id,
        unread_only=unread_only,
    )
