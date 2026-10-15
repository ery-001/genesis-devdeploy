# DevDeploy

**DevDeploy** is an internal developer platform: connect a GitHub repo, configure a deploy, and get a working app URL — while keeping the DevOps steps visible and learnable.

This repository is the control-plane monorepo (dashboard + API + data services). Workload-plane pieces (Kubernetes, Jenkins, AWS) arrive in later milestones.

## Monorepo layout

```
apps/web/           Next.js (TypeScript, Tailwind, App Router)
apps/api/           FastAPI + Alembic
infrastructure/     IaC / cluster (placeholder)
ci/                 Build pipelines (placeholder)
monitoring/         Observability stack (placeholder)
examples/           Sample deploy targets
docs/               Project docs
docker-compose.yml  Postgres + Redis
```

## Prerequisites

- Node.js 20+
- Python 3.12+ and [uv](https://github.com/astral-sh/uv)
- Docker + Docker Compose (for Postgres and Redis)

## Quick start

```bash
# 1. Environment
cp .env.example .env

# 2. Dependencies
make install

# 3. Data services
make up

# 4. Migrations (stub for now)
make migrate

# 5. API (http://127.0.0.1:8741)
make api

# 6. Web (http://127.0.0.1:43127)
make web
```

### Without Docker

If Compose is unavailable, point `DATABASE_URL` and `REDIS_URL` in `.env` at local Postgres 16 and Redis 7 instances with the credentials from `.env.example`, then run `make api` and `make web`.

## Health checks

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/health/live` | Process liveness |
| `GET /api/v1/health/ready` | Postgres (+ Redis) readiness |

API docs: [http://127.0.0.1:8741/docs](http://127.0.0.1:8741/docs)

## Current milestone

**Milestone 1 (foundation):** monorepo, Compose, FastAPI health/DB/Alembic skeleton, Next.js landing + dashboard placeholder.

Not yet in this slice: GitHub OAuth, project CRUD, Jenkins, Kubernetes, AWS.

## License

Private / project use unless otherwise stated.
