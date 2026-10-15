"""Liveness and readiness probes."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from devdeploy_api.db import ping_database
from devdeploy_api.redis_client import ping_redis

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live() -> dict[str, str]:
    return {"status": "ok", "service": "devdeploy-api"}


@router.get("/ready")
def ready() -> JSONResponse:
    checks: dict[str, str] = {}
    overall = "ok"

    try:
        ping_database()
        checks["postgres"] = "ok"
    except Exception as exc:  # noqa: BLE001 — surface readiness failure
        checks["postgres"] = f"error: {exc.__class__.__name__}"
        overall = "degraded"

    if ping_redis():
        checks["redis"] = "ok"
    else:
        checks["redis"] = "error: unreachable"
        overall = "degraded"

    status_code = 200 if overall == "ok" else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": overall, "checks": checks},
    )
