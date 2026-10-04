from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_role
from app.models.base import get_db
from app.models.organization import OrganizationMember
from app.schemas.dashboard import DashboardOut
from app.services.dashboard_service import DashboardService

router = APIRouter(tags=["dashboard"])

READ_ROLES = ("owner", "admin", "manager", "member", "accountant")


@router.get("/dashboard", response_model=DashboardOut)
async def get_dashboard(
    membership: OrganizationMember = Depends(require_role(*READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await DashboardService(db).get_overview(organization_id=membership.organization_id)
