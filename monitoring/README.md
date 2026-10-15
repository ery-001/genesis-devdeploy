# Monitoring (Milestone 6)

Stub Prometheus / Grafana / Loki wiring for the control plane and workload plane.

## Files

- `prometheus.yml` — scrape config skeleton (API metrics path reserved)
- `grafana-dashboard.json` — starter dashboard for CPU/memory/uptime (mock series)

## Local without Prometheus

The DevDeploy API serves **mock metrics** at `GET /api/v1/projects/{id}/metrics` so the dashboard works offline. Point Grafana at Prometheus when you run the stack for real.

## Alerts

`GET /api/v1/projects/{id}/alerts` returns stub alert definitions. Wire Alertmanager later.
