"""Deployment pipeline: build → publish → deploy (real Docker/kind when enabled)."""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from devdeploy_api import build_engine, k8s_engine, notify, scan_engine
from devdeploy_api.config import get_settings
from devdeploy_api.crypto_util import decrypt_secret
from devdeploy_api.db import SessionLocal
from devdeploy_api.models import (
    DeploymentJob,
    K8sResourceIntent,
    PreviewEnvironment,
    Project,
    ProjectEnvironment,
    ProjectVariable,
    Release,
)
from devdeploy_api.redis_client import get_redis

LIFECYCLE = (
    "queued",
    "pending_approval",
    "building",
    "publishing",
    "deploying",
    "succeeded",
    "failed",
    "rolled_back",
    "cancelled",
)

ACTIVE = frozenset({"queued", "building", "publishing", "deploying"})


def _append_log(job: DeploymentJob, line: str) -> None:
    stamp = datetime.now(UTC).strftime("%H:%M:%S")
    entry = f"[{stamp}] {line}"
    job.build_logs = f"{job.build_logs}\n{entry}" if job.build_logs else entry
    job.message = line


def _set_status(db: DbSession, job: DeploymentJob, status: str, message: str) -> None:
    job.status = status
    _append_log(job, message)
    db.commit()
    db.refresh(job)


def _current_release(db: DbSession, project_id: uuid.UUID) -> Release | None:
    return db.execute(
        select(Release)
        .where(Release.project_id == project_id)
        .where(Release.is_current.is_(True))
        .limit(1)
    ).scalar_one_or_none()


def _was_cancelled(db: DbSession, job_id: uuid.UUID) -> bool:
    job = db.get(DeploymentJob, job_id)
    return bool(job and (job.status == "cancelled" or job.cancelled_at is not None))


def _load_env_vars(
    db: DbSession, project_id: uuid.UUID, environment_name: str
) -> dict[str, str]:
    rows = db.execute(
        select(ProjectVariable).where(
            ProjectVariable.project_id == project_id,
            ProjectVariable.environment_name == environment_name,
        )
    ).scalars().all()
    out: dict[str, str] = {}
    for row in rows:
        try:
            out[row.key] = decrypt_secret(row.value_encrypted)
        except ValueError:
            continue
    return out


def cancel_job(db: DbSession, job: DeploymentJob) -> DeploymentJob:
    if job.status not in ACTIVE and job.status != "pending_approval":
        raise ValueError(f"Cannot cancel job in status {job.status}")
    job.status = "cancelled"
    job.cancelled_at = datetime.now(UTC)
    _append_log(job, "Cancelled by user")
    db.commit()
    db.refresh(job)
    return job


def queue_job_id(job_id: uuid.UUID) -> None:
    redis = get_redis()
    try:
        redis.lpush(
            "devdeploy:deployments",
            json.dumps({"id": str(job_id)}),
        )
    finally:
        redis.close()


def process_job(job_id: uuid.UUID, *, step_delay: float = 0.15) -> DeploymentJob:
    """Run the full pipeline for one job. Preserves healthy release on failure."""
    settings = get_settings()
    db = SessionLocal()
    try:
        job = db.get(DeploymentJob, job_id)
        if job is None:
            raise ValueError(f"job {job_id} not found")
        if job.status in ("cancelled", "succeeded", "failed", "rolled_back"):
            return job
        if job.status == "pending_approval":
            return job

        project = db.get(Project, job.project_id)
        if project is None:
            raise ValueError("project missing")

        prior = _current_release(db, project.id)

        mode = "mock" if build_engine.effective_build_mock(settings) else "real"
        _set_status(
            db,
            job,
            "building",
            f"Starting isolated build ({mode} BuildKit)",
        )
        if _was_cancelled(db, job_id):
            return db.get(DeploymentJob, job_id)  # type: ignore[return-value]
        time.sleep(step_delay)

        if job.simulate_failure:
            time.sleep(step_delay)
            _set_status(db, job, "failed", "Build failed (simulated)")
            if prior:
                _append_log(
                    job,
                    f"Prior healthy release retained: {prior.image_digest[:19]}…",
                )
                db.commit()
            return job

        try:
            build = build_engine.build_and_publish(
                settings,
                project_slug=project.slug,
                job_id=str(job.id),
                git_ref=job.git_ref or "main",
                repo_full_name=project.github_repo_full_name,
                dockerfile_path=project.dockerfile_path or "Dockerfile",
            )
        except Exception as exc:  # noqa: BLE001
            _set_status(db, job, "failed", f"Build failed: {exc}")
            if prior:
                _append_log(
                    job,
                    f"Prior healthy release retained: {prior.image_digest[:19]}…",
                )
                db.commit()
            return job

        for line in build.logs:
            _append_log(job, line)
        db.commit()

        if _was_cancelled(db, job_id):
            return db.get(DeploymentJob, job_id)  # type: ignore[return-value]

        _set_status(db, job, "publishing", "Publishing image digest")
        time.sleep(step_delay)
        job.image_digest = build.digest
        job.image_tag = build.image_tag
        db.commit()

        try:
            scan = scan_engine.persist_scan(
                db,
                project_id=project.id,
                deployment_job_id=job.id,
                image_digest=job.image_digest,
                image_ref=job.image_tag or build.image_tag,
            )
            _append_log(
                job,
                f"Vulnerability scan ({scan.scanner}): "
                f"C={scan.critical} H={scan.high} M={scan.medium} L={scan.low}",
            )
            db.commit()
        except Exception as exc:  # noqa: BLE001
            _append_log(job, f"Scan skipped: {exc}")
            db.commit()

        if not k8s_engine.effective_k8s_mock(settings) and not build.mocked:
            try:
                local_short = f"devdeploy/{project.slug}:{str(job.id)[:8]}"
                load_lines = build_engine.kind_load_image(
                    local_short, settings.kind_cluster_name
                )
                for line in load_lines:
                    _append_log(job, line)
                job.image_tag = local_short
                db.commit()
            except Exception as exc:  # noqa: BLE001
                _set_status(db, job, "failed", f"kind load failed: {exc}")
                if prior:
                    _append_log(
                        job,
                        f"Prior healthy release retained: {prior.image_digest[:19]}…",
                    )
                    db.commit()
                return job

        if _was_cancelled(db, job_id):
            return db.get(DeploymentJob, job_id)  # type: ignore[return-value]

        _set_status(db, job, "deploying", "Applying workload-plane manifests")
        time.sleep(step_delay)

        env_row = db.execute(
            select(ProjectEnvironment)
            .where(ProjectEnvironment.project_id == project.id)
            .where(ProjectEnvironment.name == job.environment_name)
        ).scalar_one_or_none()
        replicas = (
            env_row.replicas
            if env_row is not None
            else (project.replicas or 1)
        )
        env_vars = _load_env_vars(db, project.id, job.environment_name)

        runtime_slug = (job.runtime_slug or project.slug).strip() or project.slug
        try:
            deploy = k8s_engine.deploy_to_cluster(
                settings,
                project_slug=runtime_slug,
                image_tag=job.image_tag or build.image_tag,
                image_digest=job.image_digest or build.digest,
                container_port=project.container_port,
                health_path=project.health_path or "/health",
                replicas=replicas,
                cpu_request=project.cpu_request,
                memory_request=project.memory_request,
                cpu_limit=project.cpu_limit,
                memory_limit=project.memory_limit,
                env=env_vars or None,
            )
        except Exception as exc:  # noqa: BLE001
            _set_status(db, job, "failed", f"Deploy failed: {exc}")
            if prior:
                _append_log(
                    job,
                    f"Prior healthy release retained: {prior.image_digest[:19]}…",
                )
                db.commit()
            return job

        for line in deploy.logs:
            _append_log(job, line)

        release = Release(
            project_id=project.id,
            deployment_job_id=job.id,
            image_digest=job.image_digest,
            image_tag=job.image_tag,
            app_url=deploy.app_url,
            public_url=deploy.public_url,
            status="pending",
            is_current=False,
        )
        db.add(release)
        db.flush()

        for kind, name, body in deploy.manifests:
            db.add(
                K8sResourceIntent(
                    project_id=project.id,
                    release_id=release.id,
                    kind=kind,
                    name=name,
                    namespace=deploy.namespace,
                    manifest_json=json.dumps(body),
                    status=deploy.status,
                )
            )
            _append_log(job, f"Applied {kind}/{name} in {deploy.namespace}")
        db.commit()

        time.sleep(step_delay)
        if prior:
            prior.is_current = False
            prior.status = "superseded"
        release.is_current = True
        release.status = "healthy"
        job.app_url = deploy.app_url
        job.public_url = deploy.public_url
        ok_msg = f"Rollout healthy at {deploy.app_url}"
        if deploy.public_url:
            ok_msg += f" · public {deploy.public_url}"
        _set_status(db, job, "succeeded", ok_msg)

        for note in notify.notify_deployment(
            db,
            organization_id=project.organization_id,
            project_name=project.name,
            job_id=job.id,
            status="succeeded",
            message=ok_msg,
        ):
            _append_log(job, note)

        # Sync PR preview rows when this job is a preview deploy.
        if job.trigger in {"webhook_pr", "preview"} or job.runtime_slug:
            preview = db.execute(
                select(PreviewEnvironment)
                .where(PreviewEnvironment.deployment_job_id == job.id)
                .limit(1)
            ).scalar_one_or_none()
            if preview is not None:
                preview.status = "ready"
                preview.preview_url = deploy.public_url or deploy.app_url
                preview.message = ok_msg
        db.commit()
        return job
    finally:
        db.close()


def rollback_project(db: DbSession, project_id: uuid.UUID) -> Release:
    """Restore previous healthy/superseded release; keep failed attempts intact."""
    settings = get_settings()
    current = _current_release(db, project_id)
    if current is None:
        raise ValueError("No current release to roll back from")

    previous = db.execute(
        select(Release)
        .where(Release.project_id == project_id)
        .where(Release.id != current.id)
        .where(Release.status.in_(("healthy", "superseded")))
        .order_by(Release.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if previous is None:
        raise ValueError("No previous release available")

    project = db.get(Project, project_id)
    workload_logs: list[str] = []
    access: k8s_engine.AccessResult | None = None
    if project and previous.image_tag:
        try:
            access = k8s_engine.rollback_workload(
                settings,
                project_slug=project.slug,
                image_tag=previous.image_tag,
            )
            workload_logs = access.logs
            previous.app_url = access.app_url
            if access.public_url:
                previous.public_url = access.public_url
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Workload rollback failed: {exc}") from exc

    current.is_current = False
    current.status = "rolled_back"
    previous.is_current = True
    previous.status = "healthy"
    db.commit()
    db.refresh(previous)

    job = DeploymentJob(
        project_id=project_id,
        status="rolled_back",
        trigger="rollback",
        git_ref=None,
        message=f"Rolled back to {previous.image_digest[:19]}…",
        image_digest=previous.image_digest,
        image_tag=previous.image_tag,
        app_url=previous.app_url,
        public_url=previous.public_url,
        build_logs="\n".join(
            [f"Rollback to release {previous.id}", *workload_logs]
        ),
    )
    db.add(job)
    db.commit()
    return previous


def worker_loop(*, once: bool = False, step_delay: float = 0.15) -> None:
    """BRPOP deployment queue and process jobs."""
    redis = get_redis()
    try:
        while True:
            item = redis.brpop("devdeploy:deployments", timeout=2)
            if item is None:
                if once:
                    return
                continue
            _, raw = item
            payload = json.loads(raw)
            job_id = uuid.UUID(payload["id"])
            process_job(job_id, step_delay=step_delay)
            if once:
                return
    finally:
        redis.close()


def drain_queue(step_delay: float = 0.05) -> int:
    """Process all currently queued jobs (non-blocking pop)."""
    redis = get_redis()
    count = 0
    try:
        while True:
            raw = redis.rpop("devdeploy:deployments")
            if raw is None:
                break
            payload = json.loads(raw)
            process_job(uuid.UUID(payload["id"]), step_delay=step_delay)
            count += 1
    finally:
        redis.close()
    return count
