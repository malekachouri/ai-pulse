"""Seed the stack under test with a small, clearly labelled data set (CI and local end-to-end runs only).

Run inside the api container:  docker compose exec -T api python - < e2e/seed.py

Every item is titled "[E2E] ..." and links to example.com, its source is disabled (never scheduled) and
non-official, and items go through the real ingestion writer, so typed records (CVE, incident, paper,
model release, repository) are created exactly as connectors create them. Idempotent.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import create_engine, create_session_factory
from app.ingestion.normalized import (
    IncidentPayload,
    NormalizedItem,
    PaperPayload,
    ReleasePayload,
    RepositoryPayload,
    VulnerabilityPayload,
)
from app.ingestion.writer import ItemWriter
from app.models import Article, DailyBriefing, Source
from app.models.enums import IncidentStatus, ItemType, Severity, VerificationStatus

NOW = datetime.now(UTC)
URL = "https://example.com/e2e"


def ago(hours: float) -> datetime:
    return NOW - timedelta(hours=hours)


def items() -> list[NormalizedItem]:
    v = VerificationStatus.UNVERIFIED
    return [
        NormalizedItem(external_id="e2e-news-1", item_type=ItemType.NEWS, verification=v,
                       title="[E2E] Gemini-style multimodal model announced for agents",
                       url=f"{URL}/news-1", description="[E2E] Test item: a new multimodal model for AI agents.",
                       published_at=ago(3), categories=["ai-models", "ai-agents"]),
        NormalizedItem(external_id="e2e-news-2", item_type=ItemType.NEWS, verification=v,
                       title="[E2E] Retrieval-augmented generation toolkit released",
                       url=f"{URL}/news-2", description="[E2E] Test item about RAG evaluation.",
                       published_at=ago(5), categories=["rag", "ai-tools"]),
        NormalizedItem(external_id="e2e-news-3", item_type=ItemType.NEWS, verification=v,
                       title="[E2E] LLMOps platform adds tracing", url=f"{URL}/news-3",
                       description="[E2E] Test item about LLM observability.", published_at=ago(8),
                       categories=["llmops"]),
        NormalizedItem(external_id="e2e-model-1", item_type=ItemType.MODEL_RELEASE, verification=v,
                       title="[E2E] Example Labs releases Example-7B", url=f"{URL}/model-1",
                       description="[E2E] Test model release.", published_at=ago(4), categories=["ai-models"],
                       content="[E2E] Example-7B scores MMLU 64.2 and reaches 41.0% on HumanEval.",
                       release=ReleasePayload(provider="Example Labs", model_name="Example-7B", version="1.0",
                                              released_at=ago(4), is_open_weights=True,
                                              source_url=f"{URL}/model-1")),
        NormalizedItem(external_id="e2e-model-2", item_type=ItemType.MODEL_RELEASE, verification=v,
                       title="[E2E] Sample AI releases Sample-13B", url=f"{URL}/model-2",
                       description="[E2E] Second test model release.", published_at=ago(7), categories=["ai-models"],
                       content="[E2E] Sample-13B results: MMLU: 68.9, GSM8K 72.4",
                       release=ReleasePayload(provider="Sample AI", model_name="Sample-13B", version="2.0",
                                              released_at=ago(7), is_open_weights=False,
                                              source_url=f"{URL}/model-2")),
        NormalizedItem(external_id="e2e-paper-1", item_type=ItemType.RESEARCH, verification=v,
                       title="[E2E] Reinforcement learning for tool-using agents", url=f"{URL}/paper-1",
                       description="[E2E] Test paper abstract.", published_at=ago(10),
                       categories=["ai-research", "ai-agents"],
                       paper=PaperPayload(arxiv_id="2611.00001", title="[E2E] Reinforcement learning for tool-using agents",
                                          authors=["E2E Author"], abstract="[E2E] Test abstract.",
                                          published_at=ago(10))),
        NormalizedItem(external_id="CVE-2099-0101", item_type=ItemType.VULNERABILITY, verification=v,
                       title="CVE-2099-0101: [E2E] remote code execution in example-kubernetes-operator",
                       url=f"{URL}/cve-1", description="[E2E] Test vulnerability in a Kubernetes operator.",
                       published_at=ago(6), severity=Severity.CRITICAL, severity_basis="E2E fixture CVSS 3.1 9.8",
                       categories=["cybersecurity", "kubernetes"],
                       vulnerability=VulnerabilityPayload(cve_id="CVE-2099-0101", cvss_score=9.8, cvss_version="3.1",
                                                          severity=Severity.CRITICAL, published_at=ago(6),
                                                          description="[E2E] Test vulnerability.",
                                                          references=[{"url": f"{URL}/cve-1"}])),
        NormalizedItem(external_id="CVE-2099-0102", item_type=ItemType.VULNERABILITY, verification=v,
                       title="CVE-2099-0102: [E2E] path traversal in example-web", url=f"{URL}/cve-2",
                       description="[E2E] Test vulnerability, known exploited.", published_at=ago(30),
                       severity=Severity.HIGH, severity_basis="E2E fixture CVSS 3.1 8.1",
                       categories=["cybersecurity"],
                       vulnerability=VulnerabilityPayload(cve_id="CVE-2099-0102", cvss_score=8.1, cvss_version="3.1",
                                                          severity=Severity.HIGH, known_exploited=True,
                                                          kev_date_added=ago(30).date(), published_at=ago(30),
                                                          remediation="[E2E] Apply the vendor update.")),
        NormalizedItem(external_id="e2e-incident-1", item_type=ItemType.INCIDENT, verification=v,
                       title="[E2E] Example Cloud: elevated API error rates", url=f"{URL}/incident-1",
                       description="[E2E] Test incident.", published_at=ago(2), categories=["infrastructure-failures"],
                       incident=IncidentPayload(provider="Example Cloud", external_id="e2e-incident-1",
                                                title="[E2E] Elevated API error rates", status=IncidentStatus.RESOLVED,
                                                status_page_url=f"{URL}/status", impact="minor",
                                                started_at=ago(2), resolved_at=ago(1))),
        NormalizedItem(external_id="e2e-devops-1", item_type=ItemType.DEVOPS, verification=v,
                       title="[E2E] Kubernetes release adds a new scheduler feature", url=f"{URL}/devops-1",
                       description="[E2E] Test DevOps update.", published_at=ago(12),
                       categories=["kubernetes", "devops"]),
        NormalizedItem(external_id="e2e-repo-1", item_type=ItemType.GITHUB_REPO, verification=v,
                       title="example-org/e2e-agent-kit: [E2E] test repository", url=f"{URL}/repo-1",
                       description="[E2E] Test repository for agents.", published_at=ago(48),
                       categories=["ai-agents", "ai-tools"],
                       repository=RepositoryPayload(full_name="example-org/e2e-agent-kit", html_url=f"{URL}/repo-1",
                                                    description="[E2E] Test repository.", language="Python",
                                                    stars=1234, forks=56)),
        # Two releases of the same tool: the newer one gets a "what changed" comparison.
        NormalizedItem(external_id="e2e-rel-1", item_type=ItemType.TOOL, verification=v,
                       title="example-org/e2e-agent-kit v1.0", url=f"{URL}/release-1.0",
                       description="[E2E] First release.", published_at=ago(240), categories=["ai-tools"],
                       content="### Features\n- [E2E] Agent loop\n\nMMLU 70.0\n\nLicensed under the Apache 2.0 license.",
                       canonical_key="gh-release:example-org/e2e-agent-kit:v1.0", tags=["release"]),
        NormalizedItem(external_id="e2e-rel-2", item_type=ItemType.TOOL, verification=v,
                       title="example-org/e2e-agent-kit v1.1", url=f"{URL}/release-1.1",
                       description="[E2E] Second release.", published_at=ago(20), categories=["ai-tools"],
                       content="### Breaking changes\n- [E2E] Removed the old planner\n### Bug fixes\n- [E2E] Fixed retries\n\nMMLU 72.5\n\nLicensed under the MIT license.",
                       canonical_key="gh-release:example-org/e2e-agent-kit:v1.1", tags=["release"]),
    ]  # fmt: skip


async def last_week_briefing(s, src: Source) -> None:  # type: ignore[no-untyped-def]
    """A general briefing dated a week ago, so the weekly report (PDF) of last week has content."""
    day = (NOW - timedelta(days=7)).date()
    if await s.scalar(select(DailyBriefing.id).where(DailyBriefing.user_id.is_(None),
                                                     DailyBriefing.briefing_date == day)):  # fmt: skip
        return
    rows = (await s.scalars(select(Article).where(Article.source_id == src.id).order_by(Article.title))).all()

    def item(a: Article) -> dict:  # type: ignore[type-arg]
        return {"article_id": str(a.id), "title": a.title, "url": a.url, "source": src.name,
                "item_type": a.item_type.value, "published_at": a.published_at.isoformat() if a.published_at else None,
                "importance": 50, "personal_score": 50, "why_for_you": [], "severity": None, "severity_basis": None,
                "summary": None, "summary_is_ai": False}  # fmt: skip

    start = datetime.combine(day, datetime.min.time(), UTC)
    s.add(DailyBriefing(user_id=None, briefing_date=day, period_start=start - timedelta(days=1), period_end=start,
                        generated_at=start, executive_summary="[E2E] Last week's test briefing.",
                        sections={"top_ai": [item(a) for a in rows if a.item_type == ItemType.NEWS][:3],
                                  "devops": [item(a) for a in rows if a.item_type == ItemType.DEVOPS][:2]},
                        cited_article_ids=[str(a.id) for a in rows]))  # fmt: skip


async def main() -> None:
    settings = get_settings()
    engine = create_engine(settings)
    async with create_session_factory(engine)() as s:
        src = await s.scalar(select(Source).where(Source.slug == "e2e-fixtures"))
        if src is None:
            src = Source(slug="e2e-fixtures", name="E2E fixtures (test data)", source_type="api", connector="rss",
                         url=f"{URL}/feed.xml", default_item_type="news", is_official=False, reliability=0.5,
                         enabled=False, config={})  # fmt: skip
            s.add(src)
            await s.flush()
        stats = await ItemWriter(s, src, NOW).save(items())
        await s.commit()
        await last_week_briefing(s, src)
        await s.commit()
        print(f"e2e seed: created={stats.created} updated={stats.updated} skipped={stats.skipped}")
    await engine.dispose()


asyncio.run(main())
