# Real Docker + kind infrastructure

DevDeploy prefers **real** builds and local Kubernetes when tools are available. Mocks remain behind flags for CI and machines without Docker/kind.

## Flags

| Env | Default | Behavior |
|-----|---------|----------|
| `BUILD_MOCK_MODE` | `false` | `false` → real `docker build` (errors if Docker down). `true` → mock digest/logs. |
| `K8S_MOCK_MODE` | `false` | `false` → `kubectl apply` Deployment/Service/Ingress. `true` → DB intents only. |
| `AWS_MOCK_MODE` | `true` | Keep `true` unless you intentionally apply Terraform (costs money). |
| `GITHUB_MOCK_MODE` | `true` | Keep mock until a GitHub App is configured. |
| `LOCAL_REGISTRY` | `127.0.0.1:5001` | Optional local registry push after build (use `127.0.0.1` on Windows to avoid `::1` timeouts). |
| `KIND_CLUSTER_NAME` | `devdeploy` | Cluster used by `kind load` + kubectl context `kind-devdeploy`. |
| `K8S_INGRESS_HOST_PORT` | `8088` | Host port mapped to kind ingress (see kind config). |
| `BUILD_CONTEXT_DIR` | _(auto)_ | Override Docker build context (defaults to `examples/sample-fastapi-app`). |

## One-time local setup

```bash
# Docker daemon (systemd or rootless / manual dockerd)
sudo dockerd --host=unix:///var/run/docker.sock &

# Local registry (optional — bind 127.0.0.1 on Windows; push failures fall back to kind load)
docker run -d --restart=always -p 127.0.0.1:5001:5000 --name kind-registry registry:2
docker network connect kind kind-registry || true

# kind + kubectl (ensure both are on PATH for the API process)
kind create cluster --name devdeploy --config infrastructure/kind/cluster.yaml
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.12.0/deploy/static/provider/kind/deploy.yaml
kubectl -n ingress-nginx wait --for=condition=available deploy/ingress-nginx-controller --timeout=180s

# Pipeline: docker build → (optional registry push) → kind load → kubectl apply.
# With K8S_MOCK_MODE=false, missing `kind` is an error (do not silently skip load).

# Point API at real adapters
# apps/api/.env:
BUILD_MOCK_MODE=false
K8S_MOCK_MODE=false
AWS_MOCK_MODE=true
GITHUB_MOCK_MODE=true
```

App URLs after a real deploy use a managed `kubectl port-forward` onto the host
(works even when Docker runs with `--iptables=false`, which breaks kind NodePort host mapping):

`http://127.0.0.1:<18080–18200>/`

The port is stable per project slug. Redeploy replaces the forwarder.

## GitHub App (real path, optional)

Do **not** block local work on creating an App. When ready:

1. Create a GitHub App with **Contents: Read**, **Metadata: Read**, webhook `push`.
2. Webhook URL → `https://<api>/api/v1/webhooks/github` + `GITHUB_APP_WEBHOOK_SECRET`.
3. Set `GITHUB_APP_ID`, private key (`GITHUB_APP_PRIVATE_KEY` or `_PATH`), `GITHUB_APP_SLUG`.
4. `GITHUB_MOCK_MODE=false`
5. Install the App on trusted repos → `POST /api/v1/github/installations/sync` → list repos → attach.

Installation tokens are minted via App JWT (`github_app_auth.py`) for repo listing.

## AWS / Terraform

See `infrastructure/terraform/README.md`. Default stays mocked. With credentials you may run `terraform plan`; only set `AWS_MOCK_MODE=false` and `terraform apply` when you accept EKS/VPC cost.
