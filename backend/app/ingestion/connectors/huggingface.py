"""Hugging Face Hub public API.

* `hf_daily_papers` - https://huggingface.co/api/daily_papers (community-curated arXiv papers).
* `hf_models` - https://huggingface.co/api/models?author=ORG (new model repos published by an organisation's
  official account, e.g. meta-llama, mistralai, google). A new repo is a *publication*, not proof of a
  "major release"; titles say exactly that.
"""

from typing import Any

from pydantic import Field

from app.ingestion.base import Connector, ConnectorConfig, FetchResult
from app.ingestion.normalized import NormalizedItem, PaperPayload, ReleasePayload
from app.ingestion.text import parse_dt, truncate
from app.models.enums import ItemType, VerificationStatus

MODALITY = {
    "text-generation": "text",
    "text2text-generation": "text",
    "image-text-to-text": "vision",
    "image-to-text": "vision",
    "text-to-image": "image",
    "automatic-speech-recognition": "audio",
    "text-to-speech": "audio",
    "feature-extraction": "embedding",
    "sentence-similarity": "embedding",
}


class DailyPapersConfig(ConnectorConfig):
    verification: VerificationStatus = VerificationStatus.VERIFIED
    limit: int = Field(50, ge=1, le=100)


class HFDailyPapersConnector(Connector):
    key = "hf_daily_papers"
    description = "Hugging Face daily papers"
    Config = DailyPapersConfig
    config: DailyPapersConfig

    async def fetch(self, checkpoint: dict[str, Any]) -> FetchResult:
        resp = await self.http.get(
            self.source.url, params={"limit": self.config.limit}, rate_limit=self.rate_limit
        )
        return FetchResult(resp.json())

    def normalize(self, record: Any) -> list[NormalizedItem]:
        p = record["paper"]
        arxiv_id = p["id"]
        authors = [a.get("name") for a in p.get("authors", []) if a.get("name") and not a.get("hidden")]
        summary = p.get("summary")
        published = parse_dt(p.get("publishedAt"))
        return [
            NormalizedItem(
                external_id=arxiv_id,
                item_type=ItemType.RESEARCH,
                title=" ".join((p.get("title") or "").split()),
                url=f"https://huggingface.co/papers/{arxiv_id}",
                description=truncate(summary, 2000),
                content=summary,
                author=", ".join(authors[:10]) or None,
                published_at=published,
                source_updated_at=parse_dt(record.get("publishedAt")),
                categories=["ai-research"],
                verification=self.config.verification,
                canonical_key=f"arxiv:{arxiv_id}",
                raw={"upvotes": p.get("upvotes"), "github_repo": p.get("githubRepo")},
                paper=PaperPayload(
                    arxiv_id=arxiv_id,
                    title=" ".join((p.get("title") or "").split()),
                    authors=authors,
                    abstract=summary,
                    published_at=published,
                    pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
                ),
            )
        ]


class HFModelsConfig(ConnectorConfig):
    authors: dict[str, str] = Field(
        description="Hub organisation → provider name, e.g. {'meta-llama': 'Meta'}",
        min_length=1,
    )
    per_author: int = Field(20, ge=1, le=100)


class HFModelsConnector(Connector):
    key = "hf_models"
    description = "New model repositories from official Hugging Face organisations"
    Config = HFModelsConfig
    config: HFModelsConfig

    async def fetch(self, checkpoint: dict[str, Any]) -> FetchResult:
        records: list[Any] = []
        new_cp = dict(checkpoint)
        for org, provider in self.config.authors.items():
            since = parse_dt(checkpoint.get(org))
            resp = await self.http.get(
                self.source.url,
                params={"author": org, "sort": "createdAt", "direction": -1, "limit": self.config.per_author},
                rate_limit=self.rate_limit,
            )
            models = resp.json()
            fresh = [m for m in models if not since or (parse_dt(m.get("createdAt")) or since) > since]
            records.extend((m, provider) for m in fresh)
            if models and models[0].get("createdAt"):
                new_cp[org] = models[0]["createdAt"]
        return FetchResult(records, checkpoint=new_cp)

    def normalize(self, record: Any) -> list[NormalizedItem]:
        m, provider = record
        repo_id = m.get("id") or m["modelId"]
        name = repo_id.split("/", 1)[-1]
        created = parse_dt(m.get("createdAt"))
        url = f"https://huggingface.co/{repo_id}"
        tags = [t for t in m.get("tags", []) if ":" not in t][:15]
        modality = MODALITY.get(m.get("pipeline_tag") or "")
        lic = next((t.split(":", 1)[1] for t in m.get("tags", []) if t.startswith("license:")), None)
        return [
            NormalizedItem(
                external_id=repo_id,
                item_type=ItemType.MODEL_RELEASE,
                title=f"{provider} published {name} on Hugging Face",
                url=url,
                description=f"New model repository {repo_id}"
                + (f" ({m['pipeline_tag']})" if m.get("pipeline_tag") else "")
                + (f", license: {lic}" if lic else "")
                + ".",
                published_at=created,
                tags=tags,
                categories=["ai-models"],
                verification=self.config.verification,
                canonical_key=f"hf-model:{repo_id.lower()}",
                raw={"pipeline_tag": m.get("pipeline_tag"), "license": lic},
                release=ReleasePayload(
                    provider=provider,
                    model_name=name,
                    released_at=created,
                    modality=[modality] if modality else None,
                    homepage_url=url,
                    source_url=url,
                ),
            )
        ]
