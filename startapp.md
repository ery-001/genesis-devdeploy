# DevDeploy — start the app

Commands to run DevDeploy locally (**Windows-first**, Docker Desktop). Prefer PowerShell in the repo root (example):

`C:\Users\simmy\Documents\GitHub\genesis-devdeploy`

Ports match the Makefile: **API `8741`**, **web `43127`**.

## Prerequisites

- Docker Desktop **running** (WSL2 backend recommended)
- Node.js 20+
- Python 3.12+ and [uv](https://github.com/astral-sh/uv)
- Git
- Optional for real Deploy to kind: `kind`, `kubectl` (see `docs/real-infra.md`)

## One-time setup

```powershell
cd C:\Users\simmy\Documents\GitHub\genesis-devdeploy
git pull origin main

copy .env.example .env
# Edit .env: Auth + GitHub App settings as needed
# Web must talk to the API:
Set-Content -Path apps\web\.env.local -Value "NEXT_PUBLIC_API_URL=http://127.0.0.1:8741"

# Install deps (Makefile if available):
make install
# Or without make:
#   cd apps\api; uv sync
#   cd apps\web; npm install
```

Also ensure `apps\api\.env` exists (API loads cwd env) — copy from root `.env` if needed.

## Start (every session)

**1. Postgres + Redis**

```powershell
make up
# or: docker compose up -d
```

**2. Migrations**

```powershell
make migrate
```

**3. API** (terminal 1) — http://127.0.0.1:8741

```powershell
make api
```

**4. Web** (terminal 2) — http://127.0.0.1:43127

```powershell
make web
```

## Check

- App: http://127.0.0.1:43127  
- API ready: http://127.0.0.1:8741/api/v1/health/ready  
- API docs: http://127.0.0.1:8741/docs  

## Deploy extras (optional)

If Deploy needs Kubernetes (real path: `K8S_MOCK_MODE=false`):

```powershell
# kind + kubectl on PATH; cluster name typically "devdeploy"
kind get clusters
kubectl cluster-info --context kind-devdeploy
```

See `docs/real-infra.md` and `infrastructure/kind/cluster.yaml`.

## Stop

```powershell
# Ctrl+C in api/web terminals, then:
make down
# or: docker compose down
```

## Notes

- Login ≠ repo access: install/sync the **GitHub App** to attach repos (`README.md`, `docs/real-infra.md`).
- Local registry defaults to `LOCAL_REGISTRY=localhost:5001` in `.env.example`; on Windows, prefer `127.0.0.1:5001` if `localhost` hits IPv6 timeouts.
