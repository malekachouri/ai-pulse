"""Dependency-injection wiring: settings, DB session, services and the authenticated user."""

import uuid
from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers import AIProviders
from app.core.config import Settings
from app.core.errors import AuthenticationError, PermissionDeniedError
from app.core.metrics import route_template
from app.core.security import decode_access_token
from app.db.session import session_scope
from app.ingestion.queue import CeleryTaskQueue, TaskQueue
from app.models import User
from app.models.enums import RoleName
from app.services.email import ConsoleEmailSender, EmailSender

_bearer = HTTPBearer(auto_error=False)


def _declared_query_params(request: Request) -> dict[tuple[str, str], set[str]]:
    """(route template, METHOD) -> query parameter names, from the OpenAPI schema (computed once per app)."""
    cached = getattr(request.app.state, "_query_params", None)
    if cached is None:
        cached = {}
        for path, ops in request.app.openapi().get("paths", {}).items():
            for method, op in ops.items():
                names = {p["name"] for p in op.get("parameters", []) if p.get("in") == "query"}
                cached[(path, method.upper())] = names
        request.app.state._query_params = cached
    return cached


async def reject_unknown_query_params(request: Request) -> None:
    """Unknown query parameters are a 422, never silently ignored (a misspelt filter must not look valid)."""
    if not request.query_params:
        return
    allowed = _declared_query_params(request).get((route_template(request), request.method))
    if allowed is None:  # route not in the schema (e.g. include_in_schema=False): nothing to check against
        return
    unknown = sorted(set(request.query_params.keys()) - allowed)
    if unknown:
        raise RequestValidationError(
            [
                {"type": "extra_forbidden", "loc": ("query", k), "msg": "Extra inputs are not permitted"}
                for k in unknown
            ]
        )


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async for s in session_scope(request.app.state.session_factory):
        yield s


def get_email_sender(request: Request) -> EmailSender:
    return getattr(request.app.state, "email_sender", None) or ConsoleEmailSender()


def get_ai_providers(request: Request) -> AIProviders:
    return getattr(request.app.state, "ai_providers", None) or AIProviders(None, None)


def get_task_queue(request: Request) -> TaskQueue:
    return getattr(request.app.state, "task_queue", None) or CeleryTaskQueue()


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
QueueDep = Annotated[TaskQueue, Depends(get_task_queue)]
AIDep = Annotated[AIProviders, Depends(get_ai_providers)]
# scope="function": commit/rollback happens before the response is sent, so commit errors surface as 5xx.
SessionDep = Annotated[AsyncSession, Depends(get_session, scope="function")]
EmailDep = Annotated[EmailSender, Depends(get_email_sender)]


async def get_optional_user(
    session: SessionDep,
    settings: SettingsDep,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User | None:
    if creds is None:
        return None
    payload = decode_access_token(settings, creds.credentials)
    try:
        user_id = uuid.UUID(payload["sub"])
    except ValueError as exc:
        raise AuthenticationError("Invalid access token") from exc
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("User not found or disabled")
    return user


async def get_current_user(user: Annotated[User | None, Depends(get_optional_user)]) -> User:
    if user is None:
        raise AuthenticationError("Not authenticated")
    return user


OptionalUser = Annotated[User | None, Depends(get_optional_user)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: RoleName) -> Callable[..., Coroutine[Any, Any, User]]:
    async def _check(user: CurrentUser) -> User:
        if user.role.name not in roles:
            raise PermissionDeniedError("Insufficient permissions")
        return user

    _check.roles = roles  # type: ignore[attr-defined]  # introspected by scripts/build-api-docs.py
    return _check


AdminUser = Annotated[User, Depends(require_roles(RoleName.ADMIN))]
StaffUser = Annotated[User, Depends(require_roles(RoleName.ADMIN, RoleName.ANALYST))]
