"""Re-attach local port-forwards and public tunnels for current releases."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from devdeploy_api.config import Settings, get_settings
from devdeploy_api.db import SessionLocal
from devdeploy_api.k8s_engine import (
    AccessResult,
    effective_k8s_mock,
    ensure_app_access,
    kubectl_available,
)
from devdeploy_api.models import DeploymentJob, Project, Release

log = logging.getLogger(__name__)


def _apply_access(
    db: DbSession,
    *,
    release: Release,
    access: AccessResult,
    settings: Settings,
) -> None:
    release.app_url = access.app_url
    if access.public_url:
        release.public_url = access.public_url
    elif settings.public_tunnel_enabled:
        # Clear stale trycloudflare links so the UI does not show a dead share URL.
        release.public_url = None
    if release.deployment_job_id:
        job = db.get(DeploymentJob, release.deployment_job_id)
        if job is not None:
            job.app_url = release.app_url
            job.public_url = release.public_url


def restore_project_access(
    db: DbSession,
    project_id: uuid.UUID,
    settings: Settings | None = None,
) -> AccessResult:
    """Restore port-forward + tunnel for a project's current healthy release."""
    settings = settings or get_settings()
    project = db.get(Project, project_id)
    if project is None:
        raise ValueError("Project not found")
    release = db.execute(
        select(Release)
        .where(Release.project_id == project_id)
        .where(Release.is_current.is_(True))
        .where(Release.status == "healthy")
        .limit(1)
    ).scalar_one_or_none()
    if release is None:
        raise ValueError("No current healthy release to restore")

    access = ensure_app_access(settings, project_slug=project.slug)
    _apply_access(db, release=release, access=access, settings=settings)
    db.commit()
    db.refresh(release)
    return access


def restore_current_releases(settings: Settings | None = None) -> list[str]:
    """Restore host access for every healthy current release (API startup)."""
    settings = settings or get_settings()
    summary: list[str] = []
    if effective_k8s_mock(settings):
        summary.append("K8S_MOCK_MODE=true — skip access restore")
        return summary
    if not kubectl_available(settings):
        summary.append("kubectl/cluster unavailable — skip access restore")
        return summary

    db = SessionLocal()
    try:
        rows = db.execute(
            select(Release, Project)
            .join(Project, Project.id == Release.project_id)
            .where(Release.is_current.is_(True))
            .where(Release.status == "healthy")
            .order_by(Release.created_at.desc())
        ).all()
        if not rows:
            summary.append("No current healthy releases to restore")
            return summary

        for release, project in rows:
            try:
                access = ensure_app_access(settings, project_slug=project.slug)
                _apply_access(db, release=release, access=access, settings=settings)
                db.commit()
                msg = f"Restored {project.slug} → {access.app_url}"
                if access.public_url:
                    msg += f" · share {access.public_url}"
                elif settings.public_tunnel_enabled:
                    msg += " · share URL unavailable (see logs)"
                summary.append(msg)
                log.info("%s", msg)
                for line in access.logs:
                    if line.startswith("ERROR"):
                        log.warning("[%s] %s", project.slug, line)
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                err = f"Failed to restore access for {project.slug}: {exc}"
                summary.append(err)
                log.exception("%s", err)
        return summary
    finally:
        db.close()
