"""Deployment detail, releases, rollback, and metrics."""

from __future__ import annotations

import hashlib
import time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from devdeploy_api import github_service, pipeline
from devdeploy_api.deps import get_current_user, get_db
from devdeploy_api.models import DeploymentJob, Release, User
from devdeploy_api.project_service import get_project_for_user
from devdeploy_api.schemas import (
    AlertOut,
    DeployRequest,
    DeploymentJobOut,
    MetricsOut,
    ReleaseOut,
)

router = APIRouter(tags=["deployments"])


@router.get("/projects/{project_id}/deployments/{job_id}", response_model=DeploymentJobOut)
def get_deployment(
    project_id: UUID,
    job_id: UUID,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DeploymentJobOut:
    get_project_for_user(db, user, project_id)
    job = db.get(DeploymentJob, job_id)
    if job is None or job.project_id != project_id:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return DeploymentJobOut.model_validate(job)


@router.post(
    "/projects/{project_id}/deploy",
    response_model=DeploymentJobOut,
    status_code=201,
)
def deploy_project(
    project_id: UUID,
    body: DeployRequest | None = None,
    process: bool = Query(default=True),
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DeploymentJobOut:
    simulate = bool(body and body.simulate_failure)
    job = github_service.manual_deploy(
        db, user, project_id, simulate_failure=simulate
    )
    if process:
        # Synchronously drain for local demos / tests (worker also supported)
        pipeline.drain_queue(step_delay=0.05)
        db.expire_all()
        job = db.get(DeploymentJob, job.id) or job
    return DeploymentJobOut.model_validate(job)


@router.get("/projects/{project_id}/releases", response_model=list[ReleaseOut])
def list_releases(
    project_id: UUID,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ReleaseOut]:
    get_project_for_user(db, user, project_id)
    rows = db.execute(
        select(Release)
        .where(Release.project_id == project_id)
        .order_by(Release.created_at.desc())
    ).scalars().all()
    return [ReleaseOut.model_validate(r) for r in rows]


@router.post("/projects/{project_id}/rollback", response_model=ReleaseOut)
def rollback(
    project_id: UUID,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReleaseOut:
    get_project_for_user(db, user, project_id)
    try:
        release = pipeline.rollback_project(db, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ReleaseOut.model_validate(release)


@router.get("/projects/{project_id}/metrics", response_model=MetricsOut)
def project_metrics(
    project_id: UUID,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MetricsOut:
    project = get_project_for_user(db, user, project_id)
    seed = int(hashlib.sha256(str(project.id).encode()).hexdigest()[:8], 16)
    tick = int(time.time() // 15)
    return MetricsOut(
        project_id=project_id,
        cpu_percent=round(12 + (seed + tick) % 35 + (tick % 7) * 0.3, 1),
        memory_mib=round(180 + (seed % 90) + (tick % 11) * 1.5, 1),
        uptime_seconds=3600 + (tick * 15) % 86400,
        requests_per_minute=round(40 + (seed + tick) % 120 + (tick % 5) * 2.2, 1),
        source="mock",
    )


@router.get("/projects/{project_id}/alerts", response_model=list[AlertOut])
def project_alerts(
    project_id: UUID,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AlertOut]:
    get_project_for_user(db, user, project_id)
    return [
        AlertOut(
            id="cpu-high",
            severity="warning",
            title="CPU above soft limit",
            description="Mock alert — wire Prometheus Alertmanager in production.",
            firing=False,
        ),
        AlertOut(
            id="deploy-failed",
            severity="critical",
            title="Deployment failed",
            description="Fires when a job ends in failed without new healthy release.",
            firing=False,
        ),
    ]
