"""GitHub webhook receiver with HMAC verify and delivery dedupe."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session as DbSession

from devdeploy_api import github_service
from devdeploy_api.config import Settings, get_settings
from devdeploy_api.deps import get_db

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/github")
async def github_webhook(
    request: Request,
    db: DbSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
    x_github_delivery: str | None = Header(default=None, alias="X-GitHub-Delivery"),
    x_github_event: str | None = Header(default=None, alias="X-GitHub-Event"),
) -> dict:
    body = await request.body()
    github_service.verify_webhook_signature(settings, body, x_hub_signature_256)

    if not x_github_delivery:
        return {"ok": False, "detail": "missing delivery id"}

    event = x_github_event or "unknown"
    is_new = github_service.record_webhook_delivery(db, x_github_delivery, event)
    if not is_new:
        return {"ok": True, "deduped": True}

    payload = json.loads(body.decode("utf-8") or "{}")

    job_id = None
    if event == "push":
        job = github_service.handle_push_event(db, payload, x_github_delivery)
        if job:
            job_id = str(job.id)
    elif event == "pull_request":
        job = github_service.handle_pull_request_event(db, payload, x_github_delivery)
        if job:
            job_id = str(job.id)
    elif event == "installation":
        # Installation create/delete recorded later when real App is wired.
        pass
    # Jobs are processed by `make worker` (Redis list). Keep webhook fast for GitHub.

    return {
        "ok": True,
        "event": event,
        "delivery_id": x_github_delivery,
        "deployment_job_id": job_id,
    }
