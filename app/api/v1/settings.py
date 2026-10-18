from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_role
from app.core.exceptions import ValidationAppError
from app.integrations.storage import build_object_key, storage_backend
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


@router.post("/logo", response_model=SettingsOut)
async def upload_business_logo(
    file: UploadFile = File(...),
    membership: OrganizationMember = Depends(require_role(*WRITE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    max_bytes = 5 * 1024 * 1024
    content = await file.read(max_bytes + 1)
    mime_type = file.content_type or ""
    signatures = {"image/png": b"\x89PNG\r\n\x1a\n", "image/jpeg": b"\xff\xd8\xff"}
    if mime_type not in signatures or not content.startswith(signatures[mime_type]):
        raise ValidationAppError("Logo must be a valid PNG or JPEG image.", error_code="INVALID_LOGO")
    if not content or len(content) > max_bytes:
        raise ValidationAppError("Logo must be between 1 byte and 5 MB.", error_code="INVALID_LOGO_SIZE")

    key = build_object_key(
        organization_id=membership.organization_id,
        original_filename="business-logo.png" if mime_type == "image/png" else "business-logo.jpg",
    )
    await storage_backend.save(key=key, content=content)
    repo = SettingsRepository(db)
    settings_row = await repo.get_or_create(organization_id=membership.organization_id)
    old_key = settings_row.logo_key
    settings_row.logo_key = key
    await db.commit()
    if old_key:
        await storage_backend.delete(key=old_key)
    return settings_row


@router.delete("/logo", response_model=SettingsOut)
async def delete_business_logo(
    membership: OrganizationMember = Depends(require_role(*WRITE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    repo = SettingsRepository(db)
    settings_row = await repo.get_or_create(organization_id=membership.organization_id)
    old_key = settings_row.logo_key
    settings_row.logo_key = None
    await db.commit()
    if old_key:
        await storage_backend.delete(key=old_key)
    return settings_row