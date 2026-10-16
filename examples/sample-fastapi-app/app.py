"""Minimal Dockerfile HTTP app used as DevDeploy's first real deploy target."""

from __future__ import annotations

import os
from datetime import UTC, datetime

from fastapi import FastAPI

APP_NAME = "sample-fastapi-app"
VERSION = os.environ.get("APP_VERSION", "0.1.0")
STARTED_AT = datetime.now(UTC)

app = FastAPI(title=APP_NAME, version=VERSION)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "app": APP_NAME,
        "message": "Hello from DevDeploy sample app",
        "version": VERSION,
        "env": os.environ.get("DEVDEPLOY_ENV", "local"),
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/version")
def version() -> dict[str, str | float]:
    uptime = (datetime.now(UTC) - STARTED_AT).total_seconds()
    return {"app": APP_NAME, "version": VERSION, "uptime_seconds": round(uptime, 1)}
