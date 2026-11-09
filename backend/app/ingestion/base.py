"""Connector contract and the run pipeline shared by every source.

    fetch() → normalize() → validate() → deduplicate() → save() → (reconcile) → checkpoint
                         ↘ log_errors() collects per-record failures without aborting the run

A connector only implements `fetch` and `normalize`; validation, dedup and persistence are shared so every
source obeys the same data-quality rules.
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.ingestion.classify import classify
from app.ingestion.http import HttpClient, RateLimit
from app.ingestion.normalized import NormalizedItem
from app.ingestion.writer import ItemWriter, SaveStats
from app.models import Source
from app.models.enums import VerificationStatus

log = get_logger(__name__)

CVE_RE = re.compile(r"^CVE-\d{4}-\d{4,}$")
MAX_LOGGED_ERRORS = 50


class RateLimitConfig(BaseModel):
    limit: int = Field(ge=1, le=1000)
    period: float = Field(ge=1, le=3600)


class ConnectorConfig(BaseModel):
    """Options common to every connector. Unknown keys are rejected so admin typos surface immediately."""

    model_config = ConfigDict(extra="forbid")

    categories: list[str] = Field(default_factory=list, description="Category slugs always applied")
    tags: list[str] = Field(default_factory=list)
    verification: VerificationStatus = VerificationStatus.OFFICIAL
    rate_limit: RateLimitConfig | None = None
    max_items: int = Field(200, ge=1, le=5000, description="Upper bound of records processed per run")


@dataclass
class FetchResult:
    records: list[Any]
    checkpoint: dict[str, Any] | None = None  # new checkpoint to persist after a successful save
    not_modified: bool = False


@dataclass
class RunResult:
    fetched: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    invalid: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)
    checkpoint: dict[str, Any] | None = None
    created_ids: list[Any] = field(default_factory=list)

    @property
    def partial(self) -> bool:
        return bool(self.errors)


class Connector(ABC):
    key: ClassVar[str]
    description: ClassVar[str]
    Config: ClassVar[type[ConnectorConfig]] = ConnectorConfig

    def __init__(self, source: Source, http: HttpClient, settings: Settings) -> None:
        self.source = source
        self.http = http
        self.settings = settings
        self.config = self.Config.model_validate(source.config or {})
        self.errors: list[dict[str, Any]] = []
        self.now: datetime = datetime.min  # set by run()

    # ------------------------------------------------------------------ to implement
    @abstractmethod
    async def fetch(self, checkpoint: dict[str, Any]) -> FetchResult: ...

    @abstractmethod
    def normalize(self, record: Any) -> list[NormalizedItem]: ...

    async def reconcile(self, session: AsyncSession, items: list[NormalizedItem]) -> None:  # noqa: B027
        """Optional post-save hook (e.g. feeds that only list *current* incidents)."""

    # ------------------------------------------------------------------ helpers for connectors
    @property
    def rate_limit(self) -> RateLimit | None:
        rl = self.config.rate_limit
        return RateLimit(rl.limit, rl.period) if rl else None

    def record_error(self, stage: str, error: str, ref: str | None = None) -> None:
        if len(self.errors) < MAX_LOGGED_ERRORS:
            self.errors.append({"stage": stage, "error": error[:500], "ref": ref})

    # ------------------------------------------------------------------ shared stages
    def validate(self, item: NormalizedItem) -> list[str]:
        problems: list[str] = []
        if not item.title.strip():
            problems.append("missing title")
        if not re.match(r"^https?://[^\s/$.?#].[^\s]*$", item.url):
            problems.append(f"invalid original URL: {item.url!r}")
        if not item.categories:
            problems.append("no category")
        if item.published_at and item.published_at > self.now + timedelta(days=1):
            problems.append("publication date is in the future")
        if item.severity is not None and not item.severity_basis:
            problems.append("severity without a documented basis")
        if item.vulnerability and not CVE_RE.match(item.vulnerability.cve_id):
            problems.append(f"invalid CVE id {item.vulnerability.cve_id!r}")
        return problems

    def deduplicate(self, items: list[NormalizedItem]) -> list[NormalizedItem]:
        """In-batch: one item per external_id (the last occurrence wins - feeds list newest updates last
        only rarely, so connectors that care sort first). Cross-source duplicates are linked on save."""
        out: dict[str, NormalizedItem] = {}
        for item in items:
            out[item.external_id] = item
        return list(out.values())

    async def save(self, session: AsyncSession, items: list[NormalizedItem]) -> SaveStats:
        return await ItemWriter(session, self.source, self.now).save(items)

    def log_errors(self) -> None:
        for e in self.errors:
            log.warning("ingestion_record_error", source=self.source.slug, **e)

    def _enrich(self, item: NormalizedItem) -> NormalizedItem:
        text = " ".join(filter(None, [item.title, item.description, " ".join(item.tags)]))
        item.categories = classify(text, [*self.config.categories, *item.categories])
        item.tags = list(dict.fromkeys([*item.tags, *self.config.tags]))
        return item

    # ------------------------------------------------------------------ pipeline
    async def run(self, session: AsyncSession, now: datetime) -> RunResult:
        self.now = now
        result = RunResult()
        fetched = await self.fetch(dict(self.source.checkpoint or {}))
        result.checkpoint = fetched.checkpoint
        if fetched.not_modified:
            return result
        records = fetched.records[: self.config.max_items]
        result.fetched = len(records)

        items: list[NormalizedItem] = []
        for i, record in enumerate(records):
            try:
                items.extend(self._enrich(x) for x in self.normalize(record))
            except Exception as exc:  # noqa: BLE001 - one malformed record must not abort the run
                self.record_error("normalize", f"{type(exc).__name__}: {exc}", ref=str(i))

        valid: list[NormalizedItem] = []
        for item in items:
            problems = self.validate(item)
            if problems:
                result.invalid += 1
                self.record_error("validate", "; ".join(problems), ref=item.external_id)
            else:
                valid.append(item)

        stats = await self.save(session, self.deduplicate(valid))
        await self.reconcile(session, valid)
        result.created, result.updated, result.skipped = stats.created, stats.updated, stats.skipped
        result.created_ids = stats.created_ids
        result.errors = list(self.errors)
        self.log_errors()
        return result
