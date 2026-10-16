# Multi-cloud and HA (disabled by default)

DevDeploy’s local path is Docker Compose + kind. **Multi-cloud routing** and **HA control-plane** are intentionally disabled unless you set:

```bash
MULTI_CLOUD_ENABLED=true
HA_ENABLED=true
```

Even then, the UI/API expose toggles and stub state only — they do not provision AWS/GCP or multi-AZ Postgres/Redis without paid accounts and Terraform apply.

- Terraform stubs: `infrastructure/terraform/`
- Keep `AWS_MOCK_MODE=true` for demos
- Org Settings → Commercial / HA stubs records intent without spending
