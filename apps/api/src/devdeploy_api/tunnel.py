"""Public HTTPS tunnels for shareable app URLs (cloudflared / ngrok)."""

from __future__ import annotations

import atexit
import logging
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from devdeploy_api.config import Settings

log = logging.getLogger(__name__)

_TUNNELS: dict[str, subprocess.Popen] = {}
_TUNNEL_LOG_HANDLES: dict[str, object] = {}
_CLOUDFLARE_URL_RE = re.compile(
    r"https://[a-z0-9-]+\.trycloudflare\.com",
    re.IGNORECASE,
)
_NGROK_URL_RE = re.compile(
    r"https://[a-z0-9-]+\.ngrok(?:-free)?\.(?:app|io|dev)",
    re.IGNORECASE,
)


@dataclass
class TunnelResult:
    public_url: str | None
    provider: str
    logs: list[str]


def _stop_tunnel(slug: str) -> None:
    proc = _TUNNELS.pop(slug, None)
    handle = _TUNNEL_LOG_HANDLES.pop(slug, None)
    if proc and proc.poll() is None:
        try:
            os.kill(proc.pid, signal.SIGTERM)
        except OSError:
            pass
    if handle is not None:
        try:
            handle.close()  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass


def _cleanup_tunnels() -> None:
    for slug in list(_TUNNELS):
        _stop_tunnel(slug)


atexit.register(_cleanup_tunnels)


def _read_until_url(
    proc: subprocess.Popen,
    log_path: Path,
    pattern: re.Pattern[str],
    *,
    timeout: float = 45.0,
) -> str | None:
    deadline = time.time() + timeout
    seen = ""
    while time.time() < deadline:
        if proc.poll() is not None and not log_path.exists():
            break
        try:
            text = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        if len(text) > len(seen):
            seen = text
            match = pattern.search(text)
            if match:
                return match.group(0).rstrip("/")
        time.sleep(0.35)
    match = pattern.search(seen)
    return match.group(0).rstrip("/") if match else None


def start_public_tunnel(
    settings: Settings,
    *,
    local_url: str,
    slug: str,
) -> TunnelResult:
    """Expose a local http://127.0.0.1:<port>/ URL via a public tunnel."""
    logs: list[str] = []
    if not settings.public_tunnel_enabled:
        logs.append("PUBLIC_TUNNEL_ENABLED=false — skipping public tunnel")
        return TunnelResult(public_url=None, provider="none", logs=logs)

    provider = (settings.public_tunnel_provider or "cloudflared").strip().lower()
    local = local_url.rstrip("/")
    if not local.startswith("http"):
        local = f"http://{local}"

    _stop_tunnel(slug)
    log_path = Path(tempfile.gettempdir()) / f"devdeploy-tunnel-{slug}.log"

    if provider == "cloudflared":
        binary = shutil.which("cloudflared")
        if not binary:
            logs.append(
                "cloudflared not found on PATH — install from "
                "https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/ "
                "or set PUBLIC_TUNNEL_ENABLED=false"
            )
            return TunnelResult(public_url=None, provider="cloudflared", logs=logs)
        cmd = [binary, "tunnel", "--url", local, "--no-autoupdate"]
        logs.append(f"$ cloudflared tunnel --url {local}")
        log_fh = open(log_path, "w", encoding="utf-8")  # noqa: SIM115
        proc = subprocess.Popen(
            cmd,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        _TUNNELS[slug] = proc
        _TUNNEL_LOG_HANDLES[slug] = log_fh
        url = _read_until_url(proc, log_path, _CLOUDFLARE_URL_RE)
        if url:
            logs.append(f"Public tunnel ready: {url}")
            logs.append(
                "Note: quick tunnels are ephemeral — they last while the API "
                "(cloudflared) process stays running."
            )
            return TunnelResult(public_url=url + "/", provider="cloudflared", logs=logs)
        logs.append(
            f"cloudflared started (pid={proc.pid}) but no trycloudflare.com URL yet; "
            f"see {log_path}"
        )
        return TunnelResult(public_url=None, provider="cloudflared", logs=logs)

    if provider == "ngrok":
        binary = shutil.which("ngrok")
        token = (settings.ngrok_authtoken or os.environ.get("NGROK_AUTHTOKEN") or "").strip()
        if not binary:
            logs.append("ngrok not found on PATH — install ngrok or use cloudflared")
            return TunnelResult(public_url=None, provider="ngrok", logs=logs)
        if not token:
            logs.append(
                "NGROK_AUTHTOKEN not set — set it or use PUBLIC_TUNNEL_PROVIDER=cloudflared"
            )
            return TunnelResult(public_url=None, provider="ngrok", logs=logs)
        # Configure token once per process (best-effort)
        subprocess.run(
            [binary, "config", "add-authtoken", token],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        # local is http://127.0.0.1:PORT
        port = local.rsplit(":", 1)[-1].rstrip("/")
        cmd = [binary, "http", port, "--log=stdout", "--log-format=logfmt"]
        logs.append(f"$ ngrok http {port}")
        log_fh = open(log_path, "w", encoding="utf-8")  # noqa: SIM115
        proc = subprocess.Popen(
            cmd,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        _TUNNELS[slug] = proc
        _TUNNEL_LOG_HANDLES[slug] = log_fh
        url = _read_until_url(proc, log_path, _NGROK_URL_RE)
        if url:
            logs.append(f"Public tunnel ready: {url}")
            return TunnelResult(public_url=url + "/", provider="ngrok", logs=logs)
        logs.append(f"ngrok started but no public URL parsed; see {log_path}")
        return TunnelResult(public_url=None, provider="ngrok", logs=logs)

    logs.append(f"Unknown PUBLIC_TUNNEL_PROVIDER={provider!r}")
    return TunnelResult(public_url=None, provider=provider, logs=logs)
