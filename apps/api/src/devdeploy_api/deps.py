"""FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as DbSession

from devdeploy_api.auth_service import get_user_by_session_token
from devdeploy_api.config import Settings, get_settings
from devdeploy_api.db import SessionLocal
from devdeploy_api.models import User


def get_db() -> Generator[DbSession, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    request: Request,
    db: DbSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    token = request.cookies.get(settings.session_cookie_name)
    user = get_user_by_session_token(db, token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


def get_optional_user(
    request: Request,
    db: DbSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User | None:
    token = request.cookies.get(settings.session_cookie_name)
    return get_user_by_session_token(db, token)
