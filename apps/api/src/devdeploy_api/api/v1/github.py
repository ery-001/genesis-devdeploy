"""GitHub App installation and repository listing."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from devdeploy_api import github_service
from devdeploy_api.config import Settings, get_settings
from devdeploy_api.deps import get_current_user, get_db
from devdeploy_api.models import User
from devdeploy_api.schemas import (
    GitHubBranchOut,
    GitHubConfigOut,
    GitHubInstallationOut,
    GitHubRepoOut,
)

router = APIRouter(prefix="/github", tags=["github"])


@router.get("/config", response_model=GitHubConfigOut)
def github_config(settings: Settings = Depends(get_settings)) -> GitHubConfigOut:
    callback = f"{settings.api_public_url.rstrip('/')}/api/v1/webhooks/github"
    return GitHubConfigOut(
        mock_mode=settings.effective_github_mock,
        app_configured=settings.github_app_configured,
        app_slug=settings.github_app_slug,
        install_url=github_service.install_url(settings),
        webhook_callback_hint=callback,
    )


@router.get("/installations", response_model=list[GitHubInstallationOut])
def list_installations(
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[GitHubInstallationOut]:
    return [
        GitHubInstallationOut.model_validate(i)
        for i in github_service.list_installations_for_user(db, user)
    ]


@router.post(
    "/installations/mock",
    response_model=GitHubInstallationOut,
)
def mock_install(
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> GitHubInstallationOut:
    # Always available for local demos even when a real App is configured.
    _ = settings
    installation = github_service.create_mock_installation(db, user)
    return GitHubInstallationOut.model_validate(installation)


@router.post(
    "/installations/sync",
    response_model=list[GitHubInstallationOut],
)
def sync_installations(
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> list[GitHubInstallationOut]:
    """Sync installations from the real GitHub App (requires App credentials)."""
    rows = github_service.sync_real_installations(settings, db, user)
    return [GitHubInstallationOut.model_validate(i) for i in rows]


@router.get(
    "/installations/{installation_id}/repos",
    response_model=list[GitHubRepoOut],
)
def list_repos(
    installation_id: UUID,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> list[GitHubRepoOut]:
    repos = github_service.list_repos_for_installation(
        settings, db, user, installation_id
    )
    return [GitHubRepoOut.model_validate(r) for r in repos]


@router.get(
    "/installations/{installation_id}/repos/{owner}/{repo}/branches",
    response_model=list[GitHubBranchOut],
)
def list_repo_branches(
    installation_id: UUID,
    owner: str,
    repo: str,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> list[GitHubBranchOut]:
    branches = github_service.list_branches_for_repo(
        settings,
        db,
        user,
        installation_id,
        owner=owner,
        repo=repo,
    )
    return [GitHubBranchOut.model_validate(b) for b in branches]
