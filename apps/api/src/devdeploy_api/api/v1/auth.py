"""Auth routes: email, magic link, phone OTP, OAuth (mockable)."""

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session as DbSession

from devdeploy_api import auth_service
from devdeploy_api.auth_service import (
    OAUTH_PROVIDERS,
    clear_session_cookie,
    consume_magic_link,
    consume_oauth_state,
    create_session,
    issue_magic_link,
    login_email,
    mock_oauth_profile,
    register_email,
    revoke_session,
    start_oauth_state,
    start_phone_otp,
    upsert_oauth_user,
    user_to_out,
    verify_phone_otp,
)
from devdeploy_api.config import Settings, get_settings
from devdeploy_api.deps import get_current_user, get_db
from devdeploy_api.models import User
from devdeploy_api.schemas import (
    AuthConfigOut,
    LoginRequest,
    MagicLinkRequest,
    MagicLinkVerifyRequest,
    MessageOut,
    PhoneStartRequest,
    PhoneVerifyRequest,
    RegisterRequest,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/config", response_model=AuthConfigOut)
def auth_config(settings: Settings = Depends(get_settings)) -> AuthConfigOut:
    return AuthConfigOut(
        mock_mode=settings.auth_mock_mode,
        providers=["email", "phone", *OAUTH_PROVIDERS],
        session_cookie=settings.session_cookie_name,
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return user_to_out(user)


@router.post("/register", response_model=UserOut)
def register(
    body: RegisterRequest,
    response: Response,
    db: DbSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UserOut:
    user = register_email(
        db,
        email=body.email,
        password=body.password,
        display_name=body.display_name,
    )
    create_session(db, user, settings, response)
    return user_to_out(user)


@router.post("/login", response_model=UserOut)
def login(
    body: LoginRequest,
    response: Response,
    db: DbSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UserOut:
    user = login_email(db, email=body.email, password=body.password)
    create_session(db, user, settings, response)
    return user_to_out(user)


@router.post("/logout", response_model=MessageOut)
def logout(
    request: Request,
    response: Response,
    db: DbSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> MessageOut:
    token = request.cookies.get(settings.session_cookie_name)
    revoke_session(db, token)
    clear_session_cookie(settings, response)
    return MessageOut(message="Signed out")


@router.post("/magic-link/request", response_model=MessageOut)
def magic_link_request(
    body: MagicLinkRequest,
    settings: Settings = Depends(get_settings),
) -> MessageOut:
    token = issue_magic_link(settings, body.email)
    # In production we'd email the link; in mock/dev we return the token.
    return MessageOut(
        message="Magic link issued. Check your email (or use the token in mock mode).",
        mock=settings.auth_mock_mode,
        magic_link_token=token if settings.auth_mock_mode else None,
    )


@router.post("/magic-link/verify", response_model=UserOut)
def magic_link_verify(
    body: MagicLinkVerifyRequest,
    response: Response,
    db: DbSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UserOut:
    user = consume_magic_link(db, body.token)
    create_session(db, user, settings, response)
    return user_to_out(user)


@router.post("/phone/start", response_model=MessageOut)
def phone_start(
    body: PhoneStartRequest,
    settings: Settings = Depends(get_settings),
) -> MessageOut:
    phone = start_phone_otp(settings, body.phone)
    return MessageOut(
        message=f"OTP sent to {phone}",
        mock=settings.auth_mock_mode,
        otp_hint=settings.mock_otp_code if settings.auth_mock_mode else None,
    )


@router.post("/phone/verify", response_model=UserOut)
def phone_verify(
    body: PhoneVerifyRequest,
    response: Response,
    db: DbSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UserOut:
    user = verify_phone_otp(db, settings, body.phone, body.code)
    create_session(db, user, settings, response)
    return user_to_out(user)


@router.get("/oauth/{provider}/start")
def oauth_start(
    provider: str,
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    if provider not in OAUTH_PROVIDERS:
        return RedirectResponse(
            url=f"{settings.web_origin}/login?error=unsupported_provider",
            status_code=302,
        )

    state = start_oauth_state(provider)

    if settings.auth_mock_mode:
        # Mock: bounce straight to callback with a fake code
        qs = urlencode({"code": f"mock-{provider}", "state": state})
        callback = (
            f"{settings.api_public_url}{settings.api_prefix}"
            f"/auth/oauth/{provider}/callback?{qs}"
        )
        return RedirectResponse(url=callback, status_code=302)

    # Real OAuth start stubs — redirect URLs when credentials are configured later
    return RedirectResponse(
        url=f"{settings.web_origin}/login?error=oauth_not_configured&provider={provider}",
        status_code=302,
    )


@router.get("/oauth/{provider}/callback")
def oauth_callback(
    provider: str,
    response: Response,
    db: DbSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> RedirectResponse:
    if error:
        return RedirectResponse(
            url=f"{settings.web_origin}/login?error={error}",
            status_code=302,
        )
    if provider not in OAUTH_PROVIDERS or not code or not state:
        return RedirectResponse(
            url=f"{settings.web_origin}/login?error=oauth_failed",
            status_code=302,
        )

    consume_oauth_state(state, provider)

    if settings.auth_mock_mode:
        profile = mock_oauth_profile(provider)
    else:
        # Real token exchange lands here in a later pass
        return RedirectResponse(
            url=f"{settings.web_origin}/login?error=oauth_not_configured",
            status_code=302,
        )

    user = upsert_oauth_user(
        db,
        provider=provider,
        subject=profile["subject"],
        email=profile["email"],
        display_name=profile["display_name"],
    )
    # Build redirect response with session cookie
    redirect = RedirectResponse(
        url=f"{settings.web_origin}/dashboard",
        status_code=302,
    )
    create_session(db, user, settings, redirect)
    return redirect
