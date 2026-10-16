"""Kubernetes deploy via kubectl/kind (with mock intent fallback)."""

from __future__ import annotations

import atexit
import logging
import os
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from devdeploy_api.config import Settings

log = logging.getLogger(__name__)

# Track port-forwards so redeploys replace them.
_PORT_FORWARDS: dict[str, subprocess.Popen] = {}


@dataclass
class DeployResult:
    app_url: str
    namespace: str
    manifests: list[tuple[str, str, dict]]
    logs: list[str] = field(default_factory=list)
    mocked: bool = False
    status: str = "applied"
    public_url: str | None = None


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


def _stop_port_forward(slug: str) -> None:
    proc = _PORT_FORWARDS.pop(slug, None)
    if proc and proc.poll() is None:
        try:
            os.kill(proc.pid, signal.SIGTERM)
        except OSError:
            pass


def ensure_port_forward(
    settings: Settings, *, namespace: str, service: str, slug: str
) -> tuple[int, list[str]]:
    """Start kubectl port-forward so the app is reachable on the host."""
    logs: list[str] = []
    host_port = host_port_for_slug(slug)
    _stop_port_forward(slug)

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
    log_fh = open(log_path, "w")  # noqa: SIM115 — kept open for subprocess lifetime
    proc = subprocess.Popen(
        cmd,
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    _PORT_FORWARDS[slug] = proc
    logs.append(f"$ kubectl port-forward svc/{service} {host_port}:80")

    # Wait until the port accepts connections
    import socket

    deadline = time.time() + 15
    ready = False
    while time.time() < deadline:
        if proc.poll() is not None:
            logs.append(f"port-forward exited early; see {log_path}")
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
        logs.append(f"Port-forward not confirmed yet (pid={proc.pid}); URL may come up shortly")
    return host_port, logs


def _cleanup_forwards() -> None:
    for slug in list(_PORT_FORWARDS):
        _stop_port_forward(slug)


atexit.register(_cleanup_forwards)


def render_manifests(
    *,
    project_slug: str,
    namespace: str,
    image: str,
    container_port: int = 8000,
) -> str:
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
  replicas: 1
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
          readinessProbe:
            httpGet:
              path: /health
              port: {container_port}
            initialDelaySeconds: 2
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /health
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
) -> DeployResult:
    namespace = f"dd-{project_slug}"[:63]
    host = f"{project_slug}.apps.devdeploy.local"
    image_ref = image_tag
    manifests_meta = [
        ("Deployment", project_slug, {"image": image_ref, "replicas": 1}),
        ("Service", f"{project_slug}-svc", {"port": 80, "type": "ClusterIP"}),
    ]

    if effective_k8s_mock(settings):
        logs = [
            "Using mock Kubernetes controller (K8S_MOCK_MODE=true)",
            f"Would apply Deployment/Service in {namespace}",
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
        container_port=settings.workload_container_port,
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

        host_port, pf_logs = ensure_port_forward(
            settings,
            namespace=namespace,
            service=f"{project_slug}-svc",
            slug=project_slug,
        )
        logs.extend(pf_logs)
        app_url = f"http://127.0.0.1:{host_port}/"
        logs.append(f"Rollout healthy at {app_url}")

        public_url: str | None = None
        try:
            from devdeploy_api.tunnel import start_public_tunnel

            tunnel = start_public_tunnel(
                settings, local_url=app_url, slug=project_slug
            )
            logs.extend(tunnel.logs)
            public_url = tunnel.public_url
            if public_url:
                logs.append(f"Shareable public URL: {public_url}")
        except Exception as exc:  # noqa: BLE001 — tunnel is best-effort
            logs.append(f"Public tunnel failed (local URL still works): {exc}")

        return DeployResult(
            app_url=app_url,
            namespace=namespace,
            manifests=manifests_meta,
            logs=logs,
            mocked=False,
            status="applied",
            public_url=public_url,
        )
    finally:
        Path(manifest_path).unlink(missing_ok=True)


def rollback_workload(
    settings: Settings,
    *,
    project_slug: str,
    image_tag: str,
) -> list[str]:
    """Point the Deployment back at a previous image and wait for rollout."""
    if effective_k8s_mock(settings) or not kubectl_available(settings):
        return ["Mock/offline rollback — control-plane release pointer updated only"]

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
    host_port, pf_logs = ensure_port_forward(
        settings,
        namespace=namespace,
        service=f"{project_slug}-svc",
        slug=project_slug,
    )
    logs.extend(pf_logs)
    logs.append(f"Workload rolled back successfully → http://127.0.0.1:{host_port}/")
    return logs
