"""Deployment pipeline: build → publish → deploy (mock-first)."""

from __future__ import annotations

import hashlib
import json
import secrets
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from devdeploy_api.config import get_settings
from devdeploy_api.db import SessionLocal
from devdeploy_api.models import DeploymentJob, K8sResourceIntent, Project, Release
from devdeploy_api.redis_client import get_redis

LIFECYCLE = (
    "queued",
    "building",
    "publishing",
    "deploying",
    "succeeded",
    "failed",
    "rolled_back",
)


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


def _mock_digest(project: Project, job: DeploymentJob) -> str:
    raw = f"{project.slug}:{job.id}:{job.git_ref}:{secrets.token_hex(8)}"
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def _current_release(db: DbSession, project_id: uuid.UUID) -> Release | None:
    return db.execute(
        select(Release)
        .where(Release.project_id == project_id)
        .where(Release.is_current.is_(True))
        .limit(1)
    ).scalar_one_or_none()


def process_job(job_id: uuid.UUID, *, step_delay: float = 0.15) -> DeploymentJob:
    """Run the full pipeline for one job. Preserves healthy release on failure."""
    settings = get_settings()
    db = SessionLocal()
    try:
        job = db.get(DeploymentJob, job_id)
        if job is None:
            raise ValueError(f"job {job_id} not found")
        project = db.get(Project, job.project_id)
        if project is None:
            raise ValueError("project missing")

        prior = _current_release(db, project.id)

        _set_status(db, job, "building", "Starting isolated build (mock BuildKit)")
        time.sleep(step_delay)
        _append_log(job, f"Dockerfile: {project.dockerfile_path or 'Dockerfile'}")
        _append_log(job, f"Context: repo={project.github_repo_full_name} ref={job.git_ref}")
        db.commit()

        if job.simulate_failure:
            time.sleep(step_delay)
            _set_status(db, job, "failed", "Build failed (simulated)")
            # Do not touch prior healthy release
            if prior:
                _append_log(
                    job,
                    f"Prior healthy release retained: {prior.image_digest[:19]}…",
                )
                db.commit()
            return job

        time.sleep(step_delay)
        _append_log(job, "Build completed successfully")
        db.commit()

        _set_status(db, job, "publishing", "Publishing image digest")
        time.sleep(step_delay)
        digest = _mock_digest(project, job)
        tag = f"devdeploy/{project.slug}:{str(job.id)[:8]}"
        if settings.aws_mock_mode:
            _append_log(job, f"Mock ECR push → {tag}@{digest[:19]}…")
        else:
            _append_log(job, f"ECR push configured (real path) → {tag}")
        job.image_digest = digest
        job.image_tag = tag
        db.commit()

        _set_status(db, job, "deploying", "Applying workload-plane manifests")
        time.sleep(step_delay)
        app_url = f"https://{project.slug}.apps.devdeploy.local"
        namespace = f"dd-{project.slug}"[:63]
        manifests = [
            ("Deployment", project.slug, {"image": f"{tag}@{digest}", "replicas": 1}),
            ("Service", f"{project.slug}-svc", {"port": 80}),
            ("Ingress", f"{project.slug}-ing", {"host": f"{project.slug}.apps.devdeploy.local"}),
        ]
        # Create release first (not current until success)
        release = Release(
            project_id=project.id,
            deployment_job_id=job.id,
            image_digest=digest,
            image_tag=tag,
            app_url=app_url,
            status="pending",
            is_current=False,
        )
        db.add(release)
        db.flush()

        for kind, name, body in manifests:
            db.add(
                K8sResourceIntent(
                    project_id=project.id,
                    release_id=release.id,
                    kind=kind,
                    name=name,
                    namespace=namespace,
                    manifest_json=json.dumps(body),
                    status="applied-mock" if settings.k8s_mock_mode else "applied",
                )
            )
            _append_log(job, f"Applied {kind}/{name} in {namespace}")
        db.commit()

        time.sleep(step_delay)
        # Promote release; demote prior without deleting it
        if prior:
            prior.is_current = False
            prior.status = "superseded"
        release.is_current = True
        release.status = "healthy"
        job.app_url = app_url
        _set_status(db, job, "succeeded", f"Rollout healthy at {app_url}")
        return job
    finally:
        db.close()


def rollback_project(db: DbSession, project_id: uuid.UUID) -> Release:
    """Restore previous healthy/superseded release; keep failed attempts intact."""
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

    current.is_current = False
    current.status = "rolled_back"
    previous.is_current = True
    previous.status = "healthy"
    db.commit()
    db.refresh(previous)

    # Record rollback job marker
    job = DeploymentJob(
        project_id=project_id,
        status="rolled_back",
        trigger="rollback",
        git_ref=None,
        message=f"Rolled back to {previous.image_digest[:19]}…",
        image_digest=previous.image_digest,
        image_tag=previous.image_tag,
        app_url=previous.app_url,
        build_logs=f"Rollback to release {previous.id}",
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
