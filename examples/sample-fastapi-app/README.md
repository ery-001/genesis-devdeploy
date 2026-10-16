# sample-fastapi-app

Tiny FastAPI HTTP app used as DevDeploy’s first **real** Docker → kind deploy target.

## Endpoints

| Path | Purpose |
|------|---------|
| `GET /` | Hello payload |
| `GET /health` | Readiness/liveness for Kubernetes probes |
| `GET /version` | App version |

## Local run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

## Tests

```bash
pip install -r requirements.txt
pytest -q
```

## Docker

```bash
docker build -t devdeploy/sample-fastapi-app:local .
docker run --rm -p 8000:8000 devdeploy/sample-fastapi-app:local
curl -s http://127.0.0.1:8000/health
```

DevDeploy builds this directory when a project is attached to `mock-org/sample-fastapi-app` (or when `BUILD_CONTEXT_DIR` points here).
