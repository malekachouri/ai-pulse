"""Helpers for turning source markup into plain text and parsing source dates - without guessing."""

import html
import re
from calendar import timegm
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from time import struct_time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in ("p", "br", "li", "div", "h1", "h2", "h3", "h4", "tr"):
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def html_to_text(value: str | None) -> str | None:
    if not value:
        return None
    if "<" not in value:
        text = html.unescape(value)
    else:
        p = _Text()
        p.feed(value)
        text = "".join(p.parts)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    return text or None


def truncate(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def parse_dt(value: str | None) -> datetime | None:
    """ISO-8601 → aware datetime (UTC assumed only when the source gives no offset)."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def parse_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def struct_to_dt(value: struct_time | None) -> datetime | None:
    return datetime.fromtimestamp(timegm(value), tz=UTC) if value else None


_TRACKING = re.compile(r"^(utm_|fbclid$|gclid$|mc_cid$|mc_eid$|ref$)")


def canonical_url(url: str) -> str:
    """Normalise a URL for duplicate detection only (the original URL is always what we store)."""
    parts = urlsplit(url.strip())
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if not _TRACKING.match(k)])
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))
