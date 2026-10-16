"""Stable proxy share helpers."""

from __future__ import annotations

from pathlib import Path

from devdeploy_api.app_routes import (
    register_app_route,
    stable_share_url,
    use_proxy_share,
)
from devdeploy_api.config import Settings
from devdeploy_api.github_service import preview_runtime_slug


def test_use_proxy_share_auto_https(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DEVDEPLOY_APP_ROUTES_PATH", str(tmp_path / "routes.json"))
    settings = Settings(
        public_share_mode="auto",
        api_public_url="https://demo.trycloudflare.com",
    )
    assert use_proxy_share(settings) is True
    path = register_app_route("ekcms-f5f04a", 18150)
    assert path.exists()
    assert (
        stable_share_url(settings, "ekcms-f5f04a")
        == "https://demo.trycloudflare.com/apps/ekcms-f5f04a/"
    )


def test_use_proxy_share_quick_mode():
    settings = Settings(
        public_share_mode="quick",
        api_public_url="https://demo.trycloudflare.com",
    )
    assert use_proxy_share(settings) is False


def test_preview_runtime_slug():
    assert preview_runtime_slug("ekcms-f5f04a", 12) == "ekcms-f5f04a-pr-12"
