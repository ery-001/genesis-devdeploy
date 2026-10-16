"""Pydantic request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
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
    magic_link_token: str | None = None
    otp_hint: str | None = None


class OAuthProviderStatus(BaseModel):
    id: str
    configured: bool
    enabled: bool
    callback_url: str
    callback_urls: list[str] = []


class AuthConfigOut(BaseModel):
    mock_mode: bool
    providers: list[str]
    oauth_providers: list[OAuthProviderStatus] = []
    session_cookie: str
    oauth_callback_urls: list[str] = []


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
    container_port: int | None = Field(default=None, ge=1, le=65535)
    health_path: str | None = Field(default=None, max_length=255)
    cpu_request: str | None = Field(default=None, max_length=32)
    memory_request: str | None = Field(default=None, max_length=32)
    cpu_limit: str | None = Field(default=None, max_length=32)
    memory_limit: str | None = Field(default=None, max_length=32)
    auto_deploy: bool | None = None
    replicas: int | None = Field(default=None, ge=1, le=20)
    approval_required_prod: bool | None = None


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
    container_port: int = 8000
    health_path: str = "/health"
    cpu_request: str = "100m"
    memory_request: str = "128Mi"
    cpu_limit: str = "500m"
    memory_limit: str = "512Mi"
    auto_deploy: bool = True
    replicas: int = 1
    approval_required_prod: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GitHubConfigOut(BaseModel):
    mock_mode: bool
    app_configured: bool
    app_slug: str
    install_url: str | None = None
    webhook_callback_hint: str | None = None


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


class GitHubBranchOut(BaseModel):
    name: str
    protected: bool = False


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
    public_url: str | None = None
    simulate_failure: bool = False
    environment_name: str = "development"
    runtime_slug: str | None = None
    cancelled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DeployRequest(BaseModel):
    simulate_failure: bool = False
    environment: str = Field(default="development", max_length=64)


class ReleaseOut(BaseModel):
    id: UUID
    project_id: UUID
    deployment_job_id: UUID | None = None
    image_digest: str
    image_tag: str | None = None
    app_url: str | None = None
    public_url: str | None = None
    status: str
    is_current: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MetricPoint(BaseModel):
    t: int
    v: float


class MetricsOut(BaseModel):
    project_id: UUID
    cpu_percent: float
    memory_mib: float
    uptime_seconds: int
    requests_per_minute: float
    source: str = "synthetic"
    series: dict[str, list[MetricPoint]] = Field(default_factory=dict)


class AlertOut(BaseModel):
    id: str
    severity: str
    title: str
    description: str
    firing: bool


class VariableCreate(BaseModel):
    key: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    value: str = Field(min_length=0, max_length=8000)
    is_secret: bool = True
    environment_name: str = Field(default="development", max_length=64)


class VariableUpdate(BaseModel):
    value: str | None = Field(default=None, max_length=8000)
    is_secret: bool | None = None


class VariableOut(BaseModel):
    id: UUID
    project_id: UUID
    key: str
    is_secret: bool
    environment_name: str
    value_preview: str
    created_at: datetime
    updated_at: datetime


class DevDeployYamlValidateRequest(BaseModel):
    yaml_text: str = Field(min_length=1, max_length=100_000)


class DevDeployYamlValidateOut(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    parsed: dict[str, Any] = Field(default_factory=dict)


class DevDeployYamlApplyRequest(BaseModel):
    yaml_text: str = Field(min_length=1, max_length=100_000)


class EnvironmentOut(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    deploy_branch: str | None = None
    replicas: int
    approval_required: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class EnvironmentUpdate(BaseModel):
    deploy_branch: str | None = Field(default=None, max_length=200)
    replicas: int | None = Field(default=None, ge=1, le=20)
    approval_required: bool | None = None


class MemberInvite(BaseModel):
    email: EmailStr
    role: str = Field(default="developer", pattern=r"^(owner|admin|developer|viewer)$")


class MemberOut(BaseModel):
    id: UUID
    user_id: UUID
    email: str | None = None
    display_name: str | None = None
    role: str
    created_at: datetime


class MemberRoleUpdate(BaseModel):
    role: str = Field(pattern=r"^(owner|admin|developer|viewer)$")


class ApprovalOut(BaseModel):
    id: UUID
    deployment_job_id: UUID
    status: str
    note: str | None = None
    created_at: datetime
    decided_at: datetime | None = None

    model_config = {"from_attributes": True}


class ApprovalDecide(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class NotificationConfigIn(BaseModel):
    kind: str = Field(pattern=r"^(email|webhook)$")
    enabled: bool = True
    target: str = Field(min_length=1, max_length=512)


class NotificationConfigOut(BaseModel):
    id: UUID
    organization_id: UUID
    kind: str
    enabled: bool
    target: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ScanOut(BaseModel):
    id: UUID
    project_id: UUID
    deployment_job_id: UUID | None = None
    image_digest: str | None = None
    status: str
    critical: int
    high: int
    medium: int
    low: int
    scanner: str
    report: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ResourceQuotaOut(BaseModel):
    project_id: UUID
    cpu_request: str
    memory_request: str
    cpu_limit: str
    memory_limit: str
    replicas: int
    namespace: str


class LogLineOut(BaseModel):
    lines: list[str]
    source: str
    truncated: bool = False


class AuditLogOut(BaseModel):
    id: UUID
    organization_id: UUID
    actor_user_id: UUID | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    detail: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ApiKeyCreatedOut(BaseModel):
    id: UUID
    name: str
    token: str
    token_prefix: str
    created_at: datetime


class ApiKeyOut(BaseModel):
    id: UUID
    name: str
    token_prefix: str
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PreviewCreate(BaseModel):
    pr_number: int = Field(ge=1, le=999999)


class PreviewOut(BaseModel):
    id: UUID
    project_id: UUID
    pr_number: int
    status: str
    preview_url: str | None = None
    message: str | None = None
    deployment_job_id: UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class StubFeatureOut(BaseModel):
    feature: str
    enabled: bool
    status: str
    config: dict[str, Any] = Field(default_factory=dict)
    coming_soon_reason: str | None = None


class StubFeatureUpdate(BaseModel):
    enabled: bool | None = None
    config: dict[str, Any] | None = None


class BillingUsageOut(BaseModel):
    build_minutes: float
    deploy_count: int
    bandwidth_gb: float
    seats: int
    plan: str = "local-free"


class AnalyticsOut(BaseModel):
    project_id: UUID
    deploy_success_rate: float
    mean_deploy_seconds: float
    deploys_last_7d: int
    rollbacks_last_7d: int


class PlatformFlagsOut(BaseModel):
    multi_cloud_enabled: bool
    ha_enabled: bool
    aws_mock_mode: bool
