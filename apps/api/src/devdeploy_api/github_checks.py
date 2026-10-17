"""GitHub Checks API + PR comments for preview deploys."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from devdeploy_api.config import Settings
from devdeploy_api.github_app_auth import create_installation_token

log = logging.getLogger(__name__)


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _iso_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _installation_access(settings: Settings, installation_id: int) -> str | None:
    if settings.effective_github_mock:
        return None
    try:
        tok = create_installation_token(settings, installation_id)
        return tok.get("token")
    except Exception as exc:  # noqa: BLE001
        log.warning("installation token failed: %s", exc)
        return None


def create_check_run(
    settings: Settings,
    *,
    installation_id: int,
    repo_full_name: str,
    head_sha: str,
    name: str = "DevDeploy Preview",
    details_url: str | None = None,
) -> int | None:
    """Create an in-progress check run; returns check_run id."""
    token = _installation_access(settings, installation_id)
    if not token or not head_sha:
        return None
    body: dict[str, Any] = {
        "name": name,
        "head_sha": head_sha,
        "status": "in_progress",
        "started_at": _iso_now(),
    }
    if details_url:
        body["details_url"] = details_url
    url = f"https://api.github.com/repos/{repo_full_name}/check-runs"
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(url, headers=_headers(token), json=body)
            if r.status_code >= 400:
                log.warning("create check-run failed: %s %s", r.status_code, r.text[:300])
                return None
            return int(r.json()["id"])
    except Exception as exc:  # noqa: BLE001
        log.warning("create check-run error: %s", exc)
        return None


def complete_check_run(
    settings: Settings,
    *,
    installation_id: int,
    repo_full_name: str,
    check_run_id: int,
    conclusion: str,
    title: str,
    summary: str,
    details_url: str | None = None,
) -> bool:
    """Mark a check run completed (success | failure | cancelled | neutral)."""
    token = _installation_access(settings, installation_id)
    if not token:
        return False
    body: dict[str, Any] = {
        "status": "completed",
        "conclusion": conclusion,
        "completed_at": _iso_now(),
        "output": {"title": title, "summary": summary},
    }
    if details_url:
        body["details_url"] = details_url
    url = f"https://api.github.com/repos/{repo_full_name}/check-runs/{check_run_id}"
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.patch(url, headers=_headers(token), json=body)
            if r.status_code >= 400:
                log.warning("complete check-run failed: %s %s", r.status_code, r.text[:300])
                return False
            return True
    except Exception as exc:  # noqa: BLE001
        log.warning("complete check-run error: %s", exc)
        return False


def comment_on_pull_request(
    settings: Settings,
    *,
    installation_id: int,
    repo_full_name: str,
    pr_number: int,
    body: str,
) -> bool:
    """Post (or attempt) a PR issue comment with the preview URL."""
    token = _installation_access(settings, installation_id)
    if not token:
        return False
    url = f"https://api.github.com/repos/{repo_full_name}/issues/{pr_number}/comments"
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(url, headers=_headers(token), json={"body": body})
            if r.status_code >= 400:
                log.warning("PR comment failed: %s %s", r.status_code, r.text[:300])
                return False
            return True
    except Exception as exc:  # noqa: BLE001
        log.warning("PR comment error: %s", exc)
        return False
