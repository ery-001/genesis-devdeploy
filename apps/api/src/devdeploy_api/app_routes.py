"""Stable share routes via the shareable-demo proxy (/apps/{slug} → local port).

When PUBLIC_SHARE_MODE=proxy (or auto + HTTPS API_PUBLIC_URL), project share URLs
stay on the same public hostname as the DevDeploy UI, so they survive API restarts
as long as the single demo tunnel + port-forward are restored.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from devdeploy_api.config import Settings

log = logging.getLogger(__name__)


def _routes_path() -> Path:
    override = (os.environ.get("DEVDEPLOY_APP_ROUTES_PATH") or "").strip()
    if override:
        return Path(override)
    # Repo root: apps/api/src/devdeploy_api → ../../../../
    here = Path(__file__).resolve()
    repo = here.parents[4]
    return repo / ".demo-tunnel" / "app-routes.json"


def load_routes() -> dict[str, int]:
    path = _routes_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, int] = {}
    if isinstance(data, dict):
        for key, val in data.items():
            try:
                out[str(key)] = int(val)
            except (TypeError, ValueError):
                continue
    return out


def save_routes(routes: dict[str, int]) -> Path:
    path = _routes_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(routes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def register_app_route(slug: str, host_port: int) -> Path:
    routes = load_routes()
    routes[slug] = int(host_port)
    path = save_routes(routes)
    log.info("Registered app route /apps/%s → 127.0.0.1:%s (%s)", slug, host_port, path)
    return path


def use_proxy_share(settings: Settings) -> bool:
    mode = (settings.public_share_mode or "auto").strip().lower()
    if mode == "proxy":
        return True
    if mode == "quick":
        return False
    # auto: prefer stable proxy when a public HTTPS origin is configured
    return settings.api_public_url.rstrip("/").startswith("https://")


def stable_share_url(settings: Settings, slug: str) -> str:
    base = settings.api_public_url.rstrip("/")
    return f"{base}/apps/{slug}/"
