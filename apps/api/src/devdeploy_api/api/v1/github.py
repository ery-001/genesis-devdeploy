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
    GitHubConfigOut,
    GitHubInstallationOut,
    GitHubRepoOut,
)

router = APIRouter(prefix="/github", tags=["github"])


@router.get("/config", response_model=GitHubConfigOut)
def github_config(settings: Settings = Depends(get_settings)) -> GitHubConfigOut:
    return GitHubConfigOut(
        mock_mode=settings.effective_github_mock,
        app_configured=settings.github_app_configured,
        app_slug=settings.github_app_slug,
        install_url=github_service.install_url(settings),
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
    if not settings.effective_github_mock:
        # Still allow mock helper for local demos even if misconfigured
        pass
    installation = github_service.create_mock_installation(db, user)
    return GitHubInstallationOut.model_validate(installation)


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
