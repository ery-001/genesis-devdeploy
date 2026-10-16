"""API v1 router aggregate."""

from fastapi import APIRouter

from devdeploy_api.api.v1 import (
    auth,
    config_yaml,
    deployments,
    environments,
    github,
    health,
    orgs,
    platform,
    projects,
    variables,
    webhooks,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(projects.router)
api_router.include_router(variables.router)
api_router.include_router(environments.router)
api_router.include_router(config_yaml.router)
api_router.include_router(deployments.router)
api_router.include_router(github.router)
api_router.include_router(webhooks.router)
api_router.include_router(orgs.router)
api_router.include_router(platform.router)
