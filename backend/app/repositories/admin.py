import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, CollectionJob, Role, Source, User
from app.models.enums import RoleName
from app.repositories.base import SortSpec, contains_pattern, paginate
from app.schemas.admin import AdminUserFilters, AuditFilters, JobFilters

USER_SORT = SortSpec(
    {"created_at": User.created_at, "email": User.email, "last_login_at": User.last_login_at},
    default="-created_at", tiebreaker=User.id,
)  # fmt: skip
JOB_SORT = SortSpec(
    {"started_at": CollectionJob.started_at, "finished_at": CollectionJob.finished_at},
    default="-started_at", tiebreaker=CollectionJob.id,
)  # fmt: skip
AUDIT_SORT = SortSpec({"created_at": AuditLog.created_at}, default="-created_at", tiebreaker=AuditLog.id)


class AdminRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def list_users(self, f: AdminUserFilters) -> tuple[Sequence[User], int]:
        stmt = select(User).join(Role)
        if f.q:
            p = contains_pattern(f.q)
            stmt = stmt.where(User.email.ilike(p, escape="\\") | User.full_name.ilike(p, escape="\\"))
        if f.role:
            stmt = stmt.where(Role.name == f.role)
        if f.is_active is not None:
            stmt = stmt.where(User.is_active.is_(f.is_active))
        return await paginate(self.s, stmt, USER_SORT.order_by(f.sort), f.paging.offset, f.page_size)

    async def count_active_admins(self) -> int:
        return int(
            await self.s.scalar(
                select(func.count(User.id))
                .join(Role)
                .where(Role.name == RoleName.ADMIN, User.is_active.is_(True))
            )
            or 0
        )

    async def roles_with_counts(self) -> list[tuple[Role, int]]:
        rows = await self.s.execute(
            select(Role, func.count(User.id))
            .outerjoin(User, User.role_id == Role.id)
            .group_by(Role.id)
            .order_by(Role.id)
        )
        return [(r, int(c)) for r, c in rows.tuples().all()]

    async def list_jobs(self, f: JobFilters) -> tuple[Sequence[CollectionJob], int]:
        stmt = select(CollectionJob)
        if f.source:
            stmt = stmt.where(CollectionJob.source_id.in_(select(Source.id).where(Source.slug.in_(f.source))))
        if f.status:
            stmt = stmt.where(CollectionJob.status.in_(f.status))
        if f.date_from:
            stmt = stmt.where(CollectionJob.started_at >= f.date_from)
        if f.date_to:
            stmt = stmt.where(CollectionJob.started_at <= f.date_to)
        return await paginate(self.s, stmt, JOB_SORT.order_by(f.sort), f.paging.offset, f.page_size)

    async def list_audit(self, f: AuditFilters) -> tuple[Sequence[Any], int]:
        stmt = select(AuditLog)
        if f.action:
            stmt = stmt.where(AuditLog.action == f.action)
        if f.actor_id:
            stmt = stmt.where(AuditLog.actor_id == f.actor_id)
        if f.target_type:
            stmt = stmt.where(AuditLog.target_type == f.target_type)
        if f.date_from:
            stmt = stmt.where(AuditLog.created_at >= f.date_from)
        if f.date_to:
            stmt = stmt.where(AuditLog.created_at <= f.date_to)
        return await paginate(self.s, stmt, AUDIT_SORT.order_by(f.sort), f.paging.offset, f.page_size)

    async def emails(self, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not ids:
            return {}
        return dict(
            (await self.s.execute(select(User.id, User.email).where(User.id.in_(ids)))).tuples().all()
        )
