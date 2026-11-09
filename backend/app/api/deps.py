"""Dependency-injection wiring: settings, DB session, services and the authenticated user."""

import uuid
from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AuthenticationError, PermissionDeniedError
from app.core.security import decode_access_token
from app.db.session import session_scope
from app.ingestion.queue import CeleryTaskQueue, TaskQueue
from app.models import User
from app.models.enums import RoleName
from app.services.email import ConsoleEmailSender, EmailSender

_bearer = HTTPBearer(auto_error=False)


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async for s in session_scope(request.app.state.session_factory):
        yield s


def get_email_sender(request: Request) -> EmailSender:
    return getattr(request.app.state, "email_sender", None) or ConsoleEmailSender()


def get_task_queue(request: Request) -> TaskQueue:
    return getattr(request.app.state, "task_queue", None) or CeleryTaskQueue()


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
QueueDep = Annotated[TaskQueue, Depends(get_task_queue)]
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

    return _check


AdminUser = Annotated[User, Depends(require_roles(RoleName.ADMIN))]
StaffUser = Annotated[User, Depends(require_roles(RoleName.ADMIN, RoleName.ANALYST))]
