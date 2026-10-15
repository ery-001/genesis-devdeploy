"""Auth domain logic: users, identities, sessions, OTP, magic links."""

from __future__ import annotations

import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import phonenumbers
from fastapi import HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession, joinedload

from devdeploy_api.config import Settings
from devdeploy_api.models import AuthIdentity, Session, User
from devdeploy_api.redis_client import get_redis
from devdeploy_api.schemas import UserOut
from devdeploy_api.security import (
    hash_password,
    hash_session_token,
    new_session_token,
    verify_password,
)

OAUTH_PROVIDERS = ("google", "github", "apple", "microsoft")


def normalize_phone(raw: str) -> str:
    try:
        parsed = phonenumbers.parse(raw, "US")
        # Accept possible numbers so local/mock demos (e.g. 555) work.
        if not phonenumbers.is_possible_number(parsed):
            raise HTTPException(status_code=400, detail="Invalid phone number")
        return phonenumbers.format_number(
            parsed, phonenumbers.PhoneNumberFormat.E164
        )
    except phonenumbers.NumberParseException as exc:
        raise HTTPException(status_code=400, detail="Invalid phone number") from exc


def user_to_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        phone=user.phone,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        providers=sorted({identity.provider for identity in user.identities}),
    )


def create_session(
    db: DbSession,
    user: User,
    settings: Settings,
    response: Response,
) -> None:
    token = new_session_token()
    expires = datetime.now(UTC) + timedelta(seconds=settings.session_ttl_seconds)
    session = Session(
        user_id=user.id,
        token_hash=hash_session_token(token),
        expires_at=expires,
    )
    db.add(session)
    db.commit()

    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=settings.session_ttl_seconds,
        path="/",
    )


def clear_session_cookie(settings: Settings, response: Response) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        samesite="lax",
    )


def get_user_by_session_token(
    db: DbSession, token: str | None
) -> User | None:
    if not token:
        return None
    token_hash = hash_session_token(token)
    now = datetime.now(UTC)
    stmt = (
        select(Session)
        .where(Session.token_hash == token_hash)
        .where(Session.revoked_at.is_(None))
        .where(Session.expires_at > now)
    )
    session = db.execute(stmt).scalar_one_or_none()
    if session is None:
        return None
    user = db.execute(
        select(User)
        .where(User.id == session.user_id)
        .options(joinedload(User.identities))
    ).unique().scalar_one_or_none()
    return user


def revoke_session(db: DbSession, token: str | None) -> None:
    if not token:
        return
    token_hash = hash_session_token(token)
    session = db.execute(
        select(Session).where(Session.token_hash == token_hash)
    ).scalar_one_or_none()
    if session and session.revoked_at is None:
        session.revoked_at = datetime.now(UTC)
        db.commit()


def register_email(
    db: DbSession,
    *,
    email: str,
    password: str,
    display_name: str | None,
) -> User:
    email_norm = email.strip().lower()
    existing = db.execute(
        select(User).where(User.email == email_norm)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=email_norm,
        password_hash=hash_password(password),
        display_name=display_name or email_norm.split("@")[0],
    )
    db.add(user)
    db.flush()
    db.add(
        AuthIdentity(
            user_id=user.id,
            provider="email",
            provider_subject=email_norm,
            email_at_provider=email_norm,
        )
    )
    db.commit()
    db.refresh(user)
    return user


def login_email(db: DbSession, *, email: str, password: str) -> User:
    email_norm = email.strip().lower()
    user = db.execute(
        select(User).where(User.email == email_norm)
    ).scalar_one_or_none()
    if user is None or not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return user


def issue_magic_link(settings: Settings, email: str) -> str:
    email_norm = email.strip().lower()
    token = secrets.token_urlsafe(24)
    redis = get_redis()
    try:
        redis.setex(f"auth:magic:{token}", 900, email_norm)
    finally:
        redis.close()
    return token


def consume_magic_link(db: DbSession, token: str) -> User:
    redis = get_redis()
    try:
        email = redis.get(f"auth:magic:{token}")
        if email is None:
            raise HTTPException(status_code=400, detail="Invalid or expired magic link")
        email_norm = email.decode("utf-8") if isinstance(email, bytes) else str(email)
        redis.delete(f"auth:magic:{token}")
    finally:
        redis.close()

    user = db.execute(
        select(User).where(User.email == email_norm)
    ).scalar_one_or_none()
    if user is None:
        user = User(email=email_norm, display_name=email_norm.split("@")[0])
        db.add(user)
        db.flush()
        db.add(
            AuthIdentity(
                user_id=user.id,
                provider="email",
                provider_subject=email_norm,
                email_at_provider=email_norm,
            )
        )
        db.commit()
        db.refresh(user)
    else:
        _ensure_identity(db, user, "email", email_norm, email_norm)
    return user


def start_phone_otp(settings: Settings, phone: str) -> str:
    phone_norm = normalize_phone(phone)
    code = settings.mock_otp_code if settings.auth_mock_mode else f"{secrets.randbelow(1_000_000):06d}"
    redis = get_redis()
    try:
        redis.setex(f"auth:otp:{phone_norm}", 600, code)
        # Store last mock OTP for debugging in mock mode
        if settings.auth_mock_mode:
            redis.setex(f"auth:otp:last:{phone_norm}", 600, code)
    finally:
        redis.close()
    return phone_norm


def verify_phone_otp(db: DbSession, settings: Settings, phone: str, code: str) -> User:
    phone_norm = normalize_phone(phone)
    redis = get_redis()
    try:
        stored = redis.get(f"auth:otp:{phone_norm}")
        if stored is None:
            raise HTTPException(status_code=400, detail="OTP expired or not requested")
        expected = stored.decode("utf-8") if isinstance(stored, bytes) else str(stored)
        if code.strip() != expected:
            raise HTTPException(status_code=400, detail="Invalid OTP code")
        redis.delete(f"auth:otp:{phone_norm}")
    finally:
        redis.close()

    user = db.execute(
        select(User).where(User.phone == phone_norm)
    ).scalar_one_or_none()
    if user is None:
        user = User(phone=phone_norm, display_name=phone_norm)
        db.add(user)
        db.flush()
        db.add(
            AuthIdentity(
                user_id=user.id,
                provider="phone",
                provider_subject=phone_norm,
            )
        )
        db.commit()
        db.refresh(user)
    else:
        _ensure_identity(db, user, "phone", phone_norm, None)
    return user


def _ensure_identity(
    db: DbSession,
    user: User,
    provider: str,
    subject: str,
    email_at_provider: str | None,
) -> None:
    existing = db.execute(
        select(AuthIdentity).where(
            AuthIdentity.provider == provider,
            AuthIdentity.provider_subject == subject,
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            AuthIdentity(
                user_id=user.id,
                provider=provider,
                provider_subject=subject,
                email_at_provider=email_at_provider,
            )
        )
        db.commit()
        db.refresh(user)


def upsert_oauth_user(
    db: DbSession,
    *,
    provider: str,
    subject: str,
    email: str | None,
    display_name: str | None,
    avatar_url: str | None = None,
) -> User:
    identity = db.execute(
        select(AuthIdentity).where(
            AuthIdentity.provider == provider,
            AuthIdentity.provider_subject == subject,
        )
    ).scalar_one_or_none()
    if identity:
        user = db.get(User, identity.user_id)
        assert user is not None
        return user

    user: User | None = None
    if email:
        email_norm = email.strip().lower()
        user = db.execute(
            select(User).where(User.email == email_norm)
        ).scalar_one_or_none()
        if user:
            # Link provider to existing email account
            db.add(
                AuthIdentity(
                    user_id=user.id,
                    provider=provider,
                    provider_subject=subject,
                    email_at_provider=email_norm,
                )
            )
            if not user.display_name and display_name:
                user.display_name = display_name
            if avatar_url and not user.avatar_url:
                user.avatar_url = avatar_url
            db.commit()
            db.refresh(user)
            return user

    email_norm = email.strip().lower() if email else None
    user = User(
        email=email_norm,
        display_name=display_name or (email_norm.split("@")[0] if email_norm else provider),
        avatar_url=avatar_url,
    )
    db.add(user)
    db.flush()
    db.add(
        AuthIdentity(
            user_id=user.id,
            provider=provider,
            provider_subject=subject,
            email_at_provider=email_norm,
        )
    )
    db.commit()
    db.refresh(user)
    return user


def start_oauth_state(provider: str) -> str:
    if provider not in OAUTH_PROVIDERS:
        raise HTTPException(status_code=400, detail="Unsupported OAuth provider")
    state = secrets.token_urlsafe(16)
    redis = get_redis()
    try:
        redis.setex(
            f"auth:oauth:{state}",
            600,
            json.dumps({"provider": provider}),
        )
    finally:
        redis.close()
    return state


def consume_oauth_state(state: str, provider: str) -> None:
    redis = get_redis()
    try:
        raw = redis.get(f"auth:oauth:{state}")
        if raw is None:
            raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
        data = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        if data.get("provider") != provider:
            raise HTTPException(status_code=400, detail="OAuth provider mismatch")
        redis.delete(f"auth:oauth:{state}")
    finally:
        redis.close()


def mock_oauth_profile(provider: str) -> dict[str, str]:
    subject = f"mock-{provider}-{uuid.uuid4().hex[:8]}"
    return {
        "subject": subject,
        "email": f"{subject}@mock.devdeploy.local",
        "display_name": f"Mock {provider.title()} User",
    }
