import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from html import escape
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.security import hash_password, verify_password
from app.integrations import login_lockout
from app.integrations.email import email_backend
from app.models.auth_token import PURPOSE_EMAIL_VERIFICATION, PURPOSE_PASSWORD_RESET
from app.models.user import User
from app.repositories.auth_token_repository import AuthTokenRepository
from app.repositories.log_repository import LogRepository
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

INVALID_TOKEN_MESSAGE = "This link is invalid or has expired. Please request a new one."


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class AccountService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.users = UserRepository(db)
        self.tokens = AuthTokenRepository(db)
        self.logs = LogRepository(db)

    async def _issue_token(self, *, user_id: UUID, purpose: str, ttl: timedelta) -> str:
        # Only the newest link works; issuing a new one cancels older unused ones.
        await self.tokens.invalidate_unused(user_id=user_id, purpose=purpose)
        raw = secrets.token_urlsafe(32)
        await self.tokens.create(
            user_id=user_id, purpose=purpose, token_hash=_hash_token(raw),
            expires_at=datetime.now(timezone.utc) + ttl,
        )
        return raw

    async def _send_safely(self, *, to: str, subject: str, html_body: str) -> None:
        """A failed send must never change the response: if it errored only for
        real accounts it would reveal which emails are registered."""
        try:
            await email_backend.send(to=to, subject=subject, html_body=html_body)
        except Exception:
            logger.exception("Failed to send account email (%s)", subject)

    # ---- email verification ----

    async def send_verification_email(self, *, user: User, enforce_cooldown: bool = False) -> None:
        cooldown = timedelta(seconds=settings.account_email_cooldown_seconds)
        if enforce_cooldown and await self.tokens.has_recent(
            user_id=user.id, purpose=PURPOSE_EMAIL_VERIFICATION, within=cooldown
        ):
            raise AppError(
                "Please wait a minute before requesting another email.",
                error_code="EMAIL_COOLDOWN", status_code=429,
            )

        raw = await self._issue_token(
            user_id=user.id, purpose=PURPOSE_EMAIL_VERIFICATION,
            ttl=timedelta(hours=settings.email_verification_token_hours),
        )
        await self.db.commit()

        link = f"{settings.frontend_base_url}/verify-email?token={raw}"
        await self._send_safely(
            to=user.email,
            subject=f"Verify your email for {settings.app_name}",
            html_body=(
                f"<p>Welcome to {escape(settings.app_name)}! Please confirm your email address.</p>"
                f'<p><a href="{link}">Verify my email</a></p>'
                f"<p>This link expires in {settings.email_verification_token_hours} hours.</p>"
            ),
        )

    async def confirm_email(self, *, token: str, ip_address: str | None = None) -> None:
        user_id = await self.tokens.consume(purpose=PURPOSE_EMAIL_VERIFICATION, token_hash=_hash_token(token))
        if not user_id:
            raise AppError(INVALID_TOKEN_MESSAGE, error_code="INVALID_OR_EXPIRED_TOKEN")
        user = await self.users.get_by_id(user_id)
        if not user or not user.is_active:
            raise AppError(INVALID_TOKEN_MESSAGE, error_code="INVALID_OR_EXPIRED_TOKEN")

        if user.email_verified_at is None:
            user.email_verified_at = datetime.now(timezone.utc)
        await self.logs.record_audit(
            organization_id=None, user_id=user.id, action="user.email_verified",
            entity_type="user", entity_id=user.id, ip_address=ip_address,
        )
        await self.db.commit()

    # ---- password reset ----

    async def request_password_reset(self, *, email: str, ip_address: str | None = None) -> None:
        """Always returns normally. Unknown email, inactive account, or a
        request inside the cooldown window all do nothing visible, so callers
        can't use this to discover which emails have accounts."""
        user = await self.users.get_by_email(email)
        if not user or not user.is_active:
            return
        cooldown = timedelta(seconds=settings.account_email_cooldown_seconds)
        if await self.tokens.has_recent(user_id=user.id, purpose=PURPOSE_PASSWORD_RESET, within=cooldown):
            return  # stops someone from flooding a victim's inbox with reset emails

        raw = await self._issue_token(
            user_id=user.id, purpose=PURPOSE_PASSWORD_RESET,
            ttl=timedelta(minutes=settings.password_reset_token_minutes),
        )
        await self.logs.record_audit(
            organization_id=None, user_id=user.id, action="user.password_reset_requested",
            entity_type="user", entity_id=user.id, ip_address=ip_address,
        )
        await self.db.commit()

        link = f"{settings.frontend_base_url}/reset-password?token={raw}"
        await self._send_safely(
            to=user.email,
            subject=f"Reset your {settings.app_name} password",
            html_body=(
                f"<p>We received a request to reset your {escape(settings.app_name)} password.</p>"
                f'<p><a href="{link}">Reset my password</a></p>'
                f"<p>This link expires in {settings.password_reset_token_minutes} minutes. "
                "If you didn't request this, you can safely ignore this email.</p>"
            ),
        )

    async def reset_password(self, *, token: str, new_password: str, ip_address: str | None = None) -> None:
        user_id = await self.tokens.consume(purpose=PURPOSE_PASSWORD_RESET, token_hash=_hash_token(token))
        if not user_id:
            raise AppError(INVALID_TOKEN_MESSAGE, error_code="INVALID_OR_EXPIRED_TOKEN")
        user = await self.users.get_by_id(user_id)
        if not user or not user.is_active:
            raise AppError(INVALID_TOKEN_MESSAGE, error_code="INVALID_OR_EXPIRED_TOKEN")

        user.password_hash = hash_password(new_password)
        user.password_changed_at = datetime.now(timezone.utc)  # invalidates every existing session
        await self.tokens.invalidate_unused(user_id=user.id, purpose=PURPOSE_PASSWORD_RESET)
        await self.logs.record_audit(
            organization_id=None, user_id=user.id, action="user.password_reset_completed",
            entity_type="user", entity_id=user.id, ip_address=ip_address,
        )
        await self.db.commit()
        # The lockout message tells locked-out users to reset their password, so it should work.
        await login_lockout.clear_failed_attempts(user.email)

    # ---- change password (logged in) ----

    async def change_password(
        self, *, user: User, current_password: str, new_password: str, ip_address: str | None = None
    ) -> None:
        if not verify_password(current_password, user.password_hash):
            raise AppError("Current password is incorrect.", error_code="INVALID_CURRENT_PASSWORD")
        if verify_password(new_password, user.password_hash):
            raise AppError("New password must be different from the current one.", error_code="PASSWORD_UNCHANGED")

        user.password_hash = hash_password(new_password)
        user.password_changed_at = datetime.now(timezone.utc)
        await self.tokens.invalidate_unused(user_id=user.id, purpose=PURPOSE_PASSWORD_RESET)
        await self.logs.record_audit(
            organization_id=None, user_id=user.id, action="user.password_changed",
            entity_type="user", entity_id=user.id, ip_address=ip_address,
        )
        await self.db.commit()