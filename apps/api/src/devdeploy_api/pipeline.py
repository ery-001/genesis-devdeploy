"""Deployment pipeline: build → publish → deploy (real Docker/kind when enabled)."""

from __future__ import annotations

import json
import time
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from devdeploy_api import build_engine, k8s_engine
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
    from datetime import UTC, datetime

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

        mode = "mock" if build_engine.effective_build_mock(settings) else "real"
        _set_status(
            db,
            job,
            "building",
            f"Starting isolated build ({mode} BuildKit)",
        )
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
        except Exception as exc:  # noqa: BLE001 — surface in job logs
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

        _set_status(db, job, "publishing", "Publishing image digest")
        time.sleep(step_delay)
        job.image_digest = build.digest
        job.image_tag = build.image_tag
        db.commit()

        # Load local tag into kind so imagePullPolicy: IfNotPresent works offline.
        # Required when K8S_MOCK_MODE=false (registry push alone is not enough on kind).
        if not k8s_engine.effective_k8s_mock(settings) and not build.mocked:
            try:
                local_short = f"devdeploy/{project.slug}:{str(job.id)[:8]}"
                load_lines = build_engine.kind_load_image(
                    local_short, settings.kind_cluster_name
                )
                for line in load_lines:
                    _append_log(job, line)
                # Prefer the short tag for the Deployment (already on the node)
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

        _set_status(db, job, "deploying", "Applying workload-plane manifests")
        time.sleep(step_delay)

        try:
            deploy = k8s_engine.deploy_to_cluster(
                settings,
                project_slug=project.slug,
                image_tag=job.image_tag or build.image_tag,
                image_digest=job.image_digest or build.digest,
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
