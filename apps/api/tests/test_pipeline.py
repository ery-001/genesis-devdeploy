"""Pipeline checks — mock path always; real Docker/kind when available."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from devdeploy_api import build_engine, k8s_engine, pipeline
from devdeploy_api.config import get_settings
from devdeploy_api.db import get_db
from devdeploy_api.main import app


# Force mock adapters for the default suite so CI stays fast/offline-friendly.
os.environ["BUILD_MOCK_MODE"] = "true"
os.environ["K8S_MOCK_MODE"] = "true"
os.environ["AWS_MOCK_MODE"] = "true"
os.environ["GITHUB_MOCK_MODE"] = "true"
get_settings.cache_clear()

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture()
def client():
    get_settings.cache_clear()

    def _override():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def _auth(client: TestClient) -> None:
    email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "display_name": "Tester"},
    )
    assert r.status_code == 200, r.text


def _project_with_repo(client: TestClient) -> str:
    p = client.post(
        "/api/v1/projects",
        json={"name": "Pipe Demo", "description": "test"},
    ).json()
    inst = client.post("/api/v1/github/installations/mock").json()
    attach = client.post(
        f"/api/v1/projects/{p['id']}/github",
        json={
            "installation_id": inst["id"],
            "repo_id": 1001,
            "full_name": "mock-org/sample-fastapi-app",
            "default_branch": "main",
            "deploy_branch": "main",
        },
    )
    assert attach.status_code == 200, attach.text
    return p["id"]


def test_health_ready(client: TestClient):
    r = client.get("/api/v1/health/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_queue_build_deploy_success(client: TestClient):
    _auth(client)
    pid = _project_with_repo(client)
    r = client.post(f"/api/v1/projects/{pid}/deploy", json={})
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["status"] == "succeeded"
    assert job["image_digest"] and job["image_digest"].startswith("sha256:")
    assert job["app_url"]
    assert "Build completed" in (job["build_logs"] or "")
    assert "mock" in (job["build_logs"] or "").lower()

    releases = client.get(f"/api/v1/projects/{pid}/releases").json()
    assert any(x["is_current"] for x in releases)


def test_failed_build_keeps_prior_release(client: TestClient):
    _auth(client)
    pid = _project_with_repo(client)
    ok = client.post(f"/api/v1/projects/{pid}/deploy", json={}).json()
    assert ok["status"] == "succeeded"
    prior_url = ok["app_url"]

    fail = client.post(
        f"/api/v1/projects/{pid}/deploy",
        json={"simulate_failure": True},
    ).json()
    assert fail["status"] == "failed"
    assert "Prior healthy release retained" in (fail["build_logs"] or "")

    releases = client.get(f"/api/v1/projects/{pid}/releases").json()
    current = next(x for x in releases if x["is_current"])
    assert current["app_url"] == prior_url
    assert current["status"] == "healthy"


def test_rollback(client: TestClient):
    _auth(client)
    pid = _project_with_repo(client)
    first = client.post(f"/api/v1/projects/{pid}/deploy", json={}).json()
    second = client.post(f"/api/v1/projects/{pid}/deploy", json={}).json()
    assert first["image_digest"] != second["image_digest"]

    rolled = client.post(f"/api/v1/projects/{pid}/rollback").json()
    assert rolled["is_current"] is True
    assert rolled["image_digest"] == first["image_digest"]


def test_webhook_dedupe(client: TestClient):
    _auth(client)
    pid = _project_with_repo(client)
    body = {
        "ref": "refs/heads/main",
        "repository": {"full_name": "mock-org/sample-fastapi-app"},
        "after": "abc123",
        "head_commit": {"id": "abc123"},
    }
    raw = json.dumps(body).encode()
    secret = settings.github_app_webhook_secret.encode()
    sig = "sha256=" + hmac.new(secret, raw, hashlib.sha256).hexdigest()
    delivery = str(uuid.uuid4())
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": sig,
        "X-GitHub-Delivery": delivery,
        "X-GitHub-Event": "push",
    }
    r1 = client.post("/api/v1/webhooks/github", content=raw, headers=headers)
    assert r1.status_code == 200
    assert r1.json().get("deployment_job_id")
    pipeline.drain_queue(step_delay=0.02)

    r2 = client.post("/api/v1/webhooks/github", content=raw, headers=headers)
    assert r2.json().get("deduped") is True


def test_authz_project_routes(client: TestClient):
    _auth(client)
    pid = _project_with_repo(client)
    email2 = f"other-{uuid.uuid4().hex[:8]}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email2, "password": "password123"},
    )
    r = client.get(f"/api/v1/projects/{pid}")
    assert r.status_code == 404


def test_metrics_endpoint(client: TestClient):
    _auth(client)
    pid = _project_with_repo(client)
    m = client.get(f"/api/v1/projects/{pid}/metrics").json()
    assert m["source"] == "mock"
    assert m["cpu_percent"] >= 0


def test_docker_available_helper():
    # Informational — should not fail the suite either way
    assert isinstance(build_engine.docker_available(), bool)


@pytest.mark.skipif(
    not build_engine.docker_available(),
    reason="Docker daemon not available",
)
def test_real_docker_build_engine():
    get_settings.cache_clear()
    s = get_settings()
    # Temporarily force real build regardless of env defaults used by suite
    s.build_mock_mode = False
    result = build_engine.build_and_publish(
        s,
        project_slug="real-build-test",
        job_id=uuid.uuid4().hex,
        git_ref="main",
        repo_full_name="mock-org/sample-fastapi-app",
        dockerfile_path="Dockerfile",
    )
    assert result.mocked is False
    assert result.digest.startswith("sha256:")
    assert any("real Docker" in line or "BuildKit" in line for line in result.logs)


@pytest.mark.skipif(
    not (
        build_engine.docker_available()
        and k8s_engine.kubectl_available(
            type("S", (), {"k8s_context": "kind-devdeploy"})()
        )
    ),
    reason="Docker + kind cluster not available",
)
def test_real_docker_kind_deploy_via_api(client: TestClient, monkeypatch):
    monkeypatch.setenv("BUILD_MOCK_MODE", "false")
    monkeypatch.setenv("K8S_MOCK_MODE", "false")
    get_settings.cache_clear()

    _auth(client)
    pid = _project_with_repo(client)
    r = client.post(f"/api/v1/projects/{pid}/deploy", json={})
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["status"] == "succeeded", job.get("build_logs")
    assert "Using real Docker" in (job["build_logs"] or "")
    assert "Using real Kubernetes" in (job["build_logs"] or "")
    assert job["app_url"]
    # App should be reachable through kind ingress
    import httpx

    url = job["app_url"].rstrip("/") + "/health"
    resp = httpx.get(url, timeout=20.0)
    assert resp.status_code == 200, resp.text
    assert resp.json().get("status") == "ok"
    get_settings.cache_clear()
