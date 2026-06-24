from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(alias="refreshToken")

    model_config = ConfigDict(populate_by_name=True)


class LogoutRequest(BaseModel):
    refresh_token: str | None = Field(default=None, alias="refreshToken")

    model_config = ConfigDict(populate_by_name=True)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(alias="currentPassword", min_length=1)
    new_password: str = Field(alias="newPassword", min_length=8)

    model_config = ConfigDict(populate_by_name=True)


class TokenPair(BaseModel):
    access_token: str = Field(alias="accessToken")
    refresh_token: str = Field(alias="refreshToken")
    token_type: str = Field(default="bearer", alias="tokenType")

    model_config = ConfigDict(populate_by_name=True)


class UserMe(BaseModel):
    id: UUID
    email: EmailStr
    name: str
    organization_id: UUID | None = Field(default=None, alias="organizationId")
    role_codes: list[str] = Field(alias="roleCodes")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class LoginResponse(TokenPair):
    user: UserMe
