import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import JobStatus, RoleName
from app.schemas.auth import UserOut
from app.schemas.common import ORMModel
from app.schemas.intel import DateRangeMixin, ListParams


class AdminUserFilters(ListParams):
    q: str | None = Field(None, max_length=200, description="Matches email or name")
    role: RoleName | None = None
    is_active: bool | None = None

    @field_validator("q")
    @classmethod
    def _q(cls, v: str | None) -> str | None:
        return (v.strip() or None) if v else None


class AdminUserUpdate(BaseModel):
    role: RoleName | None = None
    is_active: bool | None = None


class AdminUserOut(UserOut):
    updated_at: datetime


class RoleOut(BaseModel):
    id: int
    name: RoleName
    description: str | None
    user_count: int


class JobFilters(ListParams, DateRangeMixin):
    source: list[str] | None = Field(None, description="Source slugs")
    status: list[JobStatus] | None = None


class SourceRef(ORMModel):
    id: uuid.UUID
    slug: str
    name: str


class CollectionJobOut(ORMModel):
    id: uuid.UUID
    source_id: uuid.UUID
    status: JobStatus
    trigger: str
    celery_task_id: str | None
    started_at: datetime
    finished_at: datetime | None
    duration_seconds: float | None = None
    items_fetched: int
    items_created: int
    items_updated: int
    items_skipped: int
    attempt: int
    error: str | None
    errors: list[dict[str, Any]]
    source: SourceRef | None = None


class AuditFilters(ListParams, DateRangeMixin):
    action: str | None = Field(None, max_length=100)
    actor_id: uuid.UUID | None = None
    target_type: str | None = Field(None, max_length=64)


class AuditLogOut(ORMModel):
    id: uuid.UUID
    actor_id: uuid.UUID | None
    actor_email: EmailStr | None = None
    action: str
    target_type: str | None
    target_id: str | None
    details: dict[str, Any]
    ip_address: str | None
    created_at: datetime
