"""Validate and apply project settings from a devdeploy.yaml document."""

from __future__ import annotations

from typing import Any

import yaml

ALLOWED_KEYS = {
    "dockerfile",
    "dockerfile_path",
    "port",
    "container_port",
    "health",
    "health_path",
    "cpu",
    "cpu_request",
    "memory",
    "memory_request",
    "cpu_limit",
    "memory_limit",
    "auto_deploy",
    "replicas",
    "deploy_branch",
    "branch",
}


def parse_devdeploy_yaml(text: str) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return {}, [f"YAML parse error: {exc}"]

    if data is None:
        return {}, ["Document is empty"]
    if not isinstance(data, dict):
        return {}, ["Root must be a mapping"]

    # Allow nested under `app:` or flat
    if "app" in data and isinstance(data["app"], dict):
        cfg = dict(data["app"])
    else:
        cfg = dict(data)

    unknown = [k for k in cfg if k not in ALLOWED_KEYS and k not in ("name", "env")]
    for k in unknown:
        errors.append(f"Unknown key: {k}")

    if "port" in cfg and "container_port" not in cfg:
        cfg["container_port"] = cfg["port"]
    if "dockerfile" in cfg and "dockerfile_path" not in cfg:
        cfg["dockerfile_path"] = cfg["dockerfile"]
    if "health" in cfg and "health_path" not in cfg:
        cfg["health_path"] = cfg["health"]
    if "cpu" in cfg and "cpu_request" not in cfg:
        cfg["cpu_request"] = cfg["cpu"]
    if "memory" in cfg and "memory_request" not in cfg:
        cfg["memory_request"] = cfg["memory"]
    if "branch" in cfg and "deploy_branch" not in cfg:
        cfg["deploy_branch"] = cfg["branch"]

    port = cfg.get("container_port")
    if port is not None:
        try:
            p = int(port)
            if not 1 <= p <= 65535:
                errors.append("container_port must be 1–65535")
            else:
                cfg["container_port"] = p
        except (TypeError, ValueError):
            errors.append("container_port must be an integer")

    if "replicas" in cfg:
        try:
            r = int(cfg["replicas"])
            if not 1 <= r <= 20:
                errors.append("replicas must be 1–20")
            else:
                cfg["replicas"] = r
        except (TypeError, ValueError):
            errors.append("replicas must be an integer")

    if "auto_deploy" in cfg and not isinstance(cfg["auto_deploy"], bool):
        errors.append("auto_deploy must be a boolean")

    for path_key in ("dockerfile_path", "health_path", "deploy_branch"):
        if path_key in cfg and cfg[path_key] is not None:
            if not isinstance(cfg[path_key], str) or not cfg[path_key].strip():
                errors.append(f"{path_key} must be a non-empty string")

    return cfg, errors


def settings_from_parsed(cfg: dict[str, Any]) -> dict[str, Any]:
    """Map parsed yaml keys onto ProjectUpdate fields."""
    out: dict[str, Any] = {}
    mapping = {
        "dockerfile_path": "dockerfile_path",
        "container_port": "container_port",
        "health_path": "health_path",
        "cpu_request": "cpu_request",
        "memory_request": "memory_request",
        "cpu_limit": "cpu_limit",
        "memory_limit": "memory_limit",
        "auto_deploy": "auto_deploy",
        "replicas": "replicas",
        "deploy_branch": "deploy_branch",
    }
    for src, dest in mapping.items():
        if src in cfg and cfg[src] is not None:
            out[dest] = cfg[src]
    return out
