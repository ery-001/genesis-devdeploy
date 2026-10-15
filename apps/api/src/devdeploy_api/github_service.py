"""GitHub App integration — mockable when credentials are missing."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from devdeploy_api.config import Settings
from devdeploy_api.models import (
    DeploymentJob,
    GitHubInstallation,
    OrganizationMember,
    Project,
    User,
    WebhookDelivery,
)
from devdeploy_api.project_service import ensure_personal_org, get_project_for_user
from devdeploy_api.redis_client import get_redis

MOCK_REPOS = [
    {
        "id": 1001,
        "full_name": "mock-org/sample-fastapi-app",
        "name": "sample-fastapi-app",
        "private": False,
        "default_branch": "main",
    },
    {
        "id": 1002,
        "full_name": "mock-org/billing-api",
        "name": "billing-api",
        "private": True,
        "default_branch": "main",
    },
    {
        "id": 1003,
        "full_name": "mock-org/docs-site",
        "name": "docs-site",
        "private": False,
        "default_branch": "main",
    },
]


def verify_webhook_signature(
    settings: Settings, body: bytes, signature_header: str | None
) -> None:
    if not signature_header or not signature_header.startswith("sha256="):
        raise HTTPException(status_code=401, detail="Missing webhook signature")
    secret = settings.github_app_webhook_secret.encode("utf-8")
    digest = hmac.new(secret, body, hashlib.sha256).hexdigest()
    expected = f"sha256={digest}"
    if not hmac.compare_digest(expected, signature_header):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


def list_installations_for_user(
    db: DbSession, user: User
) -> list[GitHubInstallation]:
    org_ids = db.execute(
        select(OrganizationMember.organization_id).where(
            OrganizationMember.user_id == user.id
        )
    ).scalars().all()
    stmt = select(GitHubInstallation).where(
        (GitHubInstallation.installed_by_user_id == user.id)
        | (GitHubInstallation.organization_id.in_(list(org_ids) or [uuid.uuid4()]))
    )
    return list(db.execute(stmt).scalars().unique().all())


def create_mock_installation(db: DbSession, user: User) -> GitHubInstallation:
    org = ensure_personal_org(db, user)
    existing = db.execute(
        select(GitHubInstallation)
        .where(GitHubInstallation.installed_by_user_id == user.id)
        .where(GitHubInstallation.is_mock.is_(True))
        .limit(1)
    ).scalar_one_or_none()
    if existing:
        return existing

    installation = GitHubInstallation(
        installation_id=9_000_000 + secrets.randbelow(100_000),
        account_login="mock-org",
        account_type="Organization",
        organization_id=org.id,
        installed_by_user_id=user.id,
        is_mock=True,
    )
    db.add(installation)
    db.commit()
    db.refresh(installation)
    return installation


def get_installation_for_user(
    db: DbSession, user: User, installation_uuid: uuid.UUID
) -> GitHubInstallation:
    installation = db.get(GitHubInstallation, installation_uuid)
    if installation is None:
        raise HTTPException(status_code=404, detail="Installation not found")
    allowed = list_installations_for_user(db, user)
    if installation.id not in {i.id for i in allowed}:
        raise HTTPException(status_code=404, detail="Installation not found")
    return installation


def list_repos_for_installation(
    settings: Settings,
    db: DbSession,
    user: User,
    installation_uuid: uuid.UUID,
) -> list[dict[str, Any]]:
    installation = get_installation_for_user(db, user, installation_uuid)
    if settings.effective_github_mock or installation.is_mock:
        return MOCK_REPOS
    # Real GitHub App installation token + list repos lands when credentials exist.
    raise HTTPException(
        status_code=501,
        detail="Real GitHub repo listing requires a configured GitHub App",
    )


def attach_repo_to_project(
    db: DbSession,
    user: User,
    project_id: uuid.UUID,
    *,
    installation_id: uuid.UUID,
    repo_id: int,
    full_name: str,
    default_branch: str | None,
    deploy_branch: str | None,
) -> Project:
    project = get_project_for_user(db, user, project_id)
    installation = get_installation_for_user(db, user, installation_id)
    project.github_installation_id = installation.id
    project.github_repo_id = repo_id
    project.github_repo_full_name = full_name
    project.default_branch = default_branch or "main"
    project.deploy_branch = deploy_branch or project.default_branch or "main"
    db.commit()
    db.refresh(project)
    return project


def enqueue_deployment(
    db: DbSession,
    project: Project,
    *,
    trigger: str,
    git_ref: str | None = None,
    commit_sha: str | None = None,
    delivery_id: str | None = None,
    message: str | None = None,
) -> DeploymentJob:
    if not project.github_repo_full_name:
        raise HTTPException(
            status_code=400,
            detail="Project has no GitHub repository attached",
        )
    job = DeploymentJob(
        project_id=project.id,
        status="queued",
        trigger=trigger,
        git_ref=git_ref or project.deploy_branch or project.default_branch or "main",
        commit_sha=commit_sha,
        github_delivery_id=delivery_id,
        message=message or "Queued for build (Milestone 3)",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    redis = get_redis()
    try:
        redis.lpush(
            "devdeploy:deployments",
            json.dumps(
                {
                    "id": str(job.id),
                    "project_id": str(project.id),
                    "status": job.status,
                    "trigger": job.trigger,
                    "git_ref": job.git_ref,
                }
            ),
        )
    finally:
        redis.close()
    return job


def list_deployments(db: DbSession, user: User, project_id: uuid.UUID) -> list[DeploymentJob]:
    get_project_for_user(db, user, project_id)
    return list(
        db.execute(
            select(DeploymentJob)
            .where(DeploymentJob.project_id == project_id)
            .order_by(DeploymentJob.created_at.desc())
        ).scalars().all()
    )


def manual_deploy(db: DbSession, user: User, project_id: uuid.UUID) -> DeploymentJob:
    project = get_project_for_user(db, user, project_id)
    return enqueue_deployment(
        db,
        project,
        trigger="manual",
        git_ref=project.deploy_branch or project.default_branch,
        message="Manual deploy requested",
    )


def record_webhook_delivery(db: DbSession, delivery_id: str, event: str) -> bool:
    """Return False if this delivery was already processed."""
    existing = db.execute(
        select(WebhookDelivery).where(WebhookDelivery.delivery_id == delivery_id)
    ).scalar_one_or_none()
    if existing:
        return False
    db.add(WebhookDelivery(delivery_id=delivery_id, event=event))
    db.commit()
    return True


def handle_push_event(db: DbSession, payload: dict[str, Any], delivery_id: str) -> DeploymentJob | None:
    repo = payload.get("repository") or {}
    full_name = repo.get("full_name")
    if not full_name:
        return None
    ref = payload.get("ref") or ""
    branch = ref.removeprefix("refs/heads/") if ref.startswith("refs/heads/") else None
    if not branch:
        return None

    projects = list(
        db.execute(
            select(Project).where(Project.github_repo_full_name == full_name)
        ).scalars().all()
    )
    created: DeploymentJob | None = None
    for project in projects:
        deploy_branch = project.deploy_branch or project.default_branch or "main"
        if branch != deploy_branch:
            continue
        head = (payload.get("head_commit") or {}).get("id") or payload.get("after")
        created = enqueue_deployment(
            db,
            project,
            trigger="webhook_push",
            git_ref=branch,
            commit_sha=head,
            delivery_id=delivery_id,
            message=f"Push to {branch}",
        )
    return created


def install_url(settings: Settings) -> str | None:
    if settings.effective_github_mock:
        return None
    slug = settings.github_app_slug or "your-app"
    return f"https://github.com/apps/{slug}/installations/new"
