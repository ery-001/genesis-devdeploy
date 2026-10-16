"""V2 monitoring extras + V3 stubs (billing, DB, buildpacks, tracing, HA…)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from devdeploy_api.config import Settings, get_settings
from devdeploy_api.deps import get_current_user, get_db
from devdeploy_api.models import (
    DeploymentJob,
    PlatformStubState,
    PreviewEnvironment,
    User,
    VulnerabilityScan,
)
from devdeploy_api.project_service import ensure_personal_org, get_project_for_user
from devdeploy_api.rbac import require_project_role
from devdeploy_api.schemas import (
    AnalyticsOut,
    BillingUsageOut,
    PlatformFlagsOut,
    PreviewCreate,
    PreviewOut,
    ResourceQuotaOut,
    ScanOut,
    StubFeatureOut,
    StubFeatureUpdate,
)

router = APIRouter(tags=["platform"])

STUB_FEATURES = {
    "managed_db": "Requires a paid cloud database provider account.",
    "buildpacks": "Buildpack builders need registry pull access; Dockerfile path remains V1.",
    "autoscaling": "HPA policies need metrics-server on a paid/managed cluster for production.",
    "tracing": "Distributed tracing export needs a Tempo/Jaeger backend or paid APM.",
    "multi_cloud": "Multi-cloud routing requires AWS/GCP credentials and Terraform apply.",
    "ha": "HA control-plane needs multi-AZ Postgres/Redis (paid infra).",
    "billing": "Stripe/metering not configured for local free tier.",
}


def _stub_out(row: PlatformStubState | None, feature: str) -> StubFeatureOut:
    reason = STUB_FEATURES.get(feature, "Coming soon")
    if row is None:
        return StubFeatureOut(
            feature=feature,
            enabled=False,
            status="coming_soon",
            config={},
            coming_soon_reason=reason,
        )
    try:
        cfg = json.loads(row.config_json or "{}")
    except json.JSONDecodeError:
        cfg = {}
    return StubFeatureOut(
        feature=feature,
        enabled=row.enabled,
        status=row.status,
        config=cfg if isinstance(cfg, dict) else {},
        coming_soon_reason=reason if not row.enabled else None,
    )


@router.get("/projects/{project_id}/scans", response_model=list[ScanOut])
def list_scans(
    project_id: UUID,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ScanOut]:
    get_project_for_user(db, user, project_id)
    rows = db.execute(
        select(VulnerabilityScan)
        .where(VulnerabilityScan.project_id == project_id)
        .order_by(VulnerabilityScan.created_at.desc())
        .limit(20)
    ).scalars().all()
    out: list[ScanOut] = []
    for r in rows:
        try:
            report = json.loads(r.report_json or "{}")
        except json.JSONDecodeError:
            report = {}
        out.append(
            ScanOut(
                id=r.id,
                project_id=r.project_id,
                deployment_job_id=r.deployment_job_id,
                image_digest=r.image_digest,
                status=r.status,
                critical=r.critical,
                high=r.high,
                medium=r.medium,
                low=r.low,
                scanner=r.scanner,
                report=report if isinstance(report, dict) else {},
                created_at=r.created_at,
            )
        )
    return out


@router.get("/projects/{project_id}/quotas", response_model=ResourceQuotaOut)
def project_quotas(
    project_id: UUID,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ResourceQuotaOut:
    project = get_project_for_user(db, user, project_id)
    return ResourceQuotaOut(
        project_id=project.id,
        cpu_request=project.cpu_request,
        memory_request=project.memory_request,
        cpu_limit=project.cpu_limit,
        memory_limit=project.memory_limit,
        replicas=project.replicas,
        namespace=f"dd-{project.slug}"[:63],
    )


@router.get("/projects/{project_id}/analytics", response_model=AnalyticsOut)
def project_analytics(
    project_id: UUID,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AnalyticsOut:
    get_project_for_user(db, user, project_id)
    since = datetime.now(UTC) - timedelta(days=7)
    jobs = db.execute(
        select(DeploymentJob).where(
            DeploymentJob.project_id == project_id,
            DeploymentJob.created_at >= since,
        )
    ).scalars().all()
    total = len(jobs)
    ok = sum(1 for j in jobs if j.status == "succeeded")
    rollbacks = sum(1 for j in jobs if j.status == "rolled_back" or j.trigger == "rollback")
    durations = []
    for j in jobs:
        if j.created_at and j.updated_at and j.status in ("succeeded", "failed"):
            durations.append(max(1.0, (j.updated_at - j.created_at).total_seconds()))
    return AnalyticsOut(
        project_id=project_id,
        deploy_success_rate=round((ok / total) * 100, 1) if total else 100.0,
        mean_deploy_seconds=round(sum(durations) / len(durations), 1) if durations else 0.0,
        deploys_last_7d=total,
        rollbacks_last_7d=rollbacks,
    )


@router.get("/projects/{project_id}/previews", response_model=list[PreviewOut])
def list_previews(
    project_id: UUID,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[PreviewOut]:
    get_project_for_user(db, user, project_id)
    rows = db.execute(
        select(PreviewEnvironment)
        .where(PreviewEnvironment.project_id == project_id)
        .order_by(PreviewEnvironment.created_at.desc())
    ).scalars().all()
    return [PreviewOut.model_validate(r) for r in rows]


@router.post(
    "/projects/{project_id}/previews",
    response_model=PreviewOut,
    status_code=201,
)
def create_preview(
    project_id: UUID,
    body: PreviewCreate,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PreviewOut:
    project = get_project_for_user(db, user, project_id)
    require_project_role(db, user, project, "developer")
    row = PreviewEnvironment(
        project_id=project_id,
        pr_number=body.pr_number,
        status="stub",
        preview_url=f"https://pr-{body.pr_number}-{project.slug}.preview.devdeploy.local",
        message=(
            "Preview environment stub recorded. Full PR previews need GitHub Checks + "
            "ephemeral namespaces (enable when webhook PR events are wired)."
        ),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return PreviewOut.model_validate(row)


@router.get("/orgs/me/stubs", response_model=list[StubFeatureOut])
def list_stubs(
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[StubFeatureOut]:
    org = ensure_personal_org(db, user)
    rows = {
        r.feature: r
        for r in db.execute(
            select(PlatformStubState).where(PlatformStubState.organization_id == org.id)
        ).scalars().all()
    }
    return [_stub_out(rows.get(f), f) for f in STUB_FEATURES]


@router.put("/orgs/me/stubs/{feature}", response_model=StubFeatureOut)
def update_stub(
    feature: str,
    body: StubFeatureUpdate,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StubFeatureOut:
    if feature not in STUB_FEATURES:
        raise HTTPException(status_code=404, detail="Unknown stub feature")
    org = ensure_personal_org(db, user)
    row = db.execute(
        select(PlatformStubState).where(
            PlatformStubState.organization_id == org.id,
            PlatformStubState.feature == feature,
        )
    ).scalar_one_or_none()
    if row is None:
        row = PlatformStubState(
            organization_id=org.id,
            feature=feature,
            enabled=False,
            config_json="{}",
            status="coming_soon",
        )
        db.add(row)
    if body.enabled is not None:
        # Keep commercial features disabled unless flags allow; still persist UI intent.
        row.enabled = bool(body.enabled)
        row.status = "stub_enabled" if row.enabled else "coming_soon"
    if body.config is not None:
        row.config_json = json.dumps(body.config)
    db.commit()
    db.refresh(row)
    return _stub_out(row, feature)


@router.get("/orgs/me/billing", response_model=BillingUsageOut)
def billing_usage(
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BillingUsageOut:
    org = ensure_personal_org(db, user)
    from devdeploy_api.models import Project

    pids = db.execute(
        select(Project.id).where(Project.organization_id == org.id)
    ).scalars().all()
    n = 0
    if pids:
        n = db.execute(
            select(func.count())
            .select_from(DeploymentJob)
            .where(DeploymentJob.project_id.in_(list(pids)))
        ).scalar_one()
    return BillingUsageOut(
        build_minutes=round(int(n or 0) * 2.4, 1),
        deploy_count=int(n or 0),
        bandwidth_gb=round(int(n or 0) * 0.15, 2),
        seats=1,
        plan="local-free",
    )


@router.get("/platform/flags", response_model=PlatformFlagsOut)
def platform_flags(settings: Settings = Depends(get_settings)) -> PlatformFlagsOut:
    return PlatformFlagsOut(
        multi_cloud_enabled=settings.multi_cloud_enabled,
        ha_enabled=settings.ha_enabled,
        aws_mock_mode=settings.aws_mock_mode,
    )
