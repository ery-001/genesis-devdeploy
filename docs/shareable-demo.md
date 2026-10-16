# Shareable demo (single public hostname)

Expose local DevDeploy (API `:8741` + web `:43127`) behind **one** HTTPS hostname so session cookies work for guests who open a public link and sign in with GitHub.

## Why one hostname

Browsers treat separate tunnel hostnames as cross-site. A single reverse proxy keeps `/api/*` and the UI on the same origin, so `SameSite=Lax` cookies work without `SameSite=None` / split CORS.

## Architecture

```
https://<random>.trycloudflare.com
        │
        ▼
cloudflared quick tunnel
        │
        ▼
http://127.0.0.1:18080  (scripts/demo-proxy.mjs)
   ├─ /api/*  → http://127.0.0.1:8741
   └─ /*      → http://127.0.0.1:43127
```

## Prerequisites

1. API and web already running (`make api`, `make web`) — see `startapp.md`.
2. `cloudflared` on PATH (or `%USERPROFILE%\.local\bin\cloudflared.exe`).
3. Node.js 20+.

## Start the public demo

```powershell
cd C:\Users\simmy\Documents\GitHub\genesis-devdeploy

# Proxy + one quick tunnel (prints Public demo URL + GitHub callback URL)
.\scripts\start-shareable-demo.ps1 -ApplyEnv
```

Then **restart API and web** so they load the new public origin:

```powershell
# Ctrl+C existing make api / make web, then:
make api
make web
```

`-ApplyEnv` sets (in `.env`, `apps/api/.env`, `apps/web/.env.local`):

| Variable | Value |
|----------|--------|
| `WEB_ORIGIN` | `https://<public>` |
| `API_PUBLIC_URL` | `https://<public>` |
| `CORS_ORIGINS` | local origins + `https://<public>` |
| `SESSION_COOKIE_SECURE` | `true` |
| `NEXT_PUBLIC_API_URL` | `https://<public>` |

Web calls use paths like `/api/v1/...` against that origin; the proxy forwards them to the API **keeping the path**.

## GitHub App callback (required for login)

You must update the GitHub App **User authorization callback URL** yourself:

```
https://<public>/api/v1/auth/oauth/github/callback
```

Example: if the tunnel prints `https://foo-bar-baz.trycloudflare.com`, set:

```
https://foo-bar-baz.trycloudflare.com/api/v1/auth/oauth/github/callback
```

Quick tunnels mint a **new hostname each run**, so update the callback whenever the public URL changes (or use a named Cloudflare tunnel with a stable hostname).

Homepage URL / setup URL can stay local or match the public origin for the demo session.

## Smoke checks

```powershell
# Local proxy
Invoke-WebRequest http://127.0.0.1:18080/ -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:18080/api/v1/health/ready -UseBasicParsing

# Public (use the printed URL)
Invoke-WebRequest https://<public>/ -UseBasicParsing
Invoke-WebRequest https://<public>/api/v1/health/ready -UseBasicParsing
```

- Page load works before the GitHub callback is updated.
- **GitHub login works only after** you set the callback URL above.

## Stop

End the `cloudflared` process (PID is written under `.demo-tunnel/`) and the Node `demo-proxy` window. Restore local-only env if desired:

```powershell
.\scripts\apply-public-demo-env.ps1 -PublicOrigin http://127.0.0.1:43127
# then manually set API_PUBLIC_URL=http://127.0.0.1:8741,
# NEXT_PUBLIC_API_URL=http://127.0.0.1:8741, SESSION_COOKIE_SECURE=false
```

Or copy values back from `.env.example` / your previous local settings and restart API/web.

## Manual pieces

```powershell
# Terminal A — proxy only
node .\scripts\demo-proxy.mjs

# Terminal B — tunnel
cloudflared tunnel --url http://127.0.0.1:18080

# After URL is known
.\scripts\apply-public-demo-env.ps1 -PublicOrigin https://xxxx.trycloudflare.com
```

## Security notes

- Quick tunnels are ephemeral and unauthenticated at the edge — anyone with the URL can hit your local demo while it runs.
- Never commit real `.env` secrets. Do not paste client secrets into docs or chat.
