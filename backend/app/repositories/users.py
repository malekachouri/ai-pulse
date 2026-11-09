import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PasswordResetToken, RefreshToken, Role, User
from app.models.enums import RoleName


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def get(self, user_id: uuid.UUID) -> User | None:
        return await self.s.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        return await self.s.scalar(select(User).where(func.lower(User.email) == email.lower()))

    async def get_role(self, name: RoleName) -> Role:
        role = await self.s.scalar(select(Role).where(Role.name == name))
        if role is None:  # roles are seeded by migration 0001
            raise RuntimeError(f"Role {name} missing - run database migrations")
        return role

    async def add(self, user: User) -> User:
        self.s.add(user)
        await self.s.flush()
        await self.s.refresh(user, ["role"])
        return user


class TokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def add_refresh(self, token: RefreshToken) -> RefreshToken:
        self.s.add(token)
        await self.s.flush()
        return token

    async def get_refresh_by_hash(self, token_hash: str, *, for_update: bool = False) -> RefreshToken | None:
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        if for_update:
            stmt = stmt.with_for_update()
        return await self.s.scalar(stmt)

    async def revoke_family(self, family_id: uuid.UUID, now: datetime) -> None:
        await self.s.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )

    async def revoke_all_for_user(self, user_id: uuid.UUID, now: datetime) -> None:
        await self.s.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )

    async def add_reset(self, token: PasswordResetToken) -> None:
        self.s.add(token)
        await self.s.flush()

    async def get_reset_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        return await self.s.scalar(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash).with_for_update()
        )

    async def invalidate_resets_for_user(self, user_id: uuid.UUID, now: datetime) -> None:
        await self.s.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.user_id == user_id, PasswordResetToken.used_at.is_(None))
            .values(used_at=now)
        )
