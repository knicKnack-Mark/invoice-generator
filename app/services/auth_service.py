from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AccountLockedError, ConflictError, UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.integrations import login_lockout
from app.models.user import User
from app.repositories.log_repository import LogRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.expense_repository import ExpenseCategoryRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthResponse, OrganizationOut, UserOut


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.users = UserRepository(db)
        self.orgs = OrganizationRepository(db)
        self.logs = LogRepository(db)
        self.categories = ExpenseCategoryRepository(db)

    async def register(
        self, *, email: str, password: str, full_name: str, organization_name: str, ip_address: str | None = None
    ) -> tuple[AuthResponse, str]:
        existing = await self.users.get_by_email(email)
        if existing:
            raise ConflictError("An account with this email already exists.", error_code="EMAIL_TAKEN")

        user = await self.users.create(
            email=email, password_hash=hash_password(password), full_name=full_name
        )
        org = await self.orgs.create(name=organization_name, owner_user_id=user.id)
        await self.categories.seed_defaults(organization_id=org.id)
        await self.logs.record_audit(
            organization_id=org.id, user_id=user.id, action="user.register",
            entity_type="user", entity_id=user.id, ip_address=ip_address,
        )
        await self.db.commit()

        return self._build_auth_response(user, [(org, "owner")])

    async def login(self, *, email: str, password: str, ip_address: str | None = None) -> tuple[AuthResponse, str]:
        if await login_lockout.is_locked_out(email):
            raise AccountLockedError(
                "Too many failed login attempts. Please try again later or reset your password.",
                error_code="ACCOUNT_LOCKED",
            )

        user = await self.users.get_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            await login_lockout.record_failed_attempt(email)
            if user:
                await self.logs.record_audit(
                    organization_id=None, user_id=user.id, action="user.login_failed",
                    entity_type="user", entity_id=user.id, ip_address=ip_address,
                )
                await self.db.commit()
            raise UnauthorizedError("Invalid email or password.", error_code="INVALID_CREDENTIALS")
        if not user.is_active:
            raise UnauthorizedError("This account is disabled.", error_code="ACCOUNT_DISABLED")

        await login_lockout.clear_failed_attempts(email)

        memberships = await self.orgs.list_for_user(user.id)
        orgs_with_role = [(org, member.role.value) for org, member in memberships]

        await self.logs.record_audit(
            organization_id=orgs_with_role[0][0].id if orgs_with_role else None,
            user_id=user.id, action="user.login", entity_type="user", entity_id=user.id,
            ip_address=ip_address,
        )
        await self.db.commit()

        return self._build_auth_response(user, orgs_with_role)

    async def refresh(self, user_id: UUID) -> tuple[AuthResponse, str]:
        """Called after the refresh token has already been verified by the route
        (signature + type + not-revoked). Issues a fresh access/refresh pair."""
        user = await self.users.get_by_id(user_id)
        if not user or not user.is_active:
            raise UnauthorizedError("Session is no longer valid.", error_code="INVALID_SESSION")

        memberships = await self.orgs.list_for_user(user.id)
        orgs_with_role = [(org, member.role.value) for org, member in memberships]
        return self._build_auth_response(user, orgs_with_role)

    def _build_auth_response(self, user: User, orgs_with_role: list[tuple]) -> tuple[AuthResponse, str]:
        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)

        response = AuthResponse(
            user=UserOut.model_validate(user),
            organizations=[
                OrganizationOut(id=org.id, name=org.name, slug=org.slug, role=role)
                for org, role in orgs_with_role
            ],
            access_token=access_token,
        )
        return response, refresh_token
