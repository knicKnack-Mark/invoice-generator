from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user, require_role
from app.models.base import get_db
from app.models.organization import OrganizationMember
from app.models.user import User
from app.schemas.expense import (
    ExpenseCreate,
    ExpenseOut,
    ExpenseStatusUpdate,
    ExpenseUpdate,
    UnbilledExpensesSummary,
)
from app.services.expense_service import ExpenseService

router = APIRouter(prefix="/expenses", tags=["expenses"])

READ_ROLES = ("owner", "admin", "manager", "member", "accountant")
WRITE_ROLES = ("owner", "admin", "manager", "member")  # members can log their own expenses


@router.post("", response_model=ExpenseOut, status_code=201)
async def create_expense(
    payload: ExpenseCreate,
    membership: OrganizationMember = Depends(require_role(*WRITE_ROLES)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ExpenseService(db).create(
        organization_id=membership.organization_id, payload=payload, actor_user_id=current_user.id
    )


@router.get("")
async def list_expenses(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=settings.default_page_size, ge=1, le=settings.max_page_size),
    client_id: UUID | None = Query(default=None),
    project_id: UUID | None = Query(default=None),
    category_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None, pattern="^(draft|pending|approved|rejected|billed|paid)$"),
    billable: bool | None = Query(default=None),
    reimbursable: bool | None = Query(default=None),
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    search: str | None = Query(default=None, max_length=255),
    membership: OrganizationMember = Depends(require_role(*READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    expenses, total = await ExpenseService(db).list(
        organization_id=membership.organization_id,
        page=page, page_size=page_size,
        client_id=client_id, project_id=project_id, category_id=category_id,
        status=status, billable=billable, reimbursable=reimbursable,
        currency=currency, date_from=date_from, date_to=date_to, search=search,
    )
    return {
        "success": True,
        "data": [ExpenseOut.model_validate(e) for e in expenses],
        "meta": {"page": page, "page_size": page_size, "total": total},
    }


@router.get("/unbilled", response_model=UnbilledExpensesSummary)
async def unbilled_expenses(
    client_id: UUID = Query(...),
    membership: OrganizationMember = Depends(require_role(*READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await ExpenseService(db).unbilled_summary(organization_id=membership.organization_id, client_id=client_id)


@router.get("/{expense_id}", response_model=ExpenseOut)
async def get_expense(
    expense_id: UUID,
    membership: OrganizationMember = Depends(require_role(*READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await ExpenseService(db).get(organization_id=membership.organization_id, expense_id=expense_id)


@router.patch("/{expense_id}", response_model=ExpenseOut)
async def update_expense(
    expense_id: UUID,
    payload: ExpenseUpdate,
    membership: OrganizationMember = Depends(require_role(*WRITE_ROLES)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ExpenseService(db).update(
        organization_id=membership.organization_id, expense_id=expense_id, payload=payload,
        actor_user_id=current_user.id,
    )


@router.post("/{expense_id}/status", response_model=ExpenseOut)
async def change_expense_status(
    expense_id: UUID,
    payload: ExpenseStatusUpdate,
    membership: OrganizationMember = Depends(require_role(*WRITE_ROLES)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ExpenseService(db).update_status(
        organization_id=membership.organization_id, expense_id=expense_id,
        new_status=payload.status, actor_user_id=current_user.id,
    )


@router.post("/{expense_id}/duplicate", response_model=ExpenseOut, status_code=201)
async def duplicate_expense(
    expense_id: UUID,
    membership: OrganizationMember = Depends(require_role(*WRITE_ROLES)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ExpenseService(db).duplicate(
        organization_id=membership.organization_id, expense_id=expense_id, actor_user_id=current_user.id
    )


@router.delete("/{expense_id}")
async def delete_expense(
    expense_id: UUID,
    membership: OrganizationMember = Depends(require_role(*WRITE_ROLES)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ExpenseService(db).delete(
        organization_id=membership.organization_id, expense_id=expense_id, actor_user_id=current_user.id
    )
    return {"success": True, "data": {"message": "Expense deleted."}}
