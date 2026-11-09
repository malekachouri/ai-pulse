"""Operational CLI.  Usage: python -m app.cli create-admin --email admin@example.com

The password is read from the ADMIN_PASSWORD env var or prompted interactively (never a CLI arg).
"""

import argparse
import asyncio
import getpass
import os

from app.core.config import get_settings
from app.db.session import create_engine, create_session_factory
from app.models.enums import RoleName
from app.schemas.auth import RegisterRequest
from app.services.auth import AuthService
from app.services.email import ConsoleEmailSender


async def _create_admin(email: str, full_name: str | None) -> None:
    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Admin password: ")
    req = RegisterRequest(email=email, password=password, full_name=full_name)  # validates strength
    settings = get_settings()
    engine = create_engine(settings)
    async with create_session_factory(engine)() as session:
        user = await AuthService(session, settings, ConsoleEmailSender()).register(
            req.email, req.password, req.full_name, role=RoleName.ADMIN
        )
        await session.commit()
        print(f"Created admin {user.email} ({user.id})")
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("create-admin")
    p.add_argument("--email", required=True)
    p.add_argument("--full-name")
    args = parser.parse_args()
    if args.cmd == "create-admin":
        asyncio.run(_create_admin(args.email, args.full_name))


if __name__ == "__main__":
    main()
