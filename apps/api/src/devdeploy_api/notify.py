"""Deployment notification stubs (email log + optional webhook POST)."""

from __future__ import annotations

import json
import logging
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from devdeploy_api.models import NotificationConfig

log = logging.getLogger(__name__)


def notify_deployment(
    db: DbSession,
    *,
    organization_id: uuid.UUID,
    project_name: str,
    job_id: uuid.UUID,
    status: str,
    message: str | None,
) -> list[str]:
    rows = db.execute(
        select(NotificationConfig)
        .where(NotificationConfig.organization_id == organization_id)
        .where(NotificationConfig.enabled.is_(True))
    ).scalars().all()
    notes: list[str] = []
    payload = {
        "project": project_name,
        "deployment_job_id": str(job_id),
        "status": status,
        "message": message,
    }
    for row in rows:
        if row.kind == "email":
            # Email provider not configured — durable stub log only.
            log.info(
                "email-stub to=%s subject=Deploy %s payload=%s",
                row.target,
                status,
                json.dumps(payload),
            )
            notes.append(f"Email stub → {row.target}")
        elif row.kind == "webhook":
            try:
                resp = httpx.post(row.target, json=payload, timeout=5.0)
                notes.append(f"Webhook {resp.status_code} → {row.target}")
            except Exception as exc:  # noqa: BLE001
                notes.append(f"Webhook failed → {row.target}: {exc}")
                log.warning("webhook notify failed: %s", exc)
    return notes
