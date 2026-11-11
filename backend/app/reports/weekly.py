"""Weekly Intelligence Report: the week's briefings merged into one report, served as a PDF.

* Covers Monday..Sunday of the user's timezone. It is generated on Monday (after the user's briefing hour)
  for the week that just ended, from that user's briefings, using the global briefing on days without one.
* Nothing new is written: sections, items, summaries and executive summaries are those of the briefings
  (AI-written parts stay labelled as such). Items are de-duplicated across days and ranked by the best
  personal score they had; every item is numbered and cited with its original link.
* Downloadable from the Briefing page (GET /api/v1/briefings/weekly/{week_start}/pdf) and, when the user
  opts in (alert setting "weekly_report_email") and SMTP is configured, emailed as an attachment.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.briefing import SECTION_LABEL, SECTIONS, local_now
from app.core.logging import get_logger
from app.models import DailyBriefing, User, UserPreference, WeeklyReport
from app.reports.pdf import PdfDocument
from app.services.email import EmailSender

log = get_logger(__name__)

ITEMS_PER_SECTION = 8
VERSION = "weekly-v1"


def previous_week(local_day: date) -> tuple[date, date]:
    """(Monday, Sunday) of the week before the one containing `local_day`."""
    monday = local_day - timedelta(days=local_day.weekday())
    start = monday - timedelta(days=7)
    return start, start + timedelta(days=6)


def week_of(day: date) -> tuple[date, date]:
    start = day - timedelta(days=day.weekday())
    return start, start + timedelta(days=6)


class NoBriefingsError(Exception):
    """No briefing exists for any day of the requested week."""


class WeeklyReportBuilder:
    def __init__(self, session: AsyncSession, now: datetime | None = None) -> None:
        self.s = session
        self.now = now or datetime.now(UTC)

    async def _briefings(self, user_id: uuid.UUID, start: date, end: date) -> list[DailyBriefing]:
        rows = (
            await self.s.scalars(
                select(DailyBriefing)
                .where(
                    DailyBriefing.briefing_date.between(start, end),
                    or_(DailyBriefing.user_id == user_id, DailyBriefing.user_id.is_(None)),
                )
                .order_by(DailyBriefing.briefing_date, DailyBriefing.user_id.is_(None))
            )
        ).all()
        by_day: dict[date, DailyBriefing] = {}
        for b in rows:  # the personalised briefing wins over the global one for the same day
            by_day.setdefault(b.briefing_date, b)
        return [by_day[d] for d in sorted(by_day)]

    def merge(self, briefings: list[DailyBriefing], start: date, end: date) -> dict[str, Any]:
        sections: dict[str, list[dict[str, Any]]] = {}
        for key, _, _ in SECTIONS:
            best: dict[str, dict[str, Any]] = {}
            for b in briefings:
                for item in b.sections.get(key, []) or []:
                    aid = item.get("article_id")
                    if not aid:
                        continue
                    prev = best.get(aid)
                    score = item.get("personal_score") or item.get("importance") or 0
                    if prev is None or score > (prev.get("personal_score") or prev.get("importance") or 0):
                        best[aid] = {**item, "briefing_date": b.briefing_date.isoformat()}
            ranked = sorted(
                best.values(), key=lambda i: i.get("personal_score") or i.get("importance") or 0, reverse=True
            )
            sections[key] = ranked[:ITEMS_PER_SECTION]

        # One citation number per item, in reading order.
        citations: list[dict[str, Any]] = []
        numbers: dict[str, int] = {}
        for key, _, _ in SECTIONS:
            for item in sections[key]:
                if item["article_id"] not in numbers:
                    numbers[item["article_id"]] = len(citations) + 1
                    citations.append(
                        {"n": len(citations) + 1, "title": item["title"], "url": item["url"],
                         "source": item.get("source"), "published_at": item.get("published_at")}
                    )  # fmt: skip
                item["n"] = numbers[item["article_id"]]

        vulns = sections.get("vulnerabilities", [])
        return {
            "version": VERSION,
            "week_start": start.isoformat(),
            "week_end": end.isoformat(),
            "days_covered": [b.briefing_date.isoformat() for b in briefings],
            "daily_summaries": [
                {
                    "date": b.briefing_date.isoformat(),
                    "summary": b.executive_summary,
                    "ai_generated": bool(b.llm_provider),
                    "personalized": b.user_id is not None,
                }
                for b in briefings
                if b.executive_summary
            ],
            "sections": sections,
            "section_labels": {k: SECTION_LABEL[k] for k, _, _ in SECTIONS},
            "stats": {
                "items": len(citations),
                "critical_vulnerabilities": sum(1 for v in vulns if v.get("severity") == "critical"),
                "actively_exploited": sum(1 for v in vulns if v.get("known_exploited")),
                "incidents": len(sections.get("incidents", [])),
            },
            "citations": citations,
        }

    async def build(self, user: User, week_start: date) -> WeeklyReport:
        start, end = week_of(week_start)
        await self.s.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"weekly:{user.id}:{start}"}
        )
        briefings = await self._briefings(user.id, start, end)
        if not briefings:
            raise NoBriefingsError(f"No briefing between {start} and {end}")
        content = self.merge(briefings, start, end)
        report = await self.s.scalar(
            select(WeeklyReport).where(WeeklyReport.user_id == user.id, WeeklyReport.week_start == start)
        )
        if report is None:
            report = WeeklyReport(id=uuid.uuid4(), user_id=user.id, week_start=start, week_end=end)
            self.s.add(report)
        report.content = content
        report.briefing_ids = [str(b.id) for b in briefings]
        report.generated_at = self.now
        await self.s.flush()
        return report


def render_pdf(report: WeeklyReport) -> bytes:
    c = report.content
    start, end = date.fromisoformat(c["week_start"]), date.fromisoformat(c["week_end"])
    doc = PdfDocument(
        f"AI Pulse weekly intelligence report {start:%d %b} - {end:%d %b %Y}",
        footer=f"AI Pulse weekly report {start.isoformat()}",
    )
    muted = (0.38, 0.38, 0.44)
    link_color = (0.1, 0.3, 0.75)
    doc.text("AI Pulse", size=11, bold=True, color=(0.25, 0.25, 0.6))
    doc.text("Weekly intelligence report", size=22, bold=True)
    doc.text(f"{start:%A %d %B} - {end:%A %d %B %Y}", size=11, color=muted)
    s = c.get("stats", {})
    doc.text(
        f"{s.get('items', 0)} items from {len(c.get('days_covered', []))} briefings  |  "
        f"{s.get('critical_vulnerabilities', 0)} critical vulnerabilities  |  "
        f"{s.get('actively_exploited', 0)} actively exploited  |  {s.get('incidents', 0)} incidents",
        size=9.5,
        color=muted,
    )
    doc.rule(10)

    if c.get("daily_summaries"):
        doc.text("The week, day by day", size=14, bold=True, keep_with_next=30)
        doc.space(4)
        for d in c["daily_summaries"]:
            day = date.fromisoformat(d["date"])
            label = f"{day:%A %d %b}" + ("  (AI-generated summary)" if d["ai_generated"] else "")
            doc.text(label, size=9.5, bold=True, color=muted, keep_with_next=14)
            doc.text(d["summary"], size=10)
            doc.space(5)
        doc.rule(8)

    labels = c.get("section_labels", {})
    for key, items in c.get("sections", {}).items():
        if not items:
            continue
        doc.text(labels.get(key, key), size=14, bold=True, keep_with_next=40)
        doc.space(3)
        for item in items:
            meta = [item.get("source") or ""]
            if item.get("published_at"):
                meta.append(item["published_at"][:10])
            if item.get("cve_id"):
                meta.append(
                    item["cve_id"] + (f" CVSS {item['cvss']}" if item.get("cvss") is not None else "")
                )
            if item.get("known_exploited"):
                meta.append("actively exploited (CISA KEV)")
            if item.get("severity") and item.get("severity_basis"):
                meta.append(f"{item['severity']} ({item['severity_basis']})")
            if item.get("state"):
                meta.append(f"status: {item['state']}")
            doc.text(
                f"[{item['n']}] {item['title']}", size=10.5, bold=True, link=item["url"], keep_with_next=12
            )
            doc.text("  |  ".join(m for m in meta if m), size=8.5, color=muted, indent=12)
            if item.get("summary"):
                prefix = "AI summary: " if item.get("summary_is_ai") else ""
                doc.text(prefix + item["summary"], size=9.5, indent=12)
            if item.get("why_for_you"):
                doc.text(
                    "Why for you: " + "; ".join(item["why_for_you"][:3]), size=8.5, color=muted, indent=12
                )
            doc.space(5)
        doc.space(4)

    doc.rule(8)
    doc.text("Sources", size=14, bold=True, keep_with_next=30)
    doc.space(2)
    for cit in c.get("citations", []):
        doc.text(f"[{cit['n']}] {cit['title']}", size=8.5, keep_with_next=10)
        doc.text(cit["url"], size=8, color=link_color, indent=14, link=cit["url"])
    doc.space(8)
    doc.text(
        "Every item links to its original source. Summaries marked AI-generated were written by the "
        "configured "
        "LLM from the linked item and checked for unsupported claims; verify before relying on them.",
        size=8,
        color=muted,
    )
    return doc.render(report.generated_at)


def pdf_filename(report: WeeklyReport) -> str:
    return f"ai-pulse-weekly-{report.week_start.isoformat()}.pdf"


# ---------------------------------------------------------------------------------------- scheduling
@dataclass(frozen=True)
class DueReport:
    user_id: uuid.UUID
    week_start: date


def report_due(pref: UserPreference | None, now: datetime) -> date | None:
    """Monday of the week to report on, when it is Monday (user's timezone) after their briefing hour."""
    from app.alerts.engine import settings_for

    if not settings_for(pref).weekly_report:
        return None
    local = local_now(pref, now)
    hour = pref.briefing_hour if pref else 7
    if local.weekday() != 0 or local.hour < hour:
        return None
    return previous_week(local.date())[0]


async def due_reports(session: AsyncSession, now: datetime) -> list[DueReport]:
    rows = (
        await session.execute(
            select(User.id, UserPreference)
            .join(UserPreference, UserPreference.user_id == User.id, isouter=True)
            .where(User.is_active.is_(True))
        )
    ).all()
    out = []
    for uid, pref in rows:
        week = report_due(pref, now)
        if week is None:
            continue
        exists = await session.scalar(
            select(WeeklyReport.id).where(WeeklyReport.user_id == uid, WeeklyReport.week_start == week)
        )
        if exists is None:
            out.append(DueReport(uid, week))
    return out


async def run_weekly_report(
    session: AsyncSession, user_id: uuid.UUID, week_start: date, now: datetime, email: EmailSender | None
) -> dict[str, Any]:
    """Generate one scheduled report (idempotent), notify in-app, and email it when the user opted in."""
    from app.alerts.engine import Event, deliver, settings_for
    from app.models.enums import NotificationKind, Severity

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        return {"status": "skipped"}
    existing = await session.scalar(
        select(WeeklyReport).where(WeeklyReport.user_id == user_id, WeeklyReport.week_start == week_start)
    )
    try:
        report = existing or await WeeklyReportBuilder(session, now).build(user, week_start)
    except NoBriefingsError:
        return {"status": "no_briefings"}
    pref = await session.scalar(select(UserPreference).where(UserPreference.user_id == user_id))
    settings = settings_for(pref)
    label = f"{report.week_start:%d %b} - {report.week_end:%d %b}"
    notified = await deliver(
        session,
        user_id,
        Event(
            "weekly_report",
            NotificationKind.BRIEFING,
            Severity.INFO,
            f"Your weekly intelligence report ({label}) is ready",
            f"{report.content.get('stats', {}).get('items', 0)} items. "
            "Download the PDF from the Briefing page.",
            f"/briefing?weekly={report.week_start.isoformat()}",
            None,
            f"weekly:{report.week_start.isoformat()}",
            {},
        ),
        now,
    )
    emailed = False
    if settings.weekly_report_email and email is not None and report.emailed_at is None:
        body = (
            f"Your AI Pulse weekly intelligence report for {label} is attached as a PDF.\n\n"
            "Every item links to its original source. AI-generated summaries are labelled as such.\n"
            "You can turn these emails off in Settings > Notifications."
        )
        try:
            await email.send(
                user.email,
                f"AI Pulse weekly report - {label}",
                body,
                [(pdf_filename(report), render_pdf(report), "application/pdf")],
            )
        except Exception as exc:  # noqa: BLE001 - delivery failure must not lose the report
            log.warning("weekly_report_email_failed", user_id=str(user_id), error=type(exc).__name__)
        else:
            report.emailed_at = now
            emailed = True
    return {"status": "ok", "report_id": str(report.id), "notified": notified, "emailed": emailed}
