import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError
from app.models import AuditLog, User
from app.models.enums import RoleName
from app.repositories.admin import AdminRepository
from app.repositories.users import TokenRepository, UserRepository
from app.schemas.admin import (
    AdminUserFilters,
    AdminUserOut,
    AdminUserUpdate,
    AuditFilters,
    AuditLogOut,
    CollectionJobOut,
    JobFilters,
    RoleOut,
)
from app.schemas.common import Page


class AdminService:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session
        self.repo = AdminRepository(session)
        self.users = UserRepository(session)

    def audit(
        self, actor: User, action: str, target_type: str, target_id: str, details: dict, ip: str | None
    ) -> None:
        self.s.add(
            AuditLog(
                actor_id=actor.id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                details=details,
                ip_address=ip,
                created_at=datetime.now(UTC),
            )  # fmt: skip
        )

    async def list_users(self, f: AdminUserFilters) -> Page[AdminUserOut]:
        rows, total = await self.repo.list_users(f)
        return Page.build([AdminUserOut.model_validate(u) for u in rows], total, f.paging)

    async def get_user(self, user_id: uuid.UUID) -> User:
        user = await self.users.get(user_id)
        if user is None:
            raise NotFoundError("User not found")
        return user

    async def update_user(
        self, actor: User, user_id: uuid.UUID, body: AdminUserUpdate, ip: str | None
    ) -> AdminUserOut:
        user = await self.get_user(user_id)
        changes: dict[str, object] = {}
        demoting = body.role is not None and body.role != RoleName.ADMIN and user.role.name == RoleName.ADMIN
        deactivating = body.is_active is False and user.is_active
        if user.id == actor.id and (demoting or deactivating):
            raise PermissionDeniedError("You cannot remove your own admin role or deactivate yourself")
        if (
            (demoting or deactivating)
            and user.role.name == RoleName.ADMIN
            and await self.repo.count_active_admins() <= 1
        ):
            raise ConflictError("At least one active admin must remain")

        if body.role is not None and body.role != user.role.name:
            role = await self.users.get_role(body.role)
            changes["role"] = {"from": user.role.name.value, "to": body.role.value}
            user.role_id = role.id
        if body.is_active is not None and body.is_active != user.is_active:
            changes["is_active"] = {"from": user.is_active, "to": body.is_active}
            user.is_active = body.is_active
            if not body.is_active:  # sign the user out everywhere
                await TokenRepository(self.s).revoke_all_for_user(user.id, datetime.now(UTC))
        if changes:
            self.audit(actor, "user.update", "user", str(user.id), changes, ip)
            await self.s.flush()
            await self.s.refresh(user, ["role", "updated_at"])
        return AdminUserOut.model_validate(user)

    async def roles(self) -> list[RoleOut]:
        return [
            RoleOut(id=r.id, name=r.name, description=r.description, user_count=c)
            for r, c in await self.repo.roles_with_counts()
        ]

    async def jobs(self, f: JobFilters) -> Page[CollectionJobOut]:
        rows, total = await self.repo.list_jobs(f)
        items = []
        for j in rows:
            out = CollectionJobOut.model_validate(j)
            if j.finished_at:
                out.duration_seconds = round((j.finished_at - j.started_at).total_seconds(), 3)
            items.append(out)
        return Page.build(items, total, f.paging)

    async def audit_logs(self, f: AuditFilters) -> Page[AuditLogOut]:
        rows, total = await self.repo.list_audit(f)
        emails = await self.repo.emails({r.actor_id for r in rows if r.actor_id})
        items = []
        for r in rows:
            out = AuditLogOut.model_validate(r)
            out.actor_email = emails.get(r.actor_id) if r.actor_id else None
            items.append(out)
        return Page.build(items, total, f.paging)
