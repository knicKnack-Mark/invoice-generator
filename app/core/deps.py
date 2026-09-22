from uuid import UUID

from fastapi import Cookie, Header, Depends
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.models.base import get_db
from app.models.organization import OrganizationMember
from app.models.user import User
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_repository import UserRepository


async def get_current_user(
    access_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not access_token:
        raise UnauthorizedError("Not authenticated.", error_code="NOT_AUTHENTICATED")
    try:
        user_id = decode_token(access_token, expected_type="access")
    except (JWTError, ValueError):
        raise UnauthorizedError("Invalid or expired session.", error_code="INVALID_TOKEN")

    user = await UserRepository(db).get_by_id(user_id)
    if not user or not user.is_active:
        raise UnauthorizedError("Invalid or expired session.", error_code="INVALID_TOKEN")
    return user


async def get_current_membership(
    x_organization_id: UUID = Header(..., alias="X-Organization-Id"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationMember:
    """The mandatory tenant-access check. Every route that touches org-scoped
    data (clients, expenses, invoices, ...) depends on this, directly or via
    a service that requires the resolved organization_id. A user cannot read
    or write another organization's data because there is no code path that
    skips this membership lookup."""
    membership = await OrganizationRepository(db).get_membership(
        organization_id=x_organization_id, user_id=current_user.id
    )
    if not membership:
        # 403, not 404: the org id itself isn't a guessable per-resource secret,
        # but we still don't leak membership existence beyond "you're not in it".
        raise ForbiddenError("You do not have access to this organization.", error_code="NOT_A_MEMBER")
    return membership


def require_role(*allowed_roles: str):
    async def _check(membership: OrganizationMember = Depends(get_current_membership)) -> OrganizationMember:
        if membership.role.value not in allowed_roles:
            raise ForbiddenError("You do not have permission to perform this action.", error_code="INSUFFICIENT_ROLE")
        return membership

    return _check
