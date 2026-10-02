from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user, require_role
from app.models.base import get_db
from app.models.organization import OrganizationMember
from app.models.user import User
from app.schemas.payment import PaymentCreate, PaymentOut
from app.services.payment_service import PaymentService

router = APIRouter(tags=["payments"])

READ_ROLES = ("owner", "admin", "manager", "member", "accountant")
WRITE_ROLES = ("owner", "admin", "manager", "accountant")


@router.post("/invoices/{invoice_id}/payments", response_model=PaymentOut, status_code=201)
async def record_payment(
    invoice_id: UUID,
    payload: PaymentCreate,
    membership: OrganizationMember = Depends(require_role(*WRITE_ROLES)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await PaymentService(db).create(
        organization_id=membership.organization_id, invoice_id=invoice_id, payload=payload,
        actor_user_id=current_user.id,
    )


@router.get("/invoices/{invoice_id}/payments", response_model=list[PaymentOut])
async def list_payments_for_invoice(
    invoice_id: UUID,
    membership: OrganizationMember = Depends(require_role(*READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await PaymentService(db).list_for_invoice(organization_id=membership.organization_id, invoice_id=invoice_id)


@router.get("/payments")
async def list_payments(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=settings.default_page_size, ge=1, le=settings.max_page_size),
    invoice_id: UUID | None = Query(default=None),
    membership: OrganizationMember = Depends(require_role(*READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    payments, total = await PaymentService(db).list(
        organization_id=membership.organization_id, page=page, page_size=page_size, invoice_id=invoice_id
    )
    return {
        "success": True,
        "data": [PaymentOut.model_validate(p) for p in payments],
        "meta": {"page": page, "page_size": page_size, "total": total},
    }


@router.get("/payments/{payment_id}", response_model=PaymentOut)
async def get_payment(
    payment_id: UUID,
    membership: OrganizationMember = Depends(require_role(*READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await PaymentService(db).get(organization_id=membership.organization_id, payment_id=payment_id)


@router.delete("/payments/{payment_id}")
async def delete_payment(
    payment_id: UUID,
    membership: OrganizationMember = Depends(require_role(*WRITE_ROLES)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await PaymentService(db).delete(
        organization_id=membership.organization_id, payment_id=payment_id, actor_user_id=current_user.id
    )
    return {"success": True, "data": {"message": "Payment deleted."}}