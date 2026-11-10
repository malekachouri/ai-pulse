"""SMTP delivery (against an in-process SMTP server), reset-link emails, and failure isolation."""

import asyncio
import re
import threading
from email import message_from_bytes

import pytest

from app.core.config import Settings
from app.services.email import (
    ConsoleEmailSender,
    DeferredEmailSender,
    EmailDeliveryError,
    SmtpEmailSender,
    build_email_sender,
)
from tests.conftest import register_and_login

AUTH = "/api/v1/auth"


class TinySmtpServer:
    """Just enough RFC 5321 for smtplib (EHLO, AUTH PLAIN, MAIL, RCPT, DATA, QUIT), in a thread."""

    def __init__(self) -> None:
        self.messages: list[bytes] = []
        self.auth: list[str] = []
        self.loop = asyncio.new_event_loop()
        self.ready = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.write(b"220 tiny ESMTP\r\n")
        while line := await reader.readline():
            cmd = line.decode().strip()
            verb = cmd.split(" ", 1)[0].upper()
            if verb == "EHLO":
                writer.write(b"250-tiny\r\n250 AUTH PLAIN\r\n")
            elif verb == "AUTH":
                self.auth.append(cmd)
                writer.write(b"235 ok\r\n")
            elif verb == "DATA":
                writer.write(b"354 go\r\n")
                await writer.drain()
                data = b""
                while (chunk := await reader.readline()) != b".\r\n":
                    data += chunk
                self.messages.append(data)
                writer.write(b"250 queued\r\n")
            elif verb == "QUIT":
                writer.write(b"221 bye\r\n")
                await writer.drain()
                break
            else:
                writer.write(b"250 ok\r\n")
            await writer.drain()
        writer.close()

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        server = self.loop.run_until_complete(asyncio.start_server(self._handle, "127.0.0.1", 0))
        self.port = server.sockets[0].getsockname()[1]
        self.ready.set()
        self.loop.run_forever()

    def __enter__(self) -> TinySmtpServer:
        self.thread.start()
        self.ready.wait(5)
        return self

    def __exit__(self, *exc: object) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)


async def test_smtp_sender_delivers_with_auth():
    with TinySmtpServer() as srv:
        sender = SmtpEmailSender("127.0.0.1", srv.port, "AI Pulse <no-reply@pulse.test>",
                                 username="mailer", password="s3cret", security="none")  # fmt: skip
        await sender.send("rita@example.com", "Hello", "Body line\n")
    msg = message_from_bytes(srv.messages[0])
    assert msg["To"] == "rita@example.com" and msg["Subject"] == "Hello" and "pulse.test" in msg["Message-ID"]
    assert "Body line" in msg.get_payload() and srv.auth and srv.auth[0].startswith("AUTH PLAIN")


async def test_smtp_failure_is_an_email_delivery_error():
    sender = SmtpEmailSender("127.0.0.1", 9, "x@pulse.test", security="none", timeout=2)  # nothing listens
    with pytest.raises(EmailDeliveryError):
        await sender.send("a@example.com", "s", "b")


async def test_deferred_sender_swallows_failures():
    outbox = DeferredEmailSender(SmtpEmailSender("127.0.0.1", 9, "x@pulse.test", security="none", timeout=2))
    await outbox.send("a@example.com", "s", "b")
    await outbox.flush()  # must not raise: the requester already got the generic answer
    assert outbox.outbox == []


def test_sender_selection_from_settings():
    assert isinstance(build_email_sender(Settings(smtp_host="")), ConsoleEmailSender)
    s = build_email_sender(Settings(smtp_host="smtp.example.com", smtp_from="AI Pulse <a@example.com>"))
    assert isinstance(s, SmtpEmailSender) and s.port == 587 and s.security == "starttls"


@pytest.fixture
def public_url_settings(settings):
    settings.public_url = "https://pulse.example.com/"
    yield settings
    settings.public_url = None


async def test_reset_email_contains_a_link_when_public_url_is_set(client, email_sender, public_url_settings):
    await register_and_login(client, "link@example.com")
    r = await client.post(f"{AUTH}/password-reset/request", json={"email": "link@example.com"})
    assert r.status_code == 200
    body = email_sender.sent[-1][2]
    token = re.search(r"https://pulse\.example\.com/reset-password\?token=(\S+)", body).group(1)
    r = await client.post(
        f"{AUTH}/password-reset/confirm", json={"token": token, "new_password": "Brand-new-Pass9"}
    )
    assert r.status_code == 200


async def test_reset_request_answer_does_not_depend_on_the_account(client, email_sender):
    await register_and_login(client, "known@example.com")
    known = await client.post(f"{AUTH}/password-reset/request", json={"email": "known@example.com"})
    unknown = await client.post(f"{AUTH}/password-reset/request", json={"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 200 and known.json() == unknown.json()
    assert [to for to, *_ in email_sender.sent] == ["known@example.com"]
