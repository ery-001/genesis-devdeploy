# GitHub webhook auto-deploy (E2E)

Push to the project's deploy branch → DevDeploy builds and deploys automatically when `auto_deploy` is on.

## Prerequisites

1. API + web running (`startapp.md`).
2. Shareable demo proxy + public HTTPS origin (so GitHub can reach the webhook):

```powershell
.\scripts\start-shareable-demo.ps1 -ApplyEnv
# restart make api / make web
```

3. Project has a GitHub repo attached, `deploy_branch` set (usually `main`), and **Runtime settings → auto_deploy** enabled (default true).

## GitHub App webhook

In the GitHub App settings:

| Field | Value |
|-------|--------|
| Webhook URL | `{API_PUBLIC_URL}/api/v1/webhooks/github` |
| Secret | same as `GITHUB_APP_WEBHOOK_SECRET` in `.env` |
| Events | **Push**, **Pull request** (for PR previews) |

Example with the current tunnel hostname:

```
https://<your-trycloudflare-host>/api/v1/webhooks/github
```

## Push → deploy

1. Push a commit to the deploy branch.
2. GitHub sends `X-GitHub-Event: push` with HMAC signature.
3. API verifies signature, dedupes by `X-GitHub-Delivery`, enqueues a job (`trigger=webhook_push`) if `auto_deploy` and branch match.
4. Worker/pipeline drains the queue; release gets Local + Share URLs.

Check:

- Project → Deployments (newest job `webhook_push`)
- `/deployments/<id>?project=<id>` for **live** build logs (SSE)

## Pull request → preview

On `opened` / `synchronize` / `reopened` / `ready_for_review`:

1. API creates/updates a `PreviewEnvironment` and deploys runtime slug `{project}-pr-{n}`.
2. Share URL (stable proxy mode): `{API_PUBLIC_URL}/apps/{project}-pr-{n}/`
3. Project settings → Preview environments lists status + URL.

Manual preview without a webhook: Project settings → Create preview.

## Auto-deploy gate

| Condition | Result |
|-----------|--------|
| `auto_deploy=false` | Push/PR ignored (no job) |
| Branch ≠ `deploy_branch` | Push ignored |
| Duplicate `X-GitHub-Delivery` | `{ deduped: true }` |

## Local smoke (no GitHub)

```powershell
# Health
Invoke-WebRequest http://127.0.0.1:8741/api/v1/health/ready

# Signed webhook fixture (replace secret if you changed it)
$body = '{"ref":"refs/heads/main","repository":{"full_name":"org/repo"},"head_commit":{"id":"abc"},"after":"abc"}'
# Prefer the GitHub App UI delivery or a real push once the App is pointed at your tunnel.
```

## Stable Share URLs

With `PUBLIC_SHARE_MODE=auto` (default) and an `https://` `API_PUBLIC_URL`, project shares use:

```
{API_PUBLIC_URL}/apps/{slug}/
```

routed by `scripts/demo-proxy.mjs` via `.demo-tunnel/app-routes.json`. After API restart, access-restore re-creates port-forwards and re-registers routes — **the Share URL stays the same**.
