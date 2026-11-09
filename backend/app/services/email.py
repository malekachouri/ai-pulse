"""Outbound email abstraction. The console sender logs a redacted notice (never the token)."""

from typing import Protocol

from app.core.logging import get_logger

log = get_logger(__name__)


class EmailSender(Protocol):
    async def send(self, to: str, subject: str, body: str) -> None: ...


class ConsoleEmailSender:
    async def send(self, to: str, subject: str, body: str) -> None:
        log.info("email_not_sent_console_backend", to=to, subject=subject)
