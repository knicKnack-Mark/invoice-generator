from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationAppError
from app.integrations.storage import build_object_key, storage_backend
from app.models.receipt import ExpenseReceipt
from app.repositories.log_repository import LogRepository
from app.repositories.receipt_repository import ReceiptRepository
from app.schemas.receipt import ReceiptMetadataUpdate


class ReceiptService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ReceiptRepository(db)
        self.logs = LogRepository(db)

    def _validate_upload(self, *, mime_type: str, size_bytes: int) -> None:
        if mime_type not in settings.allowed_upload_mime_type_list:
            raise ValidationAppError(
                f"Unsupported file type '{mime_type}'. Allowed: {', '.join(settings.allowed_upload_mime_type_list)}.",
                error_code="UNSUPPORTED_FILE_TYPE",
            )
        max_bytes = settings.max_upload_size_mb * 1024 * 1024
        if size_bytes > max_bytes:
            raise ValidationAppError(
                f"File exceeds the {settings.max_upload_size_mb}MB upload limit.",
                error_code="FILE_TOO_LARGE",
            )
        if size_bytes == 0:
            raise ValidationAppError("Uploaded file is empty.", error_code="EMPTY_FILE")

    async def upload(
        self,
        *,
        organization_id: UUID,
        expense_id: UUID,
        file_name: str,
        mime_type: str,
        content: bytes,
        actor_user_id: UUID,
    ) -> ExpenseReceipt:
        if not await self.repo.expense_belongs_to_org(organization_id=organization_id, expense_id=expense_id):
            raise NotFoundError("Expense not found.", error_code="EXPENSE_NOT_FOUND")

        self._validate_upload(mime_type=mime_type, size_bytes=len(content))

        # Content-based check, not just the filename extension: a renamed
        # .exe claiming to be image/jpeg still gets caught by the magic-byte
        # sniff below for the common formats we accept.
        if not _looks_like_declared_type(content, mime_type):
            raise ValidationAppError(
                "File content does not match its declared type.", error_code="FILE_CONTENT_MISMATCH"
            )

        key = build_object_key(organization_id=organization_id, original_filename=file_name)
        await storage_backend.save(key=key, content=content)

        receipt = await self.repo.create(
            expense_id=expense_id,
            file_key=key,
            file_name=file_name[:255],
            mime_type=mime_type,
            size_bytes=len(content),
        )
        await self.logs.record_activity(
            organization_id=organization_id, user_id=actor_user_id, action="receipt.uploaded",
            entity_type="expense_receipt", entity_id=receipt.id, metadata={"expense_id": str(expense_id)},
        )
        await self.db.commit()
        return receipt

    async def list_for_expense(self, *, organization_id: UUID, expense_id: UUID) -> list[ExpenseReceipt]:
        if not await self.repo.expense_belongs_to_org(organization_id=organization_id, expense_id=expense_id):
            raise NotFoundError("Expense not found.", error_code="EXPENSE_NOT_FOUND")
        return await self.repo.list_for_expense(organization_id=organization_id, expense_id=expense_id)

    async def get(self, *, organization_id: UUID, receipt_id: UUID) -> ExpenseReceipt:
        receipt = await self.repo.get_by_id(organization_id=organization_id, receipt_id=receipt_id)
        if not receipt:
            raise NotFoundError("Receipt not found.", error_code="RECEIPT_NOT_FOUND")
        return receipt

    async def get_file_bytes(self, *, organization_id: UUID, receipt_id: UUID) -> tuple[bytes, str, str]:
        receipt = await self.get(organization_id=organization_id, receipt_id=receipt_id)
        content = await storage_backend.read(key=receipt.file_key)
        return content, receipt.mime_type, receipt.file_name

    async def update_metadata(
        self, *, organization_id: UUID, receipt_id: UUID, payload: ReceiptMetadataUpdate, actor_user_id: UUID
    ) -> ExpenseReceipt:
        receipt = await self.get(organization_id=organization_id, receipt_id=receipt_id)
        receipt = await self.repo.update(receipt, **payload.model_dump(exclude_unset=True))
        await self.logs.record_activity(
            organization_id=organization_id, user_id=actor_user_id, action="receipt.metadata_updated",
            entity_type="expense_receipt", entity_id=receipt.id,
        )
        await self.db.commit()
        return receipt

    async def delete(self, *, organization_id: UUID, receipt_id: UUID, actor_user_id: UUID) -> None:
        receipt = await self.get(organization_id=organization_id, receipt_id=receipt_id)
        file_key = receipt.file_key
        await self.repo.delete(receipt)
        await self.logs.record_audit(
            organization_id=organization_id, user_id=actor_user_id, action="receipt.deleted",
            entity_type="expense_receipt", entity_id=receipt_id,
        )
        await self.db.commit()
        await storage_backend.delete(key=file_key)


def _looks_like_declared_type(content: bytes, mime_type: str) -> bool:
    signatures = {
        "image/jpeg": (b"\xff\xd8\xff",),
        "image/png": (b"\x89PNG\r\n\x1a\n",),
        "application/pdf": (b"%PDF-",),
        # HEIC has a variable-offset 'ftyp' box; skip strict sniffing for it,
        # relying on the declared content-type + extension checks instead.
        "image/heic": None,
    }
    expected = signatures.get(mime_type)
    if expected is None:
        return True
    return any(content.startswith(sig) for sig in expected)
