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
# optional: copy API URL into the web app
cp .env.example apps/web/.env.local   # or set NEXT_PUBLIC_API_URL only

# 2. Dependencies
make install

# 3. Data services
make up

# 4. Migrations
make migrate

# 5. API (http://127.0.0.1:8741)
make api

# 6. Web (http://127.0.0.1:43127)
make web
```

### Without Docker

If Compose is unavailable, point `DATABASE_URL` and `REDIS_URL` in `.env` at local Postgres 16 and Redis 7 instances with the credentials from `.env.example`, then run `make api` and `make web`.

## Auth model

DevDeploy uses **FastAPI-owned httpOnly session cookies** (not NextAuth/Auth.js).

| Flow | How it works |
|------|----------------|
| Email + password | `POST /api/v1/auth/register` and `/login` |
| Email magic link | Request token → verify (email delivery stubbed; token returned in mock mode) |
| Phone SMS OTP | Start → verify (`AUTH_MOCK_MODE` uses code `000000` by default) |
| Google / GitHub / Apple / Microsoft | `/api/v1/auth/oauth/{provider}/start` → callback |

- Sessions are stored in Postgres (`sessions` table); cookie name defaults to `devdeploy_session`.
- Users can link multiple providers (`auth_identities`); email/phone are unique when present.
- **`AUTH_MOCK_MODE=true` (default)** makes OAuth and SMS demonstrable without real credentials.
- **GitHub App repository install** is intentionally separate from user sign-in.

Web pages: `/login`, `/signup`. `/dashboard` requires a session (client checks `GET /api/v1/auth/me`).

## GitHub App (Milestone 2)

Repo access uses a **GitHub App installation**, not a user PAT.

### Local mock (default)

With `GITHUB_MOCK_MODE=true` (or missing App credentials):

1. Open a project → **Connect mock GitHub App**
2. Pick a mock repo → **Attach**
3. Set deploy branch → **Deploy** (creates a `queued` deployment job)
4. Optional webhook test:

```bash
BODY='{"ref":"refs/heads/main","repository":{"full_name":"mock-org/sample-fastapi-app"},"after":"abc123","head_commit":{"id":"abc123"}}'
SIG="sha256=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "devdeploy-local-webhook-secret" | awk '{print $2}')"
curl -sS -X POST http://127.0.0.1:8741/api/v1/webhooks/github \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: $SIG" \
  -H "X-GitHub-Delivery: $(uuidgen)" \
  -H "X-GitHub-Event: push" \
  -d "$BODY"
```

### Real GitHub App setup

1. Create a GitHub App (Settings → Developer settings → GitHub Apps).
2. Permissions: **Contents** read, **Metadata** read, **Webhooks** receive; subscribe to **push** (and `installation` if desired).
3. Webhook URL: `https://<your-api-host>/api/v1/webhooks/github`
4. Webhook secret → `GITHUB_APP_WEBHOOK_SECRET`
5. Generate a private key; set `GITHUB_APP_ID`, `GITHUB_APP_CLIENT_ID`, `GITHUB_APP_CLIENT_SECRET`, and either `GITHUB_APP_PRIVATE_KEY` (PEM) or `GITHUB_APP_PRIVATE_KEY_PATH`
6. Set `GITHUB_APP_SLUG` to the app slug; set `GITHUB_MOCK_MODE=false`
7. Install the App on orgs/repos you trust, then attach repos from the project UI

With App credentials and `GITHUB_MOCK_MODE=false`, call `POST /api/v1/github/installations/sync` then list repos via installation tokens (App JWT). Mock mode still covers the full attach → queue path locally without an App.

## Health checks

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/health/live` | Process liveness |
| `GET /api/v1/health/ready` | Postgres (+ Redis) readiness |

API docs: [http://127.0.0.1:8741/docs](http://127.0.0.1:8741/docs)

## Pipeline (Milestones 3–6 + real local infra)

Prefer **real Docker/BuildKit + kind** when available (`BUILD_MOCK_MODE=false`, `K8S_MOCK_MODE=false`). Set either flag to `true` for offline/mock demos. AWS stays mocked by default. Details: [`docs/real-infra.md`](docs/real-infra.md).

```bash
make migrate
make api          # drains the queue synchronously on Deploy for demos
# optional background worker:
make worker
make web
make test
```

Lifecycle: `queued → building → publishing → deploying → succeeded|failed`.

- Failed builds **retain** the last healthy release.
- **Rollback** restores the previous release (and `kubectl set image` when kind is live).
- Build logs appear on the project page; metrics/alerts are mock API stubs (`monitoring/` has Prom/Grafana skeletons).
- Terraform under `infrastructure/terraform/` — keep `AWS_MOCK_MODE=true` unless you intentionally `apply` (see that README for cost notes).
- Sample deploy target: `examples/sample-fastapi-app` (`/`, `/health`, `/version`, Dockerfile, tests).

### Five demos
1. Deploy → succeeded with digest + app URL  
2. Webhook push → job (deduped on replay)  
3. Simulated failure → prior release stays current  
4. Rollback to previous digest  
5. Metrics panel on project page  

## Current milestone

**Real local infra:** Docker builds + kind Deployment/Service/Ingress when tools are present; GitHub App mock by default (real JWT/installation-token path when configured); AWS Terraform plan-ready without paid apply.

## License

Private / project use unless otherwise stated.
