# sample-fastapi-app

Minimal Dockerfile HTTP app used as a DevDeploy deploy target.

- `GET /`
- `GET /health`
- `GET /version`

Build locally (when Docker is available):

```bash
docker build -t sample-fastapi-app .
```

In Milestone 3 mock mode, DevDeploy invents an immutable digest without requiring Docker.
