"""Pydantic request/response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserOut(BaseModel):
    id: UUID
    email: str | None = None
    phone: str | None = None
    display_name: str | None = None
    avatar_url: str | None = None
    providers: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class MagicLinkRequest(BaseModel):
    email: EmailStr


class MagicLinkVerifyRequest(BaseModel):
    token: str = Field(min_length=8, max_length=256)


class PhoneStartRequest(BaseModel):
    phone: str = Field(min_length=8, max_length=32)


class PhoneVerifyRequest(BaseModel):
    phone: str = Field(min_length=8, max_length=32)
    code: str = Field(min_length=4, max_length=12)


class MessageOut(BaseModel):
    message: str
    mock: bool = False
    # Dev-only fields returned when auth_mock_mode is on
    magic_link_token: str | None = None
    otp_hint: str | None = None


class AuthConfigOut(BaseModel):
    mock_mode: bool
    providers: list[str]
    session_cookie: str


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=4000)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=4000)


class ProjectOut(BaseModel):
    id: UUID
    organization_id: UUID
    owner_user_id: UUID
    name: str
    slug: str
    description: str | None = None
    github_repo_full_name: str | None = None
    default_branch: str | None = None
    dockerfile_path: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
