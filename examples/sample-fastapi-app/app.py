"""Minimal Dockerfile HTTP app used as DevDeploy's first real deploy target."""

from __future__ import annotations

import os

from fastapi import FastAPI

APP_NAME = "sample-fastapi-app"
VERSION = os.environ.get("APP_VERSION", "0.1.0")

app = FastAPI(title=APP_NAME, version=VERSION)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "app": APP_NAME,
        "message": "Hello from DevDeploy sample app",
        "version": VERSION,
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/version")
def version() -> dict[str, str]:
    return {"app": APP_NAME, "version": VERSION}
