"""Resolve public API / web origins from the incoming request.

Supports dual local + shareable-demo (tunnel) without forcing one WEB_ORIGIN.
"""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import Request

from devdeploy_api.config import Settings

_LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def public_base_from_request(request: Request, settings: Settings) -> str:
    """API origin as seen by the browser (honours demo-proxy forwarded headers)."""
    xf_host = (request.headers.get("x-forwarded-host") or "").split(",")[0].strip()
    if xf_host:
        xf_proto = (request.headers.get("x-forwarded-proto") or "https").split(",")[0].strip()
        return f"{xf_proto}://{xf_host}".rstrip("/")
    # Direct local API (e.g. http://127.0.0.1:8741)
    return str(request.base_url).rstrip("/")


def web_origin_from_request(request: Request, settings: Settings) -> str:
    """Where to send the browser after OAuth (local UI vs same-host tunnel proxy)."""
    api_base = public_base_from_request(request, settings)
    host = (urlparse(api_base).hostname or "").lower()
    if host in _LOCAL_HOSTS:
        return settings.web_origin.rstrip("/")
    # Shareable demo: UI and API share the public hostname via demo-proxy.
    return api_base


def cookie_secure_for_request(request: Request, settings: Settings) -> bool:
    """Secure cookies on HTTPS (tunnel); allow HTTP cookies for local testing."""
    api_base = public_base_from_request(request, settings)
    if api_base.startswith("https://"):
        return True
    return bool(settings.session_cookie_secure)


def oauth_callback_urls(settings: Settings) -> list[str]:
    """URLs to register on the GitHub App (local + configured public, deduped)."""
    local = f"http://127.0.0.1:8741{settings.api_prefix}/auth/oauth/github/callback"
    configured = (
        f"{settings.api_public_url.rstrip('/')}{settings.api_prefix}"
        f"/auth/oauth/github/callback"
    )
    urls = [local]
    if configured.rstrip("/") != local.rstrip("/"):
        urls.append(configured)
    return urls
