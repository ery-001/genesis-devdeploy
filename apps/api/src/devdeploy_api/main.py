"""DevDeploy FastAPI application entrypoint."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
import logging
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from devdeploy_api import __version__
from devdeploy_api.api.v1.router import api_router
from devdeploy_api.config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()


def _restore_access_background() -> None:
    """Re-attach port-forwards + tunnels without blocking API startup."""
    try:
        from devdeploy_api.access_restore import restore_current_releases

        summary = restore_current_releases(settings)
        for line in summary:
            log.info("access-restore: %s", line)
    except Exception:  # noqa: BLE001
        log.exception("access-restore failed on startup")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # uvicorn --reload and kind pod restarts otherwise leave stale Local/Share URLs.
    # Run in a daemon thread so tunnel waits (up to ~60s) do not block /health.
    threading.Thread(
        target=_restore_access_background,
        name="devdeploy-access-restore",
        daemon=True,
    ).start()
    yield


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description="Control-plane API for DevDeploy — connect a repo, deploy, get a URL.",
    lifespan=lifespan,
)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "DevDeploy API",
        "version": __version__,
        "docs": "/docs",
        "health_live": f"{settings.api_prefix}/health/live",
        "health_ready": f"{settings.api_prefix}/health/ready",
    }
