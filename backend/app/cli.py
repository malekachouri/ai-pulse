"""Operational CLI.

    python -m app.cli create-admin --email admin@example.com
    python -m app.cli sources
    python -m app.cli ingest nvd-cve
    python -m app.cli sync-sources

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


async def _list_sources() -> None:
    from sqlalchemy import select

    from app.models import Source

    settings = get_settings()
    engine = create_engine(settings)
    async with create_session_factory(engine)() as s:
        for src in await s.scalars(select(Source).order_by(Source.slug)):
            state = "on " if src.enabled else "off"
            print(f"{state} {src.slug:32} {src.connector:20} every {src.poll_interval_minutes:>4} min  "
                  f"failures={src.consecutive_failures} last_ok={src.last_success_at}")  # fmt: skip
    await engine.dispose()


async def _ingest(slug: str) -> int:
    """Run one source now, in-process (no Celery). Exit code 1 if the run failed."""
    from sqlalchemy import select

    from app.ingestion.http import HttpClient
    from app.ingestion.runner import run_source
    from app.models import Source

    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    async with factory() as s:
        src = await s.scalar(select(Source).where(Source.slug == slug))
    if src is None:
        print(f"Unknown source '{slug}'")
        await engine.dispose()
        return 2
    http = HttpClient()
    try:
        job = await run_source(factory, src.id, settings, http, trigger="manual")
    finally:
        await http.aclose()
        await engine.dispose()
    if job is None:
        print("Skipped: source is already being ingested")
        return 0
    print(f"{slug}: {job.status.value} fetched={job.items_fetched} created={job.items_created} "
          f"updated={job.items_updated} skipped={job.items_skipped} requests={http.requests}")  # fmt: skip
    if job.error:
        print(f"  error: {job.error}")
    for e in (job.errors or [])[:5]:
        print(f"  - {e}")
    return 1 if job.status.value == "failed" else 0


async def _sync_sources() -> None:
    """Insert catalog sources that don't exist yet (never overwrites admin changes)."""
    from sqlalchemy import select

    from app.ingestion.catalog import DEFAULT_SOURCES
    from app.models import Source

    settings = get_settings()
    engine = create_engine(settings)
    async with create_session_factory(engine)() as s:
        existing = set(await s.scalars(select(Source.slug)))
        added = 0
        for src in DEFAULT_SOURCES:
            if src["slug"] not in existing:
                s.add(Source(**{k: v for k, v in src.items() if k != "live_check"}))
                added += 1
        await s.commit()
        print(f"Added {added} source(s)")
    await engine.dispose()


async def _ai_analyze(limit: int, llm_limit: int) -> None:
    """Run the AI pipeline once in-process (deterministic stages always; LLM/embeddings if configured)."""
    from app.ai.pipeline import AnalysisPipeline
    from app.ai.providers import build_providers

    settings = get_settings()
    engine = create_engine(settings)
    providers = build_providers(settings)
    for problem in providers.problems:
        print(f"note: {problem}")
    async with create_session_factory(engine)() as s:
        stats = await AnalysisPipeline(s, providers, daily_budget=settings.ai_daily_token_budget).run(
            stage_a_limit=limit, llm_limit=llm_limit
        )
        await s.commit()
    await providers.aclose()
    await engine.dispose()
    print({k: v for k, v in stats.__dict__.items() if k != "errors"}, "errors:", stats.errors[:3])


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("create-admin")
    p.add_argument("--email", required=True)
    p.add_argument("--full-name")
    sub.add_parser("sources", help="List data sources and their health")
    p = sub.add_parser("ingest", help="Run one source now (without Celery)")
    p.add_argument("slug")
    sub.add_parser("sync-sources", help="Add catalog sources missing from the database")
    p = sub.add_parser("ai-analyze", help="Run the AI pipeline once")
    p.add_argument("--limit", type=int, default=5000)
    p.add_argument("--llm-limit", type=int, default=20)
    args = parser.parse_args()
    if args.cmd == "create-admin":
        asyncio.run(_create_admin(args.email, args.full_name))
    elif args.cmd == "sources":
        asyncio.run(_list_sources())
    elif args.cmd == "ingest":
        raise SystemExit(asyncio.run(_ingest(args.slug)))
    elif args.cmd == "sync-sources":
        asyncio.run(_sync_sources())
    elif args.cmd == "ai-analyze":
        asyncio.run(_ai_analyze(args.limit, args.llm_limit))


if __name__ == "__main__":
    main()
