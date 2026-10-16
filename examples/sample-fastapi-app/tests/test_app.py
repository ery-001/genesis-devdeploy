from fastapi.testclient import TestClient

from app import VERSION, app

client = TestClient(app)


def test_root():
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["app"] == "sample-fastapi-app"
    assert "Hello" in body["message"]


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_version():
    r = client.get("/version")
    assert r.status_code == 200
    assert r.json()["version"] == VERSION
