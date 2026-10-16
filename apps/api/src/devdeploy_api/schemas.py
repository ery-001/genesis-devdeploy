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


class OAuthProviderStatus(BaseModel):
    id: str
    configured: bool
    enabled: bool
    callback_url: str


class AuthConfigOut(BaseModel):
    mock_mode: bool
    providers: list[str]
    oauth_providers: list[OAuthProviderStatus] = []
    session_cookie: str


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=4000)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=4000)
    deploy_branch: str | None = Field(default=None, min_length=1, max_length=200)
    dockerfile_path: str | None = Field(default=None, max_length=255)


class ProjectOut(BaseModel):
    id: UUID
    organization_id: UUID
    owner_user_id: UUID
    name: str
    slug: str
    description: str | None = None
    github_installation_id: UUID | None = None
    github_repo_id: int | None = None
    github_repo_full_name: str | None = None
    default_branch: str | None = None
    deploy_branch: str | None = None
    dockerfile_path: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GitHubConfigOut(BaseModel):
    mock_mode: bool
    app_configured: bool
    app_slug: str
    install_url: str | None = None


class GitHubInstallationOut(BaseModel):
    id: UUID
    installation_id: int
    account_login: str
    account_type: str
    is_mock: bool
    organization_id: UUID | None = None

    model_config = {"from_attributes": True}


class GitHubRepoOut(BaseModel):
    id: int
    full_name: str
    name: str
    private: bool = False
    default_branch: str = "main"


class AttachRepoRequest(BaseModel):
    installation_id: UUID
    repo_id: int
    full_name: str = Field(min_length=1, max_length=255)
    default_branch: str | None = Field(default=None, max_length=200)
    deploy_branch: str | None = Field(default=None, max_length=200)


class DeploymentJobOut(BaseModel):
    id: UUID
    project_id: UUID
    status: str
    trigger: str
    git_ref: str | None = None
    commit_sha: str | None = None
    github_delivery_id: str | None = None
    message: str | None = None
    build_logs: str | None = None
    image_digest: str | None = None
    image_tag: str | None = None
    app_url: str | None = None
    simulate_failure: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DeployRequest(BaseModel):
    simulate_failure: bool = False


class ReleaseOut(BaseModel):
    id: UUID
    project_id: UUID
    deployment_job_id: UUID | None = None
    image_digest: str
    image_tag: str | None = None
    app_url: str | None = None
    status: str
    is_current: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MetricsOut(BaseModel):
    project_id: UUID
    cpu_percent: float
    memory_mib: float
    uptime_seconds: int
    requests_per_minute: float
    source: str = "mock"


class AlertOut(BaseModel):
    id: str
    severity: str
    title: str
    description: str
    firing: bool
