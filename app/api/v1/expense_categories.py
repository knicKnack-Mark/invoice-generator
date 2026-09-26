from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_role
from app.models.base import get_db
from app.models.organization import OrganizationMember
from app.repositories.expense_repository import ExpenseCategoryRepository
from app.schemas.expense import ExpenseCategoryCreate, ExpenseCategoryOut

router = APIRouter(prefix="/expense-categories", tags=["expense-categories"])

READ_ROLES = ("owner", "admin", "manager", "member", "accountant")
WRITE_ROLES = ("owner", "admin", "manager")


@router.get("", response_model=list[ExpenseCategoryOut])
async def list_categories(
    membership: OrganizationMember = Depends(require_role(*READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await ExpenseCategoryRepository(db).list(organization_id=membership.organization_id)


@router.post("", response_model=ExpenseCategoryOut, status_code=201)
async def create_category(
    payload: ExpenseCategoryCreate,
    membership: OrganizationMember = Depends(require_role(*WRITE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    category = await ExpenseCategoryRepository(db).create(
        organization_id=membership.organization_id, name=payload.name
    )
    await db.commit()
    return category
