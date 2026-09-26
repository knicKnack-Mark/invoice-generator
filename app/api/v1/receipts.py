import io
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.models.base import get_db
from app.models.organization import OrganizationMember
from app.models.user import User
from app.schemas.receipt import ReceiptMetadataUpdate, ReceiptOut
from app.services.receipt_service import ReceiptService

router = APIRouter(tags=["receipts"])

READ_ROLES = ("owner", "admin", "manager", "member", "accountant")
WRITE_ROLES = ("owner", "admin", "manager", "member")


@router.post("/expenses/{expense_id}/receipts", response_model=ReceiptOut, status_code=201)
async def upload_receipt(
    expense_id: UUID,
    file: UploadFile = File(...),
    membership: OrganizationMember = Depends(require_role(*WRITE_ROLES)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    return await ReceiptService(db).upload(
        organization_id=membership.organization_id,
        expense_id=expense_id,
        file_name=file.filename or "receipt",
        mime_type=file.content_type or "application/octet-stream",
        content=content,
        actor_user_id=current_user.id,
    )


@router.get("/expenses/{expense_id}/receipts", response_model=list[ReceiptOut])
async def list_receipts(
    expense_id: UUID,
    membership: OrganizationMember = Depends(require_role(*READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await ReceiptService(db).list_for_expense(
        organization_id=membership.organization_id, expense_id=expense_id
    )


@router.get("/receipts/{receipt_id}/file")
async def download_receipt_file(
    receipt_id: UUID,
    membership: OrganizationMember = Depends(require_role(*READ_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Streams the file back after the same tenant check as every other
    endpoint — receipts are never served from a public static path."""
    content, mime_type, file_name = await ReceiptService(db).get_file_bytes(
        organization_id=membership.organization_id, receipt_id=receipt_id
    )
    return StreamingResponse(
        io.BytesIO(content),
        media_type=mime_type,
        headers={"Content-Disposition": f'inline; filename="{file_name}"'},
    )


@router.patch("/receipts/{receipt_id}", response_model=ReceiptOut)
async def update_receipt_metadata(
    receipt_id: UUID,
    payload: ReceiptMetadataUpdate,
    membership: OrganizationMember = Depends(require_role(*WRITE_ROLES)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ReceiptService(db).update_metadata(
        organization_id=membership.organization_id, receipt_id=receipt_id, payload=payload,
        actor_user_id=current_user.id,
    )


@router.delete("/receipts/{receipt_id}")
async def delete_receipt(
    receipt_id: UUID,
    membership: OrganizationMember = Depends(require_role(*WRITE_ROLES)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ReceiptService(db).delete(
        organization_id=membership.organization_id, receipt_id=receipt_id, actor_user_id=current_user.id
    )
    return {"success": True, "data": {"message": "Receipt deleted."}}
