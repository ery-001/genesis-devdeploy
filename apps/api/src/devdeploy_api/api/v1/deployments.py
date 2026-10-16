"""Deployment detail, releases, rollback, cancel, metrics, logs, approvals."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from devdeploy_api import github_service, k8s_engine, pipeline
from devdeploy_api.access_restore import restore_project_access
from devdeploy_api.audit import write_audit
from devdeploy_api.config import get_settings
from devdeploy_api.db import SessionLocal
from devdeploy_api.deps import get_current_user, get_db
from devdeploy_api.models import DeploymentApproval, DeploymentJob, Release, User
from devdeploy_api.project_service import get_project_for_user
from devdeploy_api.rbac import require_project_role
from devdeploy_api.schemas import (
    AlertOut,
    ApprovalDecide,
    ApprovalOut,
    DeployRequest,
    DeploymentJobOut,
    LogLineOut,
    MetricPoint,
    MetricsOut,
    ReleaseOut,
)

router = APIRouter(tags=["deployments"])

_TERMINAL = frozenset({"succeeded", "failed", "cancelled", "rolled_back"})


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


@router.get("/projects/{project_id}/deployments/{job_id}/stream")
async def stream_deployment_logs(
    project_id: UUID,
    job_id: UUID,
    request: Request,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """SSE stream of build_logs + status until the job reaches a terminal state."""
    get_project_for_user(db, user, project_id)
    job = db.get(DeploymentJob, job_id)
    if job is None or job.project_id != project_id:
        raise HTTPException(status_code=404, detail="Deployment not found")

    async def event_gen():
        last_len = -1
        last_status = None
        # Use a fresh session inside the generator (request session closes after return).
        while True:
            if await request.is_disconnected():
                break
            session = SessionLocal()
            try:
                row = session.get(DeploymentJob, job_id)
                if row is None:
                    yield f"event: error\ndata: {json.dumps({'detail': 'gone'})}\n\n"
                    break
                logs = row.build_logs or ""
                status = row.status
                if len(logs) != last_len or status != last_status:
                    payload = {
                        "status": status,
                        "message": row.message,
                        "build_logs": logs,
                        "app_url": row.app_url,
                        "public_url": row.public_url,
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
                    last_len = len(logs)
                    last_status = status
                if status in _TERMINAL:
                    yield f"event: done\ndata: {json.dumps({'status': status})}\n\n"
                    break
            finally:
                session.close()
            await asyncio.sleep(0.6)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
    environment = (body.environment if body else None) or "development"
    job = github_service.manual_deploy(
        db,
        user,
        project_id,
        simulate_failure=simulate,
        environment_name=environment,
    )
    if process and job.status == "queued":
        pipeline.drain_queue(step_delay=0.05)
        db.expire_all()
        job = db.get(DeploymentJob, job.id) or job
    return DeploymentJobOut.model_validate(job)


@router.post(
    "/projects/{project_id}/deployments/{job_id}/cancel",
    response_model=DeploymentJobOut,
)
def cancel_deployment(
    project_id: UUID,
    job_id: UUID,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DeploymentJobOut:
    project = get_project_for_user(db, user, project_id)
    require_project_role(db, user, project, "developer")
    job = db.get(DeploymentJob, job_id)
    if job is None or job.project_id != project_id:
        raise HTTPException(status_code=404, detail="Deployment not found")
    try:
        job = pipeline.cancel_job(db, job)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    write_audit(
        db,
        organization_id=project.organization_id,
        actor=user,
        action="deployment.cancel",
        resource_type="deployment",
        resource_id=str(job.id),
        commit=True,
    )
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
    project = get_project_for_user(db, user, project_id)
    require_project_role(db, user, project, "developer")
    try:
        release = pipeline.rollback_project(db, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    write_audit(
        db,
        organization_id=project.organization_id,
        actor=user,
        action="deployment.rollback",
        resource_type="release",
        resource_id=str(release.id),
        commit=True,
    )
    return ReleaseOut.model_validate(release)


@router.post("/projects/{project_id}/access/restore", response_model=ReleaseOut)
def restore_access(
    project_id: UUID,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReleaseOut:
    """Re-attach local port-forward + public tunnel without a full redeploy."""
    get_project_for_user(db, user, project_id)
    try:
        restore_project_access(db, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    release = db.execute(
        select(Release)
        .where(Release.project_id == project_id)
        .where(Release.is_current.is_(True))
        .limit(1)
    ).scalar_one_or_none()
    if release is None:
        raise HTTPException(status_code=404, detail="No current release")
    return ReleaseOut.model_validate(release)


@router.get("/projects/{project_id}/metrics", response_model=MetricsOut)
def project_metrics(
    project_id: UUID,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MetricsOut:
    project = get_project_for_user(db, user, project_id)
    seed = int(hashlib.sha256(str(project.id).encode()).hexdigest()[:8], 16)
    now = int(time.time())
    tick = now // 15

    current = db.execute(
        select(Release)
        .where(Release.project_id == project_id)
        .where(Release.is_current.is_(True))
        .limit(1)
    ).scalar_one_or_none()
    if current and current.created_at:
        created = current.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        uptime = max(0, int((datetime.now(UTC) - created).total_seconds()))
        source = "release-derived"
    else:
        uptime = 3600 + (tick * 15) % 86400
        source = "synthetic"

    cpu = round(12 + (seed + tick) % 35 + (tick % 7) * 0.3, 1)
    mem = round(180 + (seed % 90) + (tick % 11) * 1.5, 1)
    rpm = round(40 + (seed + tick) % 120 + (tick % 5) * 2.2, 1)

    series: dict[str, list[MetricPoint]] = {"cpu": [], "memory": [], "rpm": []}
    for i in range(24):
        t = now - (23 - i) * 60
        series["cpu"].append(
            MetricPoint(t=t, v=round(10 + (seed + i * 3) % 40 + (i % 5) * 0.4, 1))
        )
        series["memory"].append(
            MetricPoint(t=t, v=round(160 + (seed % 80) + i * 1.2, 1))
        )
        series["rpm"].append(
            MetricPoint(t=t, v=round(30 + (seed + i * 7) % 100, 1))
        )

    return MetricsOut(
        project_id=project_id,
        cpu_percent=cpu,
        memory_mib=mem,
        uptime_seconds=uptime,
        requests_per_minute=rpm,
        source=source,
        series=series,
    )


@router.get("/projects/{project_id}/alerts", response_model=list[AlertOut])
def project_alerts(
    project_id: UUID,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AlertOut]:
    get_project_for_user(db, user, project_id)
    recent_fail = db.execute(
        select(DeploymentJob)
        .where(DeploymentJob.project_id == project_id)
        .where(DeploymentJob.status == "failed")
        .order_by(DeploymentJob.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    return [
        AlertOut(
            id="cpu-high",
            severity="warning",
            title="CPU above soft limit",
            description="Soft alert from synthetic series — wire Alertmanager in production.",
            firing=False,
        ),
        AlertOut(
            id="deploy-failed",
            severity="critical",
            title="Deployment failed",
            description="Fires when the latest job ended in failed.",
            firing=bool(recent_fail),
        ),
    ]


@router.get("/projects/{project_id}/logs", response_model=LogLineOut)
def project_logs(
    project_id: UUID,
    tail: int = Query(default=200, ge=10, le=2000),
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LogLineOut:
    project = get_project_for_user(db, user, project_id)
    lines, source = k8s_engine.fetch_pod_logs(
        get_settings(), project_slug=project.slug, tail=tail
    )
    return LogLineOut(lines=lines, source=source, truncated=len(lines) >= tail)


@router.get(
    "/projects/{project_id}/approvals",
    response_model=list[ApprovalOut],
)
def list_approvals(
    project_id: UUID,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ApprovalOut]:
    get_project_for_user(db, user, project_id)
    jobs = db.execute(
        select(DeploymentJob.id).where(DeploymentJob.project_id == project_id)
    ).scalars().all()
    if not jobs:
        return []
    rows = db.execute(
        select(DeploymentApproval)
        .where(DeploymentApproval.deployment_job_id.in_(list(jobs)))
        .order_by(DeploymentApproval.created_at.desc())
    ).scalars().all()
    return [ApprovalOut.model_validate(r) for r in rows]


@router.post(
    "/projects/{project_id}/deployments/{job_id}/approve",
    response_model=DeploymentJobOut,
)
def approve_deployment(
    project_id: UUID,
    job_id: UUID,
    body: ApprovalDecide | None = None,
    process: bool = Query(default=True),
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DeploymentJobOut:
    project = get_project_for_user(db, user, project_id)
    require_project_role(db, user, project, "admin")
    job = db.get(DeploymentJob, job_id)
    if job is None or job.project_id != project_id:
        raise HTTPException(status_code=404, detail="Deployment not found")
    approval = db.execute(
        select(DeploymentApproval).where(
            DeploymentApproval.deployment_job_id == job.id
        )
    ).scalar_one_or_none()
    if approval is None or approval.status != "pending":
        raise HTTPException(status_code=400, detail="No pending approval")
    approval.status = "approved"
    approval.decided_by_user_id = user.id
    approval.decided_at = datetime.now(UTC)
    approval.note = body.note if body else None
    job.status = "queued"
    job.message = "Approved — queued for pipeline"
    db.commit()
    pipeline.queue_job_id(job.id)
    if process:
        pipeline.drain_queue(step_delay=0.05)
        db.expire_all()
        job = db.get(DeploymentJob, job.id) or job
    return DeploymentJobOut.model_validate(job)


@router.post(
    "/projects/{project_id}/deployments/{job_id}/reject",
    response_model=DeploymentJobOut,
)
def reject_deployment(
    project_id: UUID,
    job_id: UUID,
    body: ApprovalDecide | None = None,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DeploymentJobOut:
    project = get_project_for_user(db, user, project_id)
    require_project_role(db, user, project, "admin")
    job = db.get(DeploymentJob, job_id)
    if job is None or job.project_id != project_id:
        raise HTTPException(status_code=404, detail="Deployment not found")
    approval = db.execute(
        select(DeploymentApproval).where(
            DeploymentApproval.deployment_job_id == job.id
        )
    ).scalar_one_or_none()
    if approval is None or approval.status != "pending":
        raise HTTPException(status_code=400, detail="No pending approval")
    approval.status = "rejected"
    approval.decided_by_user_id = user.id
    approval.decided_at = datetime.now(UTC)
    approval.note = body.note if body else None
    job.status = "failed"
    job.message = "Rejected by approver"
    db.commit()
    db.refresh(job)
    return DeploymentJobOut.model_validate(job)
