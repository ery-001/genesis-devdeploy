"""Minimal CLI: login (store API key) and deploy against a local API."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import httpx

DEFAULT_API = os.environ.get("DEVDEPLOY_API_URL", "http://127.0.0.1:8741")
CONFIG_DIR = Path.home() / ".devdeploy"
CONFIG_PATH = CONFIG_DIR / "config.json"


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {"api_url": DEFAULT_API}
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _save_config(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def cmd_login(args: argparse.Namespace) -> int:
    cfg = _load_config()
    cfg["api_url"] = args.api_url or cfg.get("api_url") or DEFAULT_API
    cfg["api_key"] = args.token
    _save_config(cfg)
    # Verify
    r = httpx.get(
        f"{cfg['api_url'].rstrip('/')}/api/v1/auth/me",
        headers={"Authorization": f"Bearer {args.token}"},
        timeout=15.0,
    )
    if r.status_code != 200:
        print(f"Login failed: {r.status_code} {r.text}")
        return 1
    user = r.json()
    print(
        f"Logged in as {user.get('email') or user.get('display_name') or user.get('id')}"
    )
    print(f"Config written to {CONFIG_PATH}")
    return 0


def cmd_deploy(args: argparse.Namespace) -> int:
    cfg = _load_config()
    token = cfg.get("api_key")
    if not token:
        print("Not logged in. Run: devdeploy login --token <api-key>")
        return 1
    api = (args.api_url or cfg.get("api_url") or DEFAULT_API).rstrip("/")
    r = httpx.post(
        f"{api}/api/v1/projects/{args.project_id}/deploy",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"environment": args.environment},
        timeout=300.0,
    )
    if r.status_code not in (200, 201):
        print(f"Deploy failed: {r.status_code} {r.text}")
        return 1
    job = r.json()
    print(f"status={job.get('status')} id={job.get('id')}")
    if job.get("app_url"):
        print(f"app_url={job['app_url']}")
    if job.get("public_url"):
        print(f"public_url={job['public_url']}")
    return 0


def cmd_whoami(_: argparse.Namespace) -> int:
    cfg = _load_config()
    token = cfg.get("api_key")
    if not token:
        print("Not logged in")
        return 1
    api = (cfg.get("api_url") or DEFAULT_API).rstrip("/")
    r = httpx.get(
        f"{api}/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15.0,
    )
    print(r.text)
    return 0 if r.status_code == 200 else 1


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="devdeploy", description="DevDeploy CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_login = sub.add_parser("login", help="Store an API key from Settings → API keys")
    p_login.add_argument("--token", required=True, help="API token (dd_…)")
    p_login.add_argument("--api-url", default=None)
    p_login.set_defaults(func=cmd_login)

    p_deploy = sub.add_parser("deploy", help="Trigger a project deploy")
    p_deploy.add_argument("project_id")
    p_deploy.add_argument("--environment", default="development")
    p_deploy.add_argument("--api-url", default=None)
    p_deploy.set_defaults(func=cmd_deploy)

    p_who = sub.add_parser("whoami", help="Show the authenticated user")
    p_who.set_defaults(func=cmd_whoami)

    args = parser.parse_args(argv)
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
