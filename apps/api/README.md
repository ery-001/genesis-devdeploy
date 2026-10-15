# DevDeploy API

FastAPI control-plane API for DevDeploy.

## Run locally

```bash
# from repo root
make api
# or
cd apps/api && uv run uvicorn devdeploy_api.main:app --reload --host 0.0.0.0 --port 8741
```

Health:
- `GET /api/v1/health/live`
- `GET /api/v1/health/ready`
