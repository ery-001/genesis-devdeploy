"""Kubernetes deploy via kubectl/kind (with mock intent fallback)."""

from __future__ import annotations

import atexit
import logging
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from devdeploy_api.config import Settings

log = logging.getLogger(__name__)

# Track port-forwards so redeploys replace them.
_PORT_FORWARDS: dict[str, subprocess.Popen] = {}
_PORT_FORWARD_LOG_HANDLES: dict[str, object] = {}


@dataclass
class DeployResult:
    app_url: str
    namespace: str
    manifests: list[tuple[str, str, dict]]
    logs: list[str] = field(default_factory=list)
    mocked: bool = False
    status: str = "applied"
    public_url: str | None = None


@dataclass
class AccessResult:
    """Local port-forward (+ optional public tunnel) for a running workload."""

    app_url: str
    public_url: str | None
    host_port: int
    logs: list[str] = field(default_factory=list)


def kubectl_available(settings: Settings) -> bool:
    if shutil_which("kubectl") is None:
        return False
    ctx = settings.k8s_context or ""
    cmd = ["kubectl"]
    if ctx:
        cmd += ["--context", ctx]
    cmd += ["cluster-info"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=False)
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def shutil_which(cmd: str) -> str | None:
    from shutil import which

    return which(cmd)


def effective_k8s_mock(settings: Settings) -> bool:
    return bool(settings.k8s_mock_mode)


def _run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=False)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _kubectl(settings: Settings, *args: str) -> tuple[int, str]:
    cmd = ["kubectl"]
    if settings.k8s_context:
        cmd += ["--context", settings.k8s_context]
    cmd += list(args)
    return _run(cmd)


def host_port_for_slug(slug: str, base: int = 18080) -> int:
    """Stable host port in 18080–18200 for port-forward."""
    return base + (sum(ord(c) for c in slug) % 120)


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


def _popen_kwargs() -> dict:
    kwargs: dict = {"start_new_session": True}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        kwargs.pop("start_new_session", None)
    return kwargs


def _stop_port_forward(slug: str) -> None:
    proc = _PORT_FORWARDS.pop(slug, None)
    handle = _PORT_FORWARD_LOG_HANDLES.pop(slug, None)
    _terminate(proc)
    if handle is not None:
        try:
            handle.close()  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass


def _free_host_port(host_port: int, logs: list[str]) -> None:
    """Best-effort: stop an orphan listener left by a previous API process."""
    if sys.platform == "win32":
        try:
            # netstat -ano | findstr :PORT then taskkill — avoid PowerShell dependency.
            out = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            ).stdout
        except Exception as exc:  # noqa: BLE001
            logs.append(f"Could not scan listeners for :{host_port}: {exc}")
            return
        needle = f":{host_port} "
        pids: set[int] = set()
        for line in out.splitlines():
            if "LISTENING" not in line.upper() or needle not in line.replace("\t", " "):
                # Also match ":18150 " with varying spacing
                if f":{host_port}" not in line or "LISTENING" not in line.upper():
                    continue
            parts = line.split()
            if not parts:
                continue
            try:
                pids.add(int(parts[-1]))
            except ValueError:
                continue
        for pid in pids:
            if pid <= 0:
                continue
            try:
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(pid)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                logs.append(f"Freed orphan listener on :{host_port} (pid={pid})")
            except Exception as exc:  # noqa: BLE001
                logs.append(f"Could not kill pid {pid} on :{host_port}: {exc}")
        return
    # Unix: fuser if available
    try:
        subprocess.run(
            ["fuser", "-k", f"{host_port}/tcp"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception:  # noqa: BLE001
        pass


def ensure_port_forward(
    settings: Settings, *, namespace: str, service: str, slug: str
) -> tuple[int, list[str]]:
    """Start kubectl port-forward so the app is reachable on the host."""
    logs: list[str] = []
    host_port = host_port_for_slug(slug)
    _stop_port_forward(slug)
    _free_host_port(host_port, logs)

    cmd = ["kubectl"]
    if settings.k8s_context:
        cmd += ["--context", settings.k8s_context]
    cmd += [
        "-n",
        namespace,
        "port-forward",
        f"svc/{service}",
        f"{host_port}:80",
        "--address=127.0.0.1",
    ]
    log_path = Path(tempfile.gettempdir()) / f"devdeploy-pf-{slug}.log"
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
        logs.append(f"ERROR: failed to start port-forward: {exc}")
        return host_port, logs
    _PORT_FORWARDS[slug] = proc
    _PORT_FORWARD_LOG_HANDLES[slug] = log_fh
    logs.append(f"$ kubectl port-forward svc/{service} {host_port}:80")

    # Wait until the port accepts connections
    import socket

    deadline = time.time() + 20
    ready = False
    while time.time() < deadline:
        if proc.poll() is not None:
            logs.append(f"ERROR: port-forward exited early (code={proc.returncode}); see {log_path}")
            try:
                tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-20:]
                logs.extend(tail)
            except OSError:
                pass
            break
        try:
            with socket.create_connection(("127.0.0.1", host_port), timeout=0.5):
                ready = True
                break
        except OSError:
            time.sleep(0.25)
    if ready:
        logs.append(f"Port-forward ready on 127.0.0.1:{host_port}")
    else:
        logs.append(
            f"ERROR: Port-forward not confirmed on 127.0.0.1:{host_port} "
            f"(pid={proc.pid}); local URL may be unavailable — see {log_path}"
        )
    return host_port, logs


def ensure_app_access(
    settings: Settings,
    *,
    project_slug: str,
    start_tunnel: bool = True,
) -> AccessResult:
    """Port-forward (+ optional public tunnel) for an already-applied workload."""
    namespace = f"dd-{project_slug}"[:63]
    service = f"{project_slug}-svc"
    host_port, logs = ensure_port_forward(
        settings,
        namespace=namespace,
        service=service,
        slug=project_slug,
    )
    app_url = f"http://127.0.0.1:{host_port}/"
    public_url: str | None = None
    if start_tunnel:
        try:
            from devdeploy_api.tunnel import start_public_tunnel

            attempts = 2 if settings.public_tunnel_enabled else 1
            for attempt in range(1, attempts + 1):
                tunnel = start_public_tunnel(
                    settings, local_url=app_url, slug=project_slug
                )
                logs.extend(tunnel.logs)
                public_url = tunnel.public_url
                if public_url:
                    logs.append(f"Shareable public URL: {public_url}")
                    break
                if attempt < attempts:
                    logs.append(
                        f"Public tunnel attempt {attempt} failed — retrying once…"
                    )
                    time.sleep(1.5)
            if settings.public_tunnel_enabled and not public_url:
                logs.append(
                    "ERROR: Public tunnel enabled but no share URL was obtained — "
                    "check cloudflared install/PATH and deployment logs above."
                )
        except Exception as exc:  # noqa: BLE001 — tunnel is best-effort for local URL
            logs.append(f"ERROR: Public tunnel failed (local URL may still work): {exc}")
            log.exception("Public tunnel failed for %s", project_slug)
    return AccessResult(
        app_url=app_url,
        public_url=public_url,
        host_port=host_port,
        logs=logs,
    )


def _cleanup_forwards() -> None:
    for slug in list(_PORT_FORWARDS):
        _stop_port_forward(slug)


atexit.register(_cleanup_forwards)


def _env_yaml(env: dict[str, str] | None) -> str:
    if not env:
        return ""
    lines = ["          env:"]
    for key, value in env.items():
        # Values are injected from decrypted secrets; never echo in logs elsewhere.
        safe_val = value.replace('"', '\\"')
        lines.append(f'            - name: {key}')
        lines.append(f'              value: "{safe_val}"')
    return "\n".join(lines) + "\n"


def render_manifests(
    *,
    project_slug: str,
    namespace: str,
    image: str,
    container_port: int = 8000,
    health_path: str = "/health",
    replicas: int = 1,
    cpu_request: str = "100m",
    memory_request: str = "128Mi",
    cpu_limit: str = "500m",
    memory_limit: str = "512Mi",
    env: dict[str, str] | None = None,
) -> str:
    env_block = _env_yaml(env)
    return f"""apiVersion: v1
kind: Namespace
metadata:
  name: {namespace}
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {project_slug}
  namespace: {namespace}
  labels:
    app: {project_slug}
    managed-by: devdeploy
spec:
  replicas: {max(1, replicas)}
  selector:
    matchLabels:
      app: {project_slug}
  template:
    metadata:
      labels:
        app: {project_slug}
    spec:
      containers:
        - name: app
          image: {image}
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: {container_port}
{env_block}          resources:
            requests:
              cpu: {cpu_request}
              memory: {memory_request}
            limits:
              cpu: {cpu_limit}
              memory: {memory_limit}
          readinessProbe:
            httpGet:
              path: {health_path}
              port: {container_port}
            initialDelaySeconds: 2
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: {health_path}
              port: {container_port}
            initialDelaySeconds: 5
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: {project_slug}-svc
  namespace: {namespace}
spec:
  type: ClusterIP
  selector:
    app: {project_slug}
  ports:
    - name: http
      port: 80
      targetPort: {container_port}
"""


def deploy_to_cluster(
    settings: Settings,
    *,
    project_slug: str,
    image_tag: str,
    image_digest: str,
    container_port: int | None = None,
    health_path: str = "/health",
    replicas: int = 1,
    cpu_request: str = "100m",
    memory_request: str = "128Mi",
    cpu_limit: str = "500m",
    memory_limit: str = "512Mi",
    env: dict[str, str] | None = None,
) -> DeployResult:
    namespace = f"dd-{project_slug}"[:63]
    host = f"{project_slug}.apps.devdeploy.local"
    image_ref = image_tag
    port = container_port or settings.workload_container_port
    manifests_meta = [
        (
            "Deployment",
            project_slug,
            {"image": image_ref, "replicas": max(1, replicas), "port": port},
        ),
        ("Service", f"{project_slug}-svc", {"port": 80, "type": "ClusterIP"}),
    ]

    if effective_k8s_mock(settings):
        logs = [
            "Using mock Kubernetes controller (K8S_MOCK_MODE=true)",
            f"Would apply Deployment/Service in {namespace} (replicas={replicas})",
            f"App URL (mock): https://{host}",
        ]
        return DeployResult(
            app_url=f"https://{host}",
            namespace=namespace,
            manifests=manifests_meta
            + [("Ingress", f"{project_slug}-ing", {"host": host})],
            logs=logs,
            mocked=True,
            status="applied-mock",
        )

    if not kubectl_available(settings):
        raise RuntimeError(
            "K8S_MOCK_MODE=false but kubectl/cluster unavailable. "
            "Create a kind cluster (see infrastructure/kind/cluster.yaml) "
            "or set K8S_MOCK_MODE=true."
        )

    logs: list[str] = ["Using real Kubernetes (kubectl)"]
    yaml_text = render_manifests(
        project_slug=project_slug,
        namespace=namespace,
        image=image_ref,
        container_port=port,
        health_path=health_path,
        replicas=replicas,
        cpu_request=cpu_request,
        memory_request=memory_request,
        cpu_limit=cpu_limit,
        memory_limit=memory_limit,
        env=env,
    )
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as fh:
        fh.write(yaml_text)
        manifest_path = fh.name

    try:
        code, out = _kubectl(settings, "apply", "-f", manifest_path)
        logs.append("$ kubectl apply -f <manifest>")
        logs.extend((out or "").splitlines()[-40:])
        if code != 0:
            raise RuntimeError(f"kubectl apply failed: {out}")

        code, out = _kubectl(
            settings,
            "-n",
            namespace,
            "rollout",
            "status",
            f"deploy/{project_slug}",
            f"--timeout={settings.k8s_rollout_timeout_seconds}s",
        )
        logs.append(f"$ kubectl rollout status deploy/{project_slug}")
        logs.extend((out or "").splitlines()[-30:])
        if code != 0:
            raise RuntimeError(f"Rollout failed: {out}")

        access = ensure_app_access(settings, project_slug=project_slug)
        logs.extend(access.logs)
        logs.append(f"Rollout healthy at {access.app_url}")
        if access.public_url:
            logs.append(f"Shareable public URL: {access.public_url}")

        return DeployResult(
            app_url=access.app_url,
            namespace=namespace,
            manifests=manifests_meta,
            logs=logs,
            mocked=False,
            status="applied",
            public_url=access.public_url,
        )
    finally:
        Path(manifest_path).unlink(missing_ok=True)


def fetch_pod_logs(
    settings: Settings,
    *,
    project_slug: str,
    tail: int = 200,
) -> tuple[list[str], str]:
    """Return recent application logs (kubectl or synthetic mock)."""
    namespace = f"dd-{project_slug}"[:63]
    if effective_k8s_mock(settings) or not kubectl_available(settings):
        return (
            [
                f"[mock] Waiting for traffic on {project_slug}",
                f"[mock] GET {settings.workload_container_port}/health → 200",
                "[mock] Deploy pipeline completed; attach a real cluster for live logs",
            ],
            "mock",
        )
    code, out = _kubectl(
        settings,
        "-n",
        namespace,
        "logs",
        f"deploy/{project_slug}",
        f"--tail={tail}",
        "--all-containers=true",
    )
    if code != 0:
        return ([f"kubectl logs failed: {out.strip()}"], "kubectl-error")
    lines = [ln for ln in (out or "").splitlines() if ln.strip()]
    return (lines[-tail:], "kubectl")


def rollback_workload(
    settings: Settings,
    *,
    project_slug: str,
    image_tag: str,
) -> AccessResult:
    """Point the Deployment back at a previous image and wait for rollout."""
    if effective_k8s_mock(settings) or not kubectl_available(settings):
        return AccessResult(
            app_url=f"https://{project_slug}.apps.devdeploy.local",
            public_url=None,
            host_port=0,
            logs=["Mock/offline rollback — control-plane release pointer updated only"],
        )

    namespace = f"dd-{project_slug}"[:63]
    logs: list[str] = []
    code, out = _kubectl(
        settings,
        "-n",
        namespace,
        "set",
        "image",
        f"deploy/{project_slug}",
        f"app={image_tag}",
    )
    logs.append(f"$ kubectl set image deploy/{project_slug} app={image_tag}")
    logs.extend((out or "").splitlines()[-20:])
    if code != 0:
        raise RuntimeError(f"kubectl set image failed: {out}")
    code, out = _kubectl(
        settings,
        "-n",
        namespace,
        "rollout",
        "status",
        f"deploy/{project_slug}",
        f"--timeout={settings.k8s_rollout_timeout_seconds}s",
    )
    logs.extend((out or "").splitlines()[-20:])
    if code != 0:
        raise RuntimeError(f"Rollback rollout failed: {out}")
    access = ensure_app_access(settings, project_slug=project_slug)
    logs.extend(access.logs)
    logs.append(f"Workload rolled back successfully → {access.app_url}")
    if access.public_url:
        logs.append(f"Shareable public URL: {access.public_url}")
    return AccessResult(
        app_url=access.app_url,
        public_url=access.public_url,
        host_port=access.host_port,
        logs=logs,
    )
