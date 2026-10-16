"""FastAPI dependencies."""

from __future__ import annotations

import hashlib
from collections.abc import Generator
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from devdeploy_api.auth_service import get_user_by_session_token
from devdeploy_api.config import Settings, get_settings
from devdeploy_api.db import SessionLocal
from devdeploy_api.models import ApiKey, OrganizationMember, User


def get_db() -> Generator[DbSession, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _user_from_api_key(db: DbSession, authorization: str | None) -> User | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    if not token.startswith("dd_"):
        return None
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    key = db.execute(
        select(ApiKey).where(
            ApiKey.token_hash == token_hash,
            ApiKey.revoked_at.is_(None),
        )
    ).scalar_one_or_none()
    if key is None:
        return None
    key.last_used_at = datetime.now(UTC)
    # Prefer the creator; else any org owner.
    if key.created_by_user_id:
        user = db.get(User, key.created_by_user_id)
        if user:
            db.commit()
            return user
    membership = db.execute(
        select(OrganizationMember)
        .where(OrganizationMember.organization_id == key.organization_id)
        .where(OrganizationMember.role == "owner")
        .limit(1)
    ).scalar_one_or_none()
    if membership is None:
        db.commit()
        return None
    user = db.get(User, membership.user_id)
    db.commit()
    return user


def get_current_user(
    request: Request,
    db: DbSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    user = _user_from_api_key(db, request.headers.get("Authorization"))
    if user is not None:
        return user
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
    user = _user_from_api_key(db, request.headers.get("Authorization"))
    if user is not None:
        return user
    token = request.cookies.get(settings.session_cookie_name)
    return get_user_by_session_token(db, token)
