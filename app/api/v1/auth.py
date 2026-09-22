import secrets

from fastapi import APIRouter, Cookie, Depends, Request, Response
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user
from app.core.exceptions import UnauthorizedError
from app.core.security import decode_token
from app.middleware.csrf import CSRF_COOKIE_NAME
from app.models.base import get_db
from app.models.user import User
from app.repositories.log_repository import LogRepository
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserOut
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
        user_id = decode_token(refresh_token, expected_type="refresh")
    except (JWTError, ValueError):
        raise UnauthorizedError("Invalid or expired refresh token.", error_code="INVALID_TOKEN")

    auth_response, new_refresh_token = await AuthService(db).refresh(user_id)
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
