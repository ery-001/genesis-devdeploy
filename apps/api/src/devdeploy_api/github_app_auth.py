"""GitHub App JWT + installation access tokens (real App path)."""

from __future__ import annotations

import time
from pathlib import Path

import httpx
import jwt

from devdeploy_api.config import Settings


def load_private_key(settings: Settings) -> str:
    if settings.github_app_private_key.strip():
        key = settings.github_app_private_key.strip()
        # Allow escaped newlines from env files
        return key.replace("\\n", "\n")
    if settings.github_app_private_key_path:
        return Path(settings.github_app_private_key_path).expanduser().read_text()
    raise ValueError("GitHub App private key not configured")


def create_app_jwt(settings: Settings, *, ttl_seconds: int = 540) -> str:
    """RS256 JWT for GitHub App authentication (max 10 minutes)."""
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + ttl_seconds,
        "iss": settings.github_app_id,
    }
    return jwt.encode(payload, load_private_key(settings), algorithm="RS256")


def create_installation_token(
    settings: Settings, installation_id: int
) -> dict:
    """POST /app/installations/{id}/access_tokens → token payload."""
    token = create_app_jwt(settings)
    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    with httpx.Client(timeout=30.0) as client:
        r = client.post(url, headers=headers)
        r.raise_for_status()
        return r.json()


def list_installation_repos(settings: Settings, installation_id: int) -> list[dict]:
    """List repositories accessible to an installation."""
    tok = create_installation_token(settings, installation_id)
    access = tok["token"]
    headers = {
        "Authorization": f"Bearer {access}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    repos: list[dict] = []
    url: str | None = "https://api.github.com/installation/repositories?per_page=100"
    with httpx.Client(timeout=30.0) as client:
        while url:
            r = client.get(url, headers=headers)
            r.raise_for_status()
            data = r.json()
            for repo in data.get("repositories") or []:
                repos.append(
                    {
                        "id": repo["id"],
                        "full_name": repo["full_name"],
                        "name": repo["name"],
                        "private": repo.get("private", False),
                        "default_branch": repo.get("default_branch") or "main",
                    }
                )
            # Follow Link: next if present
            link = r.headers.get("link") or ""
            next_url = None
            for part in link.split(","):
                if 'rel="next"' in part:
                    next_url = part[part.find("<") + 1 : part.find(">")]
            url = next_url
    return repos


def list_repo_branches(
    settings: Settings, installation_id: int, owner: str, repo: str
) -> list[dict]:
    """List branches for a repository via an installation token."""
    tok = create_installation_token(settings, installation_id)
    access = tok["token"]
    headers = {
        "Authorization": f"Bearer {access}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    branches: list[dict] = []
    url: str | None = (
        f"https://api.github.com/repos/{owner}/{repo}/branches?per_page=100"
    )
    with httpx.Client(timeout=30.0) as client:
        while url:
            r = client.get(url, headers=headers)
            r.raise_for_status()
            for branch in r.json():
                if isinstance(branch, dict) and branch.get("name"):
                    branches.append(
                        {
                            "name": branch["name"],
                            "protected": bool(branch.get("protected")),
                        }
                    )
            link = r.headers.get("link") or ""
            next_url = None
            for part in link.split(","):
                if 'rel="next"' in part:
                    next_url = part[part.find("<") + 1 : part.find(">")]
            url = next_url
    return branches


def list_app_installations(settings: Settings) -> list[dict]:
    """GET /app/installations — requires App JWT."""
    token = create_app_jwt(settings)
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    out: list[dict] = []
    url: str | None = "https://api.github.com/app/installations?per_page=100"
    with httpx.Client(timeout=30.0) as client:
        while url:
            r = client.get(url, headers=headers)
            r.raise_for_status()
            for inst in r.json():
                account = inst.get("account") or {}
                out.append(
                    {
                        "installation_id": inst["id"],
                        "account_login": account.get("login") or "",
                        "account_type": account.get("type") or "User",
                    }
                )
            link = r.headers.get("link") or ""
            next_url = None
            for part in link.split(","):
                if 'rel="next"' in part:
                    next_url = part[part.find("<") + 1 : part.find(">")]
            url = next_url
    return out
