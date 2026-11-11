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
from app.models import Source
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
                       release=ReleasePayload(provider="Example Labs", model_name="Example-7B", version="1.0",
                                              released_at=ago(4), is_open_weights=True,
                                              source_url=f"{URL}/model-1")),
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
        print(f"e2e seed: created={stats.created} updated={stats.updated} skipped={stats.skipped}")
    await engine.dispose()


asyncio.run(main())
