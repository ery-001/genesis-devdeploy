"""Docker/BuildKit build + local registry publish (with mock fallback)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from devdeploy_api.config import Settings

log = logging.getLogger(__name__)

def _find_sample_app() -> Path:
    env = os.environ.get("BUILD_CONTEXT_DIR", "").strip()
    if env and Path(env).is_dir():
        return Path(env)
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        candidate = parent / "examples" / "sample-fastapi-app"
        if candidate.is_dir():
            return candidate
    # Workspace default when running from /workspace/apps/api
    fallback = Path("/workspace/examples/sample-fastapi-app")
    return fallback


@dataclass
class BuildResult:
    digest: str
    image_tag: str
    logs: list[str] = field(default_factory=list)
    mocked: bool = False
    context_path: str | None = None


def docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        r = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def effective_build_mock(settings: Settings) -> bool:
    """True → mock builder. False → require real Docker (error if unavailable)."""
    if settings.build_mock_mode:
        return True
    return False


def resolve_build_context(repo_full_name: str | None, dockerfile_path: str | None) -> Path:
    """Prefer the in-repo sample app for mock/sample targets; else BUILD_CONTEXT_DIR."""
    sample = _find_sample_app()
    name = (repo_full_name or "").lower()
    if "sample-fastapi-app" in name or not name or name.startswith("mock-org/"):
        if sample.is_dir():
            return sample

    if sample.is_dir():
        return sample
    raise FileNotFoundError(
        "No build context found. Set BUILD_CONTEXT_DIR or use examples/sample-fastapi-app."
    )


def _run(cmd: list[str], *, cwd: Path | None = None) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out


def _mock_digest(slug: str, job_id: str, git_ref: str) -> str:
    raw = f"{slug}:{job_id}:{git_ref}:{secrets.token_hex(8)}"
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def build_and_publish(
    settings: Settings,
    *,
    project_slug: str,
    job_id: str,
    git_ref: str,
    repo_full_name: str | None,
    dockerfile_path: str | None = "Dockerfile",
) -> BuildResult:
    """Build an image and return an immutable digest.

    When BUILD_MOCK_MODE=true → faithful mock.
    When BUILD_MOCK_MODE=false → real docker buildx/build; raises if Docker missing.
    """
    logs: list[str] = []
    dockerfile = dockerfile_path or "Dockerfile"
    tag_local = f"devdeploy/{project_slug}:{job_id[:8]}"
    registry = settings.local_registry.strip().rstrip("/")
    publish_tag = f"{registry}/devdeploy/{project_slug}:{job_id[:8]}" if registry else tag_local

    if effective_build_mock(settings):
        logs.append("Using mock BuildKit (BUILD_MOCK_MODE=true)")
        logs.append(f"Dockerfile: {dockerfile}")
        logs.append(f"Context: repo={repo_full_name} ref={git_ref}")
        logs.append("Build completed successfully (mock)")
        digest = _mock_digest(project_slug, job_id, git_ref)
        if settings.aws_mock_mode:
            logs.append(f"Mock ECR push → {publish_tag}@{digest[:19]}…")
        else:
            logs.append(f"ECR push configured (real path) → {publish_tag}")
        return BuildResult(
            digest=digest,
            image_tag=publish_tag,
            logs=logs,
            mocked=True,
        )

    if not docker_available():
        raise RuntimeError(
            "BUILD_MOCK_MODE=false but Docker is unavailable. "
            "Start the daemon (dockerd) or set BUILD_MOCK_MODE=true."
        )

    context = resolve_build_context(repo_full_name, dockerfile)
    logs.append("Using real Docker/BuildKit")
    logs.append(f"Dockerfile: {dockerfile}")
    logs.append(f"Context: {context}")
    logs.append(f"Repo: {repo_full_name} ref={git_ref}")

    # Prefer buildx for provenance/digest; fall back to docker build.
    build_cmds = [
        [
            "docker",
            "buildx",
            "build",
            "--load",
            "-f",
            dockerfile,
            "-t",
            tag_local,
            "--progress=plain",
            ".",
        ],
        ["docker", "build", "-f", dockerfile, "-t", tag_local, "--progress=plain", "."],
    ]
    built = False
    for cmd in build_cmds:
        code, out = _run(cmd, cwd=context)
        logs.append(f"$ {' '.join(cmd)}")
        logs.extend(out.splitlines()[-80:] if out else [])
        if code == 0:
            built = True
            break
        logs.append(f"Build command failed (exit {code}); trying fallback…" if cmd is build_cmds[0] else f"Build failed (exit {code})")
    if not built:
        raise RuntimeError("Docker build failed — see build logs")

    # Immutable digest from image inspect
    code, out = _run(["docker", "image", "inspect", tag_local, "--format", "{{json .RepoDigests}}"])
    digest = ""
    if code == 0 and out.strip():
        try:
            digests = json.loads(out.strip())
            if digests:
                digest = digests[0].split("@", 1)[-1]
        except json.JSONDecodeError:
            digest = ""
    if not digest:
        code, out = _run(["docker", "image", "inspect", tag_local, "--format", "{{.Id}}"])
        image_id = out.strip()
        if image_id.startswith("sha256:"):
            digest = image_id
        else:
            digest = "sha256:" + hashlib.sha256(image_id.encode()).hexdigest()

    logs.append(f"Build completed successfully — digest {digest[:19]}…")

    # Tag + push to local registry when configured
    if registry:
        code, out = _run(["docker", "tag", tag_local, publish_tag])
        logs.extend((out or "").splitlines()[-20:])
        if code != 0:
            raise RuntimeError(f"docker tag failed: {out}")
        code, out = _run(["docker", "push", publish_tag])
        logs.append(f"$ docker push {publish_tag}")
        logs.extend((out or "").splitlines()[-40:])
        if code != 0:
            # kind load still works without registry push
            logs.append(
                f"Registry push failed (exit {code}); will load image into kind directly"
            )
            publish_tag = tag_local
        else:
            # Prefer registry digest if present
            code, out = _run(
                ["docker", "image", "inspect", publish_tag, "--format", "{{index .RepoDigests 0}}"]
            )
            if code == 0 and "@" in out:
                digest = out.strip().split("@", 1)[-1]
            logs.append(f"Published {publish_tag}@{digest[:19]}…")
    else:
        publish_tag = tag_local
        logs.append(f"No local registry configured; using local tag {publish_tag}")

    if settings.aws_mock_mode:
        logs.append("AWS_MOCK_MODE=true — skipped real ECR (local registry / kind load)")
    elif settings.ecr_registry:
        ecr_tag = f"{settings.ecr_registry.rstrip('/')}/devdeploy/{project_slug}:{job_id[:8]}"
        logs.append(f"ECR push configured → {ecr_tag} (run docker push with AWS creds)")

    return BuildResult(
        digest=digest if digest.startswith("sha256:") else f"sha256:{digest}",
        image_tag=publish_tag,
        logs=logs,
        mocked=False,
        context_path=str(context),
    )


def kind_load_image(image_tag: str, cluster_name: str) -> list[str]:
    """Load a local image into kind so pods can use imagePullPolicy: Never/IfNotPresent."""
    lines: list[str] = []
    if shutil.which("kind") is None:
        lines.append("kind CLI not found — skip kind load")
        return lines
    code, out = _run(["kind", "load", "docker-image", image_tag, "--name", cluster_name])
    lines.append(f"$ kind load docker-image {image_tag} --name {cluster_name}")
    lines.extend((out or "").splitlines()[-30:])
    if code != 0:
        raise RuntimeError(f"kind load failed: {out}")
    lines.append("Image loaded into kind node")
    return lines
