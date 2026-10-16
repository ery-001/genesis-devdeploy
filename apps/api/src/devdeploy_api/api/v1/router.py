"""API v1 router aggregate."""

from fastapi import APIRouter

from devdeploy_api.api.v1 import auth, deployments, github, health, projects, webhooks

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(projects.router)
api_router.include_router(deployments.router)
api_router.include_router(github.router)
api_router.include_router(webhooks.router)
