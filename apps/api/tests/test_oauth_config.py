"""OAuth config helpers — no live provider calls."""

from __future__ import annotations

from devdeploy_api.config import Settings
from devdeploy_api.oauth import (
    github_oauth_client_id,
    oauth_callback_url,
    provider_configured,
    providers_status,
)


def test_oauth_callback_url_uses_api_public():
    settings = Settings(
        api_public_url="http://127.0.0.1:8741",
        api_prefix="/api/v1",
    )
    assert (
        oauth_callback_url(settings, "github")
        == "http://127.0.0.1:8741/api/v1/auth/oauth/github/callback"
    )


def test_github_falls_back_to_app_client():
    settings = Settings(
        github_client_id="",
        github_app_client_id="IvApp",
        github_app_client_secret="secret",
        auth_mock_mode=False,
    )
    assert github_oauth_client_id(settings) == "IvApp"
    assert provider_configured(settings, "github") is True
    assert provider_configured(settings, "google") is False


def test_providers_status_respects_mock_and_credentials():
    settings = Settings(
        auth_mock_mode=False,
        github_app_client_id="IvApp",
        github_app_client_secret="secret",
        google_client_id="",
        google_client_secret="",
    )
    rows = {r["id"]: r for r in providers_status(settings)}
    assert rows["github"]["configured"] is True
    assert rows["github"]["enabled"] is True
    assert rows["google"]["configured"] is False
    assert rows["google"]["enabled"] is False

    mock_settings = Settings(auth_mock_mode=True)
    mock_rows = {r["id"]: r for r in providers_status(mock_settings)}
    assert mock_rows["google"]["enabled"] is True
