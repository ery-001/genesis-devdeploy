"""DevDeploy FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from devdeploy_api import __version__
from devdeploy_api.api.v1.router import api_router
from devdeploy_api.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description="Control-plane API for DevDeploy — connect a repo, deploy, get a URL.",
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
