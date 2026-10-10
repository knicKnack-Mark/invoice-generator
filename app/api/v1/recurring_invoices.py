from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.models.base import get_db
from app.models.organization import OrganizationMember
from app.models.user import User
from app.schemas.invoice import InvoiceOut
from app.schemas.recurring_invoice import RecurringInvoiceCreate, RecurringInvoiceOut, RecurringInvoiceUpdate
from app.services.recurring_invoice_service import RecurringInvoiceService

router = APIRouter(prefix="/recurring-invoices", tags=["recurring-invoices"])

READ_ROLES = ("owner", "admin", "manager", "member", "accountant")
WRITE_ROLES = ("owner", "admin", "manager")


@router.post("", response_model=RecurringInvoiceOut, status_code=201)
async def create_recurring_invoice(
    payload: RecurringInvoiceCreate,
    membership: OrganizationMember = Depends(require_role(*WRITE_ROLES)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await RecurringInvoiceService(db).create(
        organization_id=membership.organization_id, payload=payload, actor_user_id=current_user.id
    )


@router.get("", response_model=list[RecurringInvoiceOut])
async def list_recurring_invoices(
    is_active: bool | None = Query(default=None),
    membership: OrganizationMember = Depends(require_role(*READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await RecurringInvoiceService(db).list(organization_id=membership.organization_id, is_active=is_active)


@router.post("/generate-due", response_model=list[InvoiceOut])
async def generate_due_recurring_invoices(
    membership: OrganizationMember = Depends(require_role(*WRITE_ROLES)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await RecurringInvoiceService(db).generate_due(
        organization_id=membership.organization_id, actor_user_id=current_user.id
    )


@router.get("/{recurring_id}", response_model=RecurringInvoiceOut)
async def get_recurring_invoice(
    recurring_id: UUID,
    membership: OrganizationMember = Depends(require_role(*READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await RecurringInvoiceService(db).get(
        organization_id=membership.organization_id, recurring_id=recurring_id
    )


@router.patch("/{recurring_id}", response_model=RecurringInvoiceOut)
async def update_recurring_invoice(
    recurring_id: UUID,
    payload: RecurringInvoiceUpdate,
    membership: OrganizationMember = Depends(require_role(*WRITE_ROLES)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await RecurringInvoiceService(db).update(
        organization_id=membership.organization_id, recurring_id=recurring_id, payload=payload,
        actor_user_id=current_user.id,
    )


@router.post("/{recurring_id}/generate", response_model=InvoiceOut)
async def generate_recurring_invoice_now(
    recurring_id: UUID,
    membership: OrganizationMember = Depends(require_role(*WRITE_ROLES)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await RecurringInvoiceService(db).generate_now(
        organization_id=membership.organization_id, recurring_id=recurring_id, actor_user_id=current_user.id
    )