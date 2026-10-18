import secrets
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Request, Response
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user
from app.core.exceptions import UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    decode_token_payload,
)
from app.middleware.csrf import CSRF_COOKIE_NAME
from app.models.base import get_db
from app.models.user import User
from app.repositories.log_repository import LogRepository
from app.schemas.auth import (
    AuthResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    UserOut,
    VerifyEmailRequest,
)
from app.services.account_service import AccountService
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
ACCESS_COOKIE = "access_token"
COOKIE_KWARGS = dict(httponly=True, secure=settings.environment != "development", samesite="lax")


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        ACCESS_COOKIE, access_token, max_age=settings.access_token_expire_minutes * 60, **COOKIE_KWARGS
    )
    response.set_cookie(
        REFRESH_COOKIE, refresh_token, max_age=settings.refresh_token_expire_days * 86400, **COOKIE_KWARGS
    )
    # CSRF cookie is deliberately readable by frontend JS (not httpOnly) so it
    # can be echoed back in the X-CSRF-Token header on state-changing requests.
    response.set_cookie(
        CSRF_COOKIE_NAME,
        secrets.token_urlsafe(32),
        max_age=settings.refresh_token_expire_days * 86400,
        httponly=False,
        secure=settings.environment != "development",
        samesite="lax",
    )


@router.post("/register", response_model=AuthResponse)
async def register(payload: RegisterRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    auth_response, refresh_token = await AuthService(db).register(
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        organization_name=payload.organization_name,
        ip_address=request.client.host if request.client else None,
    )
    _set_auth_cookies(response, auth_response.access_token, refresh_token)
    return auth_response


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    auth_response, refresh_token = await AuthService(db).login(
        email=payload.email, password=payload.password,
        ip_address=request.client.host if request.client else None,
    )
    _set_auth_cookies(response, auth_response.access_token, refresh_token)
    return auth_response


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not refresh_token:
        raise UnauthorizedError("No refresh token provided.", error_code="NOT_AUTHENTICATED")
    try:
        payload = decode_token_payload(refresh_token, expected_type="refresh")
        user_id = UUID(payload["sub"])
    except (JWTError, ValueError, KeyError):
        raise UnauthorizedError("Invalid or expired refresh token.", error_code="INVALID_TOKEN")

    auth_response, new_refresh_token = await AuthService(db).refresh(user_id, token_payload=payload)
    _set_auth_cookies(response, auth_response.access_token, new_refresh_token)
    return auth_response

@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    access_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    # Best-effort audit log: only written if the access token is still valid;
    # an already-expired/invalid token still logs out cleanly (cookies cleared)
    # without raising, since logout should never fail for the user.
    if access_token:
        try:
            user_id = decode_token(access_token, expected_type="access")
            await LogRepository(db).record_audit(
                organization_id=None, user_id=user_id, action="user.logout",
                entity_type="user", entity_id=user_id,
                ip_address=request.client.host if request.client else None,
            )
            await db.commit()
        except (JWTError, ValueError):
            pass

    response.delete_cookie(ACCESS_COOKIE)
    response.delete_cookie(REFRESH_COOKIE)
    response.delete_cookie(CSRF_COOKIE_NAME)
    return {"success": True, "data": {"message": "Logged out."}}


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return current_user

def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    await AccountService(db).request_password_reset(email=payload.email, ip_address=_client_ip(request))
    # Same response whether or not the account exists.
    return {
        "success": True,
        "data": {"message": "If an account exists for that email, a reset link has been sent."},
    }


@router.post("/reset-password")
async def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    await AccountService(db).reset_password(
        token=payload.token, new_password=payload.new_password, ip_address=_client_ip(request)
    )
    response.delete_cookie(ACCESS_COOKIE)
    response.delete_cookie(REFRESH_COOKIE)
    response.delete_cookie(CSRF_COOKIE_NAME)
    return {"success": True, "data": {"message": "Password updated. Please log in with your new password."}}


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await AccountService(db).change_password(
        user=current_user, current_password=payload.current_password,
        new_password=payload.new_password, ip_address=_client_ip(request),
    )
    # Every older session was just invalidated; give this one fresh tokens so the user stays logged in.
    _set_auth_cookies(response, create_access_token(current_user.id), create_refresh_token(current_user.id))
    return {"success": True, "data": {"message": "Password changed."}}


@router.post("/verify-email/request")
async def request_email_verification(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    if current_user.email_verified_at is not None:
        return {"success": True, "data": {"message": "Your email is already verified."}}
    await AccountService(db).send_verification_email(user=current_user, enforce_cooldown=True)
    return {"success": True, "data": {"message": "Verification email sent."}}


@router.post("/verify-email/confirm")
async def confirm_email(
    payload: VerifyEmailRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    await AccountService(db).confirm_email(token=payload.token, ip_address=_client_ip(request))
    return {"success": True, "data": {"message": "Email verified."}}