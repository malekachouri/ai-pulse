"""Daily cleanup: inactive radar entries and finished job logs past their retention; nothing else."""

from datetime import timedelta

from sqlalchemy import select

from app.core.config import Settings
from app.models import AISkill, CollectionJob
from app.models.enums import JobStatus, SkillKind
from app.services.retention import cleanup
from tests import feature_data as fd

NOW = fd.NOW


async def _seed(session_factory):  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        src = await fd.source(s, "ret-src", connector="mcp_registry")

        def skill(name, status, days_ago, updated=True):  # type: ignore[no-untyped-def]
            t = NOW - timedelta(days=days_ago)
            s.add(AISkill(source_id=src.id, kind=SkillKind.MCP_SERVER, name=name, status=status,
                          listing_url=f"https://r.test/{name}", first_seen_at=t, last_seen_at=t,
                          source_updated_at=t if updated else None))  # fmt: skip

        skill("active-old", "active", 400)  # active entries are never deleted
        skill("deprecated-old", "deprecated", 200)
        skill("deleted-recent", "deleted", 30)
        skill("removed-old", "removed", 200, updated=False)  # a plugin that left its marketplace

        def job(status, days_ago):  # type: ignore[no-untyped-def]
            t = NOW - timedelta(days=days_ago)
            finished = None if status in (JobStatus.RUNNING, JobStatus.PENDING) else t
            s.add(CollectionJob(source_id=src.id, status=status, started_at=t, finished_at=finished))

        job(JobStatus.SUCCEEDED, 120)
        job(JobStatus.FAILED, 100)
        job(JobStatus.RUNNING, 120)  # never deleted
        job(JobStatus.PENDING, 120)
        job(JobStatus.PARTIAL, 10)
        await s.commit()


async def test_cleanup_deletes_only_what_retention_allows(session_factory):
    await _seed(session_factory)
    settings = Settings(environment="test", jwt_secret="x" * 40)
    async with session_factory() as s:
        out = await cleanup(s, settings, NOW)
        await s.commit()
        names = set(await s.scalars(select(AISkill.name)))
        jobs = sorted(j.value for j in await s.scalars(select(CollectionJob.status)))
    assert (out.skills_deleted, out.jobs_deleted) == (2, 2)
    assert names == {"active-old", "deleted-recent"}
    assert jobs == ["partial", "pending", "running"]


async def test_zero_keeps_everything(session_factory):
    await _seed(session_factory)
    keep = Settings(environment="test", jwt_secret="x" * 40, retention_inactive_skills_days=0,
                    retention_jobs_days=0)  # fmt: skip
    async with session_factory() as s:
        out = await cleanup(s, keep, NOW)
    assert (out.skills_deleted, out.jobs_deleted) == (0, 0)
