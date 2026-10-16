"""Real OAuth authorize + token exchange for user sign-in providers.

User login OAuth is separate from the GitHub App installation used for repo access.
GitHub login reuses the GitHub App's OAuth client credentials when
GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET are unset.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import HTTPException

from devdeploy_api.auth_service import OAUTH_PROVIDERS
from devdeploy_api.config import Settings

ProviderStatus = dict[str, Any]


def oauth_callback_url(
    settings: Settings,
    provider: str,
    *,
    api_base: str | None = None,
) -> str:
    base = (api_base or settings.api_public_url).rstrip("/")
    return f"{base}{settings.api_prefix}/auth/oauth/{provider}/callback"


def github_oauth_client_id(settings: Settings) -> str:
    return (settings.github_client_id or settings.github_app_client_id or "").strip()


def github_oauth_client_secret(settings: Settings) -> str:
    return (
        settings.github_client_secret or settings.github_app_client_secret or ""
    ).strip()


def provider_credentials(settings: Settings, provider: str) -> tuple[str, str]:
    if provider == "github":
        return github_oauth_client_id(settings), github_oauth_client_secret(settings)
    if provider == "google":
        return settings.google_client_id.strip(), settings.google_client_secret.strip()
    if provider == "apple":
        return settings.apple_client_id.strip(), settings.apple_client_secret.strip()
    if provider == "microsoft":
        return (
            settings.microsoft_client_id.strip(),
            settings.microsoft_client_secret.strip(),
        )
    return "", ""


def provider_configured(settings: Settings, provider: str) -> bool:
    client_id, client_secret = provider_credentials(settings, provider)
    return bool(client_id and client_secret)


def providers_status(settings: Settings) -> list[ProviderStatus]:
    from devdeploy_api.public_url import oauth_callback_urls

    rows: list[ProviderStatus] = []
    for provider in OAUTH_PROVIDERS:
        configured = provider_configured(settings, provider)
        primary = oauth_callback_url(settings, provider)
        extras = (
            oauth_callback_urls(settings)
            if provider == "github"
            else [primary]
        )
        rows.append(
            {
                "id": provider,
                "configured": configured,
                "enabled": settings.auth_mock_mode or configured,
                "callback_url": primary,
                "callback_urls": extras,
            }
        )
    return rows


def build_authorize_url(
    settings: Settings,
    provider: str,
    state: str,
    *,
    api_base: str | None = None,
) -> str:
    client_id, _ = provider_credentials(settings, provider)
    if not client_id:
        raise HTTPException(status_code=400, detail=f"{provider} OAuth is not configured")

    redirect_uri = oauth_callback_url(settings, provider, api_base=api_base)

    if provider == "github":
        qs = urlencode(
            {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "state": state,
                "scope": "read:user user:email",
                "allow_signup": "true",
            }
        )
        return f"https://github.com/login/oauth/authorize?{qs}"

    if provider == "google":
        qs = urlencode(
            {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "access_type": "online",
                "prompt": "select_account",
            }
        )
        return f"https://accounts.google.com/o/oauth2/v2/auth?{qs}"

    if provider == "microsoft":
        tenant = (settings.microsoft_tenant_id or "common").strip() or "common"
        qs = urlencode(
            {
                "client_id": client_id,
                "response_type": "code",
                "redirect_uri": redirect_uri,
                "response_mode": "query",
                "scope": "openid profile email User.Read",
                "state": state,
            }
        )
        return f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize?{qs}"

    if provider == "apple":
        qs = urlencode(
            {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "response_mode": "form_post",
                "scope": "name email",
                "state": state,
            }
        )
        return f"https://appleid.apple.com/auth/authorize?{qs}"

    raise HTTPException(status_code=400, detail="Unsupported OAuth provider")


def _raise_oauth_http(provider: str, response: httpx.Response) -> None:
    detail = f"{provider} OAuth token exchange failed ({response.status_code})"
    try:
        payload = response.json()
        if isinstance(payload, dict):
            err = payload.get("error_description") or payload.get("error") or payload.get("message")
            if err:
                detail = f"{detail}: {err}"
    except Exception:
        pass
    raise HTTPException(status_code=400, detail=detail)


def exchange_code_for_profile(
    settings: Settings,
    provider: str,
    code: str,
    *,
    api_base: str | None = None,
) -> dict[str, str | None]:
    """Exchange authorization code for a normalized profile dict."""
    client_id, client_secret = provider_credentials(settings, provider)
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail=f"{provider} OAuth is not configured")

    redirect_uri = oauth_callback_url(settings, provider, api_base=api_base)

    with httpx.Client(timeout=20.0) as client:
        if provider == "github":
            token_res = client.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )
            if token_res.status_code >= 400:
                _raise_oauth_http(provider, token_res)
            token_payload = token_res.json()
            access_token = token_payload.get("access_token")
            if not access_token:
                raise HTTPException(
                    status_code=400,
                    detail=token_payload.get("error_description")
                    or token_payload.get("error")
                    or "GitHub did not return an access token",
                )
            user_res = client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            if user_res.status_code >= 400:
                _raise_oauth_http(provider, user_res)
            user = user_res.json()
            email = user.get("email")
            if not email:
                emails_res = client.get(
                    "https://api.github.com/user/emails",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                )
                if emails_res.status_code < 400:
                    emails = emails_res.json()
                    if isinstance(emails, list):
                        primary = next(
                            (
                                e
                                for e in emails
                                if isinstance(e, dict) and e.get("primary") and e.get("email")
                            ),
                            None,
                        )
                        email = (primary or next((e for e in emails if isinstance(e, dict)), {})).get(
                            "email"
                        )
            subject = str(user.get("id") or "")
            if not subject:
                raise HTTPException(status_code=400, detail="GitHub profile missing id")
            return {
                "subject": subject,
                "email": email,
                "display_name": user.get("name") or user.get("login"),
                "avatar_url": user.get("avatar_url"),
            }

        if provider == "google":
            token_res = client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            if token_res.status_code >= 400:
                _raise_oauth_http(provider, token_res)
            access_token = token_res.json().get("access_token")
            if not access_token:
                raise HTTPException(status_code=400, detail="Google did not return an access token")
            info_res = client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if info_res.status_code >= 400:
                _raise_oauth_http(provider, info_res)
            info = info_res.json()
            subject = str(info.get("sub") or "")
            if not subject:
                raise HTTPException(status_code=400, detail="Google profile missing sub")
            return {
                "subject": subject,
                "email": info.get("email"),
                "display_name": info.get("name"),
                "avatar_url": info.get("picture"),
            }

        if provider == "microsoft":
            tenant = (settings.microsoft_tenant_id or "common").strip() or "common"
            token_res = client.post(
                f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            if token_res.status_code >= 400:
                _raise_oauth_http(provider, token_res)
            access_token = token_res.json().get("access_token")
            if not access_token:
                raise HTTPException(
                    status_code=400, detail="Microsoft did not return an access token"
                )
            me_res = client.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if me_res.status_code >= 400:
                _raise_oauth_http(provider, me_res)
            me = me_res.json()
            subject = str(me.get("id") or "")
            if not subject:
                raise HTTPException(status_code=400, detail="Microsoft profile missing id")
            return {
                "subject": subject,
                "email": me.get("mail") or me.get("userPrincipalName"),
                "display_name": me.get("displayName"),
                "avatar_url": None,
            }

        if provider == "apple":
            token_res = client.post(
                "https://appleid.apple.com/auth/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
            )
            if token_res.status_code >= 400:
                _raise_oauth_http(provider, token_res)
            id_token = token_res.json().get("id_token")
            if not id_token:
                raise HTTPException(status_code=400, detail="Apple did not return an id_token")
            # Apple signs id_token; for local login we decode claims without
            # remote JWKS verification (secret already authenticated the code).
            claims = jwt.decode(
                id_token,
                options={"verify_signature": False, "verify_aud": False},
            )
            subject = str(claims.get("sub") or "")
            if not subject:
                raise HTTPException(status_code=400, detail="Apple id_token missing sub")
            return {
                "subject": subject,
                "email": claims.get("email"),
                "display_name": None,
                "avatar_url": None,
            }

    raise HTTPException(status_code=400, detail="Unsupported OAuth provider")
