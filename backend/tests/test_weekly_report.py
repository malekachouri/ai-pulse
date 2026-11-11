"""Weekly Intelligence Report: merged from the week's briefings, valid PDF, Monday schedule, opt-in email."""

import re
import uuid
import zlib
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.models import DailyBriefing, Notification, User, UserPreference, WeeklyReport
from app.reports.pdf import PdfDocument, text_width, wrap
from app.reports.weekly import due_reports, previous_week, render_pdf, report_due, run_weekly_report
from tests import feature_data as fd
from tests.conftest import CapturingEmail, register_and_login

PARIS = ZoneInfo("Europe/Paris")
MONDAY = datetime(2026, 11, 9, 8, 30, tzinfo=PARIS).astimezone(UTC)  # Monday 08:30 in Paris
WEEK = date(2026, 11, 2)


def _item(key: str, title: str, score: float, **kw):  # type: ignore[no-untyped-def]
    return {"article_id": str(uuid.uuid5(uuid.NAMESPACE_URL, key)), "title": title,
            "url": f"https://src.test/{key}", "source": "Test source", "item_type": "news",
            "published_at": "2026-11-03T09:00:00+00:00", "importance": score, "personal_score": score,
            "why_for_you": ["Follows Kubernetes"], "summary": f"Summary of {title}.", "summary_is_ai": True,
            **kw}  # fmt: skip


async def _briefings(s, user_id):  # type: ignore[no-untyped-def]
    def b(day: date, uid, sections, summary, llm=True):  # type: ignore[no-untyped-def]
        start = datetime.combine(day, datetime.min.time(), UTC)
        return DailyBriefing(id=uuid.uuid4(), user_id=uid, briefing_date=day, period_start=start,
                             period_end=start + timedelta(days=1), generated_at=start + timedelta(hours=7),
                             executive_summary=summary, sections=sections, cited_article_ids=[],
                             llm_provider="fake" if llm else None, llm_model="m" if llm else None)  # fmt: skip

    k8s = _item("k8s", "Kubernetes 1.35 released", 60)
    s.add_all([
        b(date(2026, 11, 2), user_id, {"top_ai": [k8s, _item("rag", "A RAG toolkit", 40)]}, "Monday summary."),
        b(date(2026, 11, 3), user_id, {"top_ai": [{**k8s, "personal_score": 75}],
                                       "vulnerabilities": [_item("cve", "CVE-2026-1 in X", 90, severity="critical",
                                                                 cve_id="CVE-2026-1", cvss=9.8,
                                                                 known_exploited=True)]}, "Tuesday summary."),
        b(date(2026, 11, 4), None, {"incidents": [_item("aws", "AWS us-east-1 incident", 70, state="resolved")]},
          "Global Wednesday summary.", llm=False),
        b(date(2026, 11, 4), user_id, {"devops": [_item("tf", "Terraform 2 beta", 30)]}, "Personal Wednesday."),
        b(date(2026, 11, 5), None, {"devops": [_item("helm", "Helm 4", 35)]}, "Global Thursday."),
        b(date(2026, 11, 9), user_id, {"top_ai": [_item("next", "Next week item", 99)]}, "Not in this report."),
    ])  # fmt: skip
    await s.flush()


def _pdf_text(pdf: bytes) -> str:
    """Decompress content streams and check the xref table points at each object."""
    assert pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%%EOF")
    start = int(re.search(rb"startxref\n(\d+)", pdf).group(1))  # type: ignore[union-attr]
    assert pdf[start : start + 4] == b"xref"
    offsets = [int(x) for x in re.findall(rb"(\d{10}) 00000 n", pdf)]
    for n, off in enumerate(offsets, start=1):
        assert pdf[off:].startswith(b"%d 0 obj" % n)
    texts = []
    for m in re.finditer(rb"stream\n(.*?)\nendstream", pdf, re.S):
        texts += re.findall(rb"\((.*?)\) Tj", zlib.decompress(m.group(1)))
    raw = "\n".join(t.decode("cp1252") for t in texts)
    return re.sub(r"\\(.)", r"\1", raw)  # PDF string escapes


async def test_weekly_report_merges_the_week_and_renders_a_pdf(session_factory):
    async with session_factory() as s:
        u = await fd.user(s, "weekly@example.com", timezone="Europe/Paris",
                          alert_settings={"weekly_report_email": True})  # fmt: skip
        await _briefings(s, u.id)
        await s.commit()

        assert report_due(await s.scalar(select(UserPreference).where(UserPreference.user_id == u.id)),
                          MONDAY) == WEEK  # fmt: skip
        due = await due_reports(s, MONDAY)
        assert [(d.user_id, d.week_start) for d in due if d.user_id == u.id] == [(u.id, WEEK)]

        mail = CapturingEmail()
        out = await run_weekly_report(s, u.id, WEEK, MONDAY, mail)
        await s.commit()
        assert out["status"] == "ok" and out["emailed"] and out["notified"]
        report = await s.scalar(select(WeeklyReport).where(WeeklyReport.user_id == u.id))
        again = await run_weekly_report(s, u.id, WEEK, MONDAY, mail)  # retried task: no second email
        assert again["emailed"] is False and len(mail.sent) == 1
        assert await due_reports(s, MONDAY + timedelta(hours=1)) == []
        notes = (await s.scalars(select(Notification).where(Notification.user_id == u.id))).all()

    c = report.content
    assert c["week_start"] == "2026-11-02" and c["week_end"] == "2026-11-08"
    # Personal briefing wins on Wednesday; the global one fills Thursday; next Monday is out.
    assert c["days_covered"] == ["2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05"]
    assert [d["summary"] for d in c["daily_summaries"]][2:] == ["Personal Wednesday.", "Global Thursday."]
    top = c["sections"]["top_ai"]
    assert [i["title"] for i in top] == ["Kubernetes 1.35 released", "A RAG toolkit"]  # de-duplicated
    assert top[0]["personal_score"] == 75 and top[0]["briefing_date"] == "2026-11-03"
    assert c["stats"] == {"items": 5, "critical_vulnerabilities": 1, "actively_exploited": 1, "incidents": 0}
    assert [x["n"] for x in c["citations"]] == [1, 2, 3, 4, 5]
    assert {x["url"] for x in c["citations"]} >= {"https://src.test/k8s", "https://src.test/cve"}

    to, subject, body = mail.sent[0]
    assert to == "weekly@example.com" and "02 Nov - 08 Nov" in subject
    ((name, pdf, mime),) = mail.attachments[0]
    assert name == "ai-pulse-weekly-2026-11-02.pdf" and mime == "application/pdf"
    text = _pdf_text(pdf)
    assert "Weekly intelligence report" in text and "[1] Kubernetes 1.35 released" in text
    assert "AI-generated summary" in text and "actively exploited (CISA KEV)" in text
    assert b"/URI (https://src.test/k8s)" in pdf  # titles and sources are clickable links
    assert [n.link for n in notes] == ["/briefing?weekly=2026-11-02"]


async def test_schedule_respects_monday_hour_and_opt_out(session_factory):
    async with session_factory() as s:
        u = await fd.user(s, "w2@example.com", timezone="Europe/Paris", briefing_hour=9)
        off = await fd.user(s, "w3@example.com", alert_settings={"weekly_report": False})
        await s.commit()
        pref = await s.scalar(select(UserPreference).where(UserPreference.user_id == u.id))
        assert report_due(pref, MONDAY) is None  # 08:30 < 09:00 local
        assert report_due(pref, MONDAY + timedelta(hours=1)) == WEEK
        assert report_due(pref, MONDAY + timedelta(days=1)) is None  # Tuesday
        due = await due_reports(s, MONDAY + timedelta(hours=1))
        assert off.id not in {d.user_id for d in due}
        # No briefing at all: nothing to send.
        assert (await run_weekly_report(s, u.id, WEEK, MONDAY, None))["status"] == "no_briefings"
    assert previous_week(date(2026, 11, 15)) == (date(2026, 11, 2), date(2026, 11, 8))  # a Sunday


async def test_weekly_api_generate_list_and_download(client, session_factory):
    token = await register_and_login(client, "weekly-api@example.com")
    h = {"Authorization": f"Bearer {token}"}
    async with session_factory() as s:
        uid = await s.scalar(select(User.id).where(User.email == "weekly-api@example.com"))
        await _briefings(s, uid)
        await s.commit()

    assert (await client.post("/api/v1/briefings/weekly/generate", headers=h,
                              params={"week_start": "2026-10-19"})).status_code == 404  # fmt: skip
    r = await client.post("/api/v1/briefings/weekly/generate", headers=h, params={"week_start": "2026-11-04"})
    assert r.status_code == 200, r.text
    item = r.json()
    assert item["week_start"] == "2026-11-02" and item["items"] == 5 and item["days_covered"] == 4
    assert item["pdf_url"] == "/api/v1/briefings/weekly/2026-11-02/pdf"

    listed = (await client.get("/api/v1/briefings/weekly", headers=h)).json()
    assert [x["week_start"] for x in listed] == ["2026-11-02"]
    pdf = await client.get(item["pdf_url"], headers=h)
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert 'filename="ai-pulse-weekly-2026-11-02.pdf"' in pdf.headers["content-disposition"]
    assert "Kubernetes 1.35 released" in _pdf_text(pdf.content)

    other = {"Authorization": f"Bearer {await register_and_login(client, 'other-weekly@example.com')}"}
    assert (await client.get(item["pdf_url"], headers=other)).status_code == 404  # not someone else's report
    assert (await client.get(item["pdf_url"])).status_code == 401
    assert (await client.get("/api/v1/briefings/2026-11-02")).status_code in (200, 404)  # date route intact


def test_pdf_writer_wraps_paginates_and_escapes():
    long = "word " * 3000
    doc = PdfDocument("T (test)")
    doc.text("Parens (and) back\\slash", bold=True, link="https://example.com/a")
    doc.text(long)
    doc.text("x" * 400)  # one token wider than the page is hard-broken
    pdf = doc.render()
    text = _pdf_text(pdf)
    assert len(doc.pages) >= 3 and "page 1 of" in text and b"/URI (https://example.com/a)" in pdf
    assert "Parens (and) back\\slash" in text
    assert all(text_width(line, 10) <= doc.width + 0.01 for line in wrap(long + "x" * 400, 10, doc.width))
    assert render_pdf  # imported for the API path
