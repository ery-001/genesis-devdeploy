"""Public HTTPS tunnels for shareable app URLs (cloudflared / ngrok)."""

from __future__ import annotations

import atexit
import logging
import os
import re
import shutil
import subprocess
import sys
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


def _terminate(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:  # noqa: BLE001
        try:
            proc.kill()
        except OSError:
            pass


def _stop_tunnel(slug: str) -> None:
    proc = _TUNNELS.pop(slug, None)
    handle = _TUNNEL_LOG_HANDLES.pop(slug, None)
    _terminate(proc)
    if handle is not None:
        try:
            handle.close()  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass


def _cleanup_tunnels() -> None:
    for slug in list(_TUNNELS):
        _stop_tunnel(slug)


atexit.register(_cleanup_tunnels)


def _popen_kwargs() -> dict:
    kwargs: dict = {"start_new_session": True}
    if sys.platform == "win32":
        # New process group so we can terminate cleanly; survives briefly across
        # parent signals better than the default console group.
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        kwargs.pop("start_new_session", None)
    return kwargs


def _log_tail(log_path: Path, *, lines: int = 40) -> list[str]:
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return text.splitlines()[-lines:]


def _read_until_url(
    proc: subprocess.Popen,
    log_path: Path,
    pattern: re.Pattern[str],
    *,
    timeout: float = 60.0,
) -> str | None:
    deadline = time.time() + timeout
    seen = ""
    while time.time() < deadline:
        if proc.poll() is not None:
            # Process died — do one last read then stop.
            try:
                seen = log_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass
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
            # Common user install location on this machine / Windows agents.
            candidates = [
                Path.home() / ".local" / "bin" / "cloudflared.exe",
                Path.home() / ".local" / "bin" / "cloudflared",
            ]
            for cand in candidates:
                if cand.is_file():
                    binary = str(cand)
                    logs.append(f"cloudflared not on PATH; using {binary}")
                    break
        if not binary:
            logs.append(
                "ERROR: cloudflared not found on PATH — install from "
                "https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/ "
                "or set PUBLIC_TUNNEL_ENABLED=false. Share URL will be unavailable."
            )
            return TunnelResult(public_url=None, provider="cloudflared", logs=logs)
        cmd = [binary, "tunnel", "--url", local, "--no-autoupdate"]
        logs.append(f"$ cloudflared tunnel --url {local}")
        # Line-buffered so URL banners show up promptly for the parent reader.
        log_fh = open(log_path, "w", encoding="utf-8", buffering=1)  # noqa: SIM115
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                **_popen_kwargs(),
            )
        except OSError as exc:
            log_fh.close()
            logs.append(f"ERROR: failed to start cloudflared: {exc}")
            return TunnelResult(public_url=None, provider="cloudflared", logs=logs)
        _TUNNELS[slug] = proc
        _TUNNEL_LOG_HANDLES[slug] = log_fh
        url = _read_until_url(proc, log_path, _CLOUDFLARE_URL_RE, timeout=60.0)
        if url:
            logs.append(f"Public tunnel ready: {url}")
            logs.append(
                "Note: quick tunnels are ephemeral — they last while the API "
                "(cloudflared) process stays running."
            )
            return TunnelResult(public_url=url + "/", provider="cloudflared", logs=logs)
        # Failed to obtain URL — surface details into deployment logs.
        if proc.poll() is not None:
            logs.append(
                f"ERROR: cloudflared exited early (code={proc.returncode}) "
                f"without a trycloudflare.com URL; see {log_path}"
            )
        else:
            logs.append(
                f"ERROR: cloudflared started (pid={proc.pid}) but no "
                f"trycloudflare.com URL within 60s; see {log_path}"
            )
            _stop_tunnel(slug)
        tail = _log_tail(log_path)
        if tail:
            logs.append("--- cloudflared log (tail) ---")
            logs.extend(tail)
        return TunnelResult(public_url=None, provider="cloudflared", logs=logs)

    if provider == "ngrok":
        binary = shutil.which("ngrok")
        token = (settings.ngrok_authtoken or os.environ.get("NGROK_AUTHTOKEN") or "").strip()
        if not binary:
            logs.append("ERROR: ngrok not found on PATH — install ngrok or use cloudflared")
            return TunnelResult(public_url=None, provider="ngrok", logs=logs)
        if not token:
            logs.append(
                "ERROR: NGROK_AUTHTOKEN not set — set it or use PUBLIC_TUNNEL_PROVIDER=cloudflared"
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
        log_fh = open(log_path, "w", encoding="utf-8", buffering=1)  # noqa: SIM115
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                **_popen_kwargs(),
            )
        except OSError as exc:
            log_fh.close()
            logs.append(f"ERROR: failed to start ngrok: {exc}")
            return TunnelResult(public_url=None, provider="ngrok", logs=logs)
        _TUNNELS[slug] = proc
        _TUNNEL_LOG_HANDLES[slug] = log_fh
        url = _read_until_url(proc, log_path, _NGROK_URL_RE, timeout=60.0)
        if url:
            logs.append(f"Public tunnel ready: {url}")
            return TunnelResult(public_url=url + "/", provider="ngrok", logs=logs)
        if proc.poll() is not None:
            logs.append(f"ERROR: ngrok exited early (code={proc.returncode}); see {log_path}")
        else:
            logs.append(f"ERROR: ngrok started but no public URL parsed; see {log_path}")
            _stop_tunnel(slug)
        tail = _log_tail(log_path)
        if tail:
            logs.append("--- ngrok log (tail) ---")
            logs.extend(tail)
        return TunnelResult(public_url=None, provider="ngrok", logs=logs)

    logs.append(f"ERROR: Unknown PUBLIC_TUNNEL_PROVIDER={provider!r}")
    return TunnelResult(public_url=None, provider=provider, logs=logs)
