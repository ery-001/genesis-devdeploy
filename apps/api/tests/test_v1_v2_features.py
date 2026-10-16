"""V1/V2 feature coverage: settings, secrets, yaml, cancel, envs, roles, stubs."""

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

from devdeploy_api.config import get_settings
from devdeploy_api.db import get_db
from devdeploy_api.main import app

os.environ["BUILD_MOCK_MODE"] = "true"
os.environ["K8S_MOCK_MODE"] = "true"
os.environ["AWS_MOCK_MODE"] = "true"
os.environ["GITHUB_MOCK_MODE"] = "true"
os.environ["SESSION_COOKIE_SECURE"] = "false"
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
    email = f"feat-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "display_name": "Feat"},
    )
    assert r.status_code == 200, r.text


def _project_with_repo(client: TestClient) -> str:
    p = client.post(
        "/api/v1/projects",
        json={"name": "Feat Demo", "description": "test"},
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


def test_project_settings_and_yaml(client: TestClient):
    _auth(client)
    pid = _project_with_repo(client)
    patched = client.patch(
        f"/api/v1/projects/{pid}",
        json={
            "container_port": 8080,
            "health_path": "/healthz",
            "auto_deploy": False,
            "replicas": 2,
            "cpu_request": "200m",
        },
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["container_port"] == 8080
    assert body["health_path"] == "/healthz"
    assert body["auto_deploy"] is False
    assert body["replicas"] == 2

    yaml_text = """
dockerfile: Dockerfile
port: 9000
health: /ready
auto_deploy: true
replicas: 3
"""
    v = client.post(
        f"/api/v1/projects/{pid}/devdeploy-yaml/validate",
        json={"yaml_text": yaml_text},
    )
    assert v.status_code == 200
    assert v.json()["valid"] is True

    applied = client.post(
        f"/api/v1/projects/{pid}/devdeploy-yaml/apply",
        json={"yaml_text": yaml_text},
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["container_port"] == 9000
    assert applied.json()["replicas"] == 3


def test_variables_encrypted_preview(client: TestClient):
    _auth(client)
    pid = _project_with_repo(client)
    created = client.post(
        f"/api/v1/projects/{pid}/variables",
        json={
            "key": "SECRET_TOKEN",
            "value": "super-secret-value",
            "is_secret": True,
            "environment_name": "development",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["value_preview"] == "••••••••"
    assert "super-secret" not in created.text

    listed = client.get(f"/api/v1/projects/{pid}/variables").json()
    assert listed[0]["key"] == "SECRET_TOKEN"
    assert "super-secret" not in json.dumps(listed)


def test_auto_deploy_off_skips_webhook(client: TestClient):
    _auth(client)
    p = client.post(
        "/api/v1/projects",
        json={"name": "No Auto", "description": "test"},
    ).json()
    pid = p["id"]
    inst = client.post("/api/v1/github/installations/mock").json()
    unique_repo = f"mock-org/no-auto-{uuid.uuid4().hex[:8]}"
    assert (
        client.post(
            f"/api/v1/projects/{pid}/github",
            json={
                "installation_id": inst["id"],
                "repo_id": 999001,
                "full_name": unique_repo,
                "default_branch": "main",
                "deploy_branch": "main",
            },
        ).status_code
        == 200
    )
    patched = client.patch(f"/api/v1/projects/{pid}", json={"auto_deploy": False})
    assert patched.json()["auto_deploy"] is False
    body = {
        "ref": "refs/heads/main",
        "repository": {"full_name": unique_repo},
        "after": "deadbeef",
        "head_commit": {"id": "deadbeef"},
    }
    raw = json.dumps(body).encode()
    secret = settings.github_app_webhook_secret.encode()
    sig = "sha256=" + hmac.new(secret, raw, hashlib.sha256).hexdigest()
    r = client.post(
        "/api/v1/webhooks/github",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": sig,
            "X-GitHub-Delivery": str(uuid.uuid4()),
            "X-GitHub-Event": "push",
        },
    )
    assert r.status_code == 200
    assert r.json().get("deployment_job_id") is None
    jobs = client.get(f"/api/v1/projects/{pid}/deployments").json()
    assert jobs == []


def test_cancel_queued_job(client: TestClient):
    _auth(client)
    pid = _project_with_repo(client)
    # Create without processing so it stays queued briefly — process=false
    job = client.post(
        f"/api/v1/projects/{pid}/deploy?process=false",
        json={},
    ).json()
    assert job["status"] in ("queued", "pending_approval")
    cancelled = client.post(
        f"/api/v1/projects/{pid}/deployments/{job['id']}/cancel"
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"


def test_environments_and_prod_approval(client: TestClient):
    _auth(client)
    pid = _project_with_repo(client)
    envs = client.get(f"/api/v1/projects/{pid}/environments").json()
    names = {e["name"] for e in envs}
    assert names == {"development", "staging", "production"}

    prod = next(e for e in envs if e["name"] == "production")
    client.patch(
        f"/api/v1/projects/{pid}/environments/{prod['id']}",
        json={"approval_required": True, "replicas": 3},
    )
    job = client.post(
        f"/api/v1/projects/{pid}/deploy?process=false",
        json={"environment": "production"},
    ).json()
    assert job["status"] == "pending_approval"

    approved = client.post(
        f"/api/v1/projects/{pid}/deployments/{job['id']}/approve"
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "succeeded"


def test_metrics_series_and_scan(client: TestClient):
    _auth(client)
    pid = _project_with_repo(client)
    client.post(f"/api/v1/projects/{pid}/deploy", json={})
    m = client.get(f"/api/v1/projects/{pid}/metrics").json()
    assert m["source"] in ("synthetic", "release-derived")
    assert "cpu" in m["series"]
    assert len(m["series"]["cpu"]) >= 1

    scans = client.get(f"/api/v1/projects/{pid}/scans").json()
    assert len(scans) >= 1
    assert scans[0]["scanner"] in ("mock", "trivy", "mock-fallback")


def test_api_key_and_audit(client: TestClient):
    _auth(client)
    _project_with_repo(client)
    created = client.post("/api/v1/orgs/me/api-keys", json={"name": "cli"})
    assert created.status_code == 201, created.text
    token = created.json()["token"]
    assert token.startswith("dd_")

    # New client using bearer token
    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 200

    audit = client.get("/api/v1/orgs/me/audit").json()
    assert any(a["action"] == "api_key.create" for a in audit)


def test_preview_and_billing_stubs(client: TestClient):
    _auth(client)
    pid = _project_with_repo(client)
    preview = client.post(
        f"/api/v1/projects/{pid}/previews",
        json={"pr_number": 42},
    )
    assert preview.status_code == 201
    assert preview.json()["status"] == "stub"

    billing = client.get("/api/v1/orgs/me/billing").json()
    assert billing["plan"] == "local-free"

    stubs = client.get("/api/v1/orgs/me/stubs").json()
    assert any(s["feature"] == "managed_db" for s in stubs)
