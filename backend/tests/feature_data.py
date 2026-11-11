"""Small builders for feature tests that need collected items without running a connector."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from app.models import Article, Category, Role, Source, User, UserPreference
from app.models.enums import ItemType, SourceType, VerificationStatus

NOW = datetime.now(UTC).replace(microsecond=0)


async def source(s, slug: str, connector: str = "rss", name: str | None = None) -> Source:  # type: ignore[no-untyped-def]
    src = Source(slug=slug, name=name or slug, source_type=SourceType.API, connector=connector,
                 url=f"https://{slug}.test/", default_item_type=ItemType.NEWS, is_official=True,
                 reliability=0.9)  # fmt: skip
    s.add(src)
    await s.flush()
    return src


async def article(s, src: Source, key: str, *, item_type: ItemType = ItemType.NEWS, title: str,  # type: ignore[no-untyped-def]
                  description: str | None = None, content: str | None = None, url: str | None = None,
                  hours_ago: float = 2, categories: tuple[str, ...] = (), **kw: Any) -> Article:  # fmt: skip
    cats = {c.slug: c for c in await s.scalars(select(Category))} if categories else {}
    a = Article(source_id=src.id, external_id=key, item_type=item_type, title=title, description=description,
                content=content, url=url or f"https://{src.slug}.test/{key}",
                published_at=NOW - timedelta(hours=hours_ago), collected_at=NOW - timedelta(hours=hours_ago),
                content_hash=uuid.uuid4().hex.ljust(64, "0"), verification_status=VerificationStatus.OFFICIAL,
                categories=[cats[c] for c in categories], **kw)  # fmt: skip
    s.add(a)
    await s.flush()
    return a


async def user(s, email: str, **prefs: Any) -> User:  # type: ignore[no-untyped-def]
    u = User(email=email, password_hash="x", role=await s.scalar(select(Role).where(Role.name == "user")))
    s.add(u)
    await s.flush()
    s.add(UserPreference(user_id=u.id, **prefs))
    await s.flush()
    return u
