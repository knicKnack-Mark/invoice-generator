from uuid import UUID

from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    organization_name: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    is_active: bool
    email_verified_at: datetime | None = None

    model_config = {"from_attributes": True}


class OrganizationOut(BaseModel):
    id: UUID
    name: str
    slug: str
    role: str

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    user: UserOut
    organizations: list[OrganizationOut]
    access_token: str


class RefreshRequest(BaseModel):
    refresh_token: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    new_password: str = Field(min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)