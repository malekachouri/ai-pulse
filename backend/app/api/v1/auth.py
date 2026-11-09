from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response, status

from app.api.deps import CurrentUser, EmailDep, SessionDep, SettingsDep
from app.core.config import Settings
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    MessageResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    PasswordResetRequestResponse,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserOut,
)
from app.schemas.common import ErrorResponse
from app.services.auth import AuthService, IssuedTokens

router = APIRouter(prefix="/auth", tags=["auth"], responses={401: {"model": ErrorResponse}})


def _set_refresh_cookie(response: Response, settings: Settings, tokens: IssuedTokens) -> None:
    max_age = int((tokens.refresh_expires_at - datetime.now(UTC)).total_seconds())
    response.set_cookie(
        settings.refresh_cookie_name,
        tokens.refresh_token,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path=f"{settings.api_v1_prefix}/auth",
    )


def _clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        settings.refresh_cookie_name,
        path=f"{settings.api_v1_prefix}/auth",
        secure=settings.cookie_secure,
        httponly=True,
        samesite=settings.cookie_samesite,
    )


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}},
)
async def register(
    body: RegisterRequest, session: SessionDep, settings: SettingsDep, email: EmailDep
) -> UserOut:
    user = await AuthService(session, settings, email).register(body.email, body.password, body.full_name)
    return UserOut.model_validate(user)


@router.post("/login", response_model=TokenResponse, summary="Login; sets an httpOnly refresh cookie")
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    email: EmailDep,
) -> TokenResponse:
    tokens = await AuthService(session, settings, email).login(
        body.email, body.password, request.headers.get("user-agent")
    )
    _set_refresh_cookie(response, settings, tokens)
    return TokenResponse(access_token=tokens.access_token, expires_in=tokens.expires_in)


@router.post(
    "/refresh", response_model=TokenResponse, summary="Rotate the refresh cookie, get a new access token"
)
async def refresh(
    request: Request, response: Response, session: SessionDep, settings: SettingsDep, email: EmailDep
) -> TokenResponse:
    raw = request.cookies.get(settings.refresh_cookie_name)
    tokens = await AuthService(session, settings, email).refresh(raw, request.headers.get("user-agent"))
    _set_refresh_cookie(response, settings, tokens)
    return TokenResponse(access_token=tokens.access_token, expires_in=tokens.expires_in)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request, response: Response, session: SessionDep, settings: SettingsDep, email: EmailDep
) -> MessageResponse:
    await AuthService(session, settings, email).logout(request.cookies.get(settings.refresh_cookie_name))
    _clear_refresh_cookie(response, settings)
    return MessageResponse(message="Logged out")


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut)
async def update_me(body: UpdateProfileRequest, user: CurrentUser, session: SessionDep) -> UserOut:
    if "full_name" in body.model_fields_set:
        user.full_name = body.full_name
    await session.flush()
    return UserOut.model_validate(user)


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    body: ChangePasswordRequest,
    user: CurrentUser,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    email: EmailDep,
) -> MessageResponse:
    await AuthService(session, settings, email).change_password(
        user, body.current_password, body.new_password
    )
    _clear_refresh_cookie(response, settings)
    return MessageResponse(message="Password changed; all sessions were signed out")


@router.post("/password-reset/request", response_model=PasswordResetRequestResponse)
async def request_reset(
    body: PasswordResetRequest, session: SessionDep, settings: SettingsDep, email: EmailDep
) -> PasswordResetRequestResponse:
    raw = await AuthService(session, settings, email).request_password_reset(body.email)
    return PasswordResetRequestResponse(
        message="If an account exists for this email, a reset link has been sent.",
        reset_token=raw if settings.expose_reset_token else None,
    )


@router.post("/password-reset/confirm", response_model=MessageResponse)
async def confirm_reset(
    body: PasswordResetConfirm, session: SessionDep, settings: SettingsDep, email: EmailDep
) -> MessageResponse:
    await AuthService(session, settings, email).reset_password(body.token, body.new_password)
    return MessageResponse(message="Password updated; please sign in")
