import io
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user, require_role
from app.models.base import get_db
from app.models.organization import OrganizationMember
from app.models.user import User
from app.schemas.invoice import InvoiceCreate, InvoiceOut, InvoiceStatusUpdate, InvoiceUpdate, PublicInvoiceOut
from app.services.invoice_service import InvoiceService

router = APIRouter(tags=["invoices"])

READ_ROLES = ("owner", "admin", "manager", "member", "accountant")
WRITE_ROLES = ("owner", "admin", "manager")


@router.post("/invoices", response_model=InvoiceOut, status_code=201)
async def create_invoice(
    payload: InvoiceCreate,
    membership: OrganizationMember = Depends(require_role(*WRITE_ROLES)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await InvoiceService(db).create(
        organization_id=membership.organization_id, payload=payload, actor_user_id=current_user.id
    )


@router.get("/invoices")
async def list_invoices(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=settings.default_page_size, ge=1, le=settings.max_page_size),
    client_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None, pattern="^(draft|sent|viewed|partially_paid|paid|cancelled)$"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    membership: OrganizationMember = Depends(require_role(*READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    invoices, total = await InvoiceService(db).list(
        organization_id=membership.organization_id, page=page, page_size=page_size,
        client_id=client_id, status=status, date_from=date_from, date_to=date_to,
    )
    return {
        "success": True,
        "data": [InvoiceOut.model_validate(i) for i in invoices],
        "meta": {"page": page, "page_size": page_size, "total": total},
    }


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
async def get_invoice(
    invoice_id: UUID,
    membership: OrganizationMember = Depends(require_role(*READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await InvoiceService(db).get(organization_id=membership.organization_id, invoice_id=invoice_id)


@router.patch("/invoices/{invoice_id}", response_model=InvoiceOut)
async def update_invoice(
    invoice_id: UUID,
    payload: InvoiceUpdate,
    membership: OrganizationMember = Depends(require_role(*WRITE_ROLES)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await InvoiceService(db).update(
        organization_id=membership.organization_id, invoice_id=invoice_id, payload=payload,
        actor_user_id=current_user.id,
    )


@router.post("/invoices/{invoice_id}/status", response_model=InvoiceOut)
async def change_invoice_status(
    invoice_id: UUID,
    payload: InvoiceStatusUpdate,
    membership: OrganizationMember = Depends(require_role(*WRITE_ROLES)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await InvoiceService(db).change_status(
        organization_id=membership.organization_id, invoice_id=invoice_id,
        new_status=payload.status, actor_user_id=current_user.id,
    )


@router.post("/invoices/{invoice_id}/send", response_model=InvoiceOut)
async def send_invoice(
    invoice_id: UUID,
    membership: OrganizationMember = Depends(require_role(*WRITE_ROLES)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await InvoiceService(db).send(
        organization_id=membership.organization_id, invoice_id=invoice_id, actor_user_id=current_user.id
    )


@router.get("/invoices/{invoice_id}/pdf")
async def download_invoice_pdf(
    invoice_id: UUID,
    membership: OrganizationMember = Depends(require_role(*READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    pdf_bytes = await InvoiceService(db).get_pdf_bytes(organization_id=membership.organization_id, invoice_id=invoice_id)
    return StreamingResponse(
        io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=invoice-{invoice_id}.pdf"},
    )


@router.delete("/invoices/{invoice_id}")
async def delete_invoice(
    invoice_id: UUID,
    membership: OrganizationMember = Depends(require_role(*WRITE_ROLES)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await InvoiceService(db).delete(
        organization_id=membership.organization_id, invoice_id=invoice_id, actor_user_id=current_user.id
    )
    return {"success": True, "data": {"message": "Invoice deleted."}}


# --- Public, unauthenticated link (spec §58) ---
public_router = APIRouter(tags=["public-invoices"])


@public_router.get("/invoice/public/{public_token}", response_model=PublicInvoiceOut)
async def view_public_invoice(public_token: str, db: AsyncSession = Depends(get_db)):
    _invoice, public_out = await InvoiceService(db).get_by_public_token(public_token=public_token)
    return public_out