"""API v1 router aggregate."""

from fastapi import APIRouter

from devdeploy_api.api.v1 import health

api_router = APIRouter()
api_router.include_router(health.router)
