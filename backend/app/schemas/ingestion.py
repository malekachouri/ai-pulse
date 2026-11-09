import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.enums import JobStatus
from app.schemas.admin import CollectionJobOut


class ConnectorInfo(BaseModel):
    key: str
    description: str
    config_schema: dict[str, Any]


class SourceStatus(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    connector: str
    source_type: str
    url: str
    enabled: bool
    is_official: bool
    poll_interval_minutes: int
    health: str
    health_reason: str
    consecutive_failures: int
    last_success_at: datetime | None
    last_error_at: datetime | None
    last_error: str | None
    last_job: CollectionJobOut | None
    next_run_at: datetime | None
    items_total: int
    items_24h: int


class IngestionOverview(BaseModel):
    generated_at: datetime
    totals: dict[str, int]
    by_health: dict[str, int]
    sources: list[SourceStatus]
    recent_failures: list[CollectionJobOut]


class EnqueueResponse(BaseModel):
    task_id: str
    source_id: uuid.UUID
    status: JobStatus | str = "queued"
