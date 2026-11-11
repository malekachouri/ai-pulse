# Daily briefings & notifications

## Personalised briefing

`app/ai/briefing.py` builds one briefing per user and per **local** date, using the user's timezone. A general edition (`user_id` NULL) is produced every day after 06:00 UTC.

Each briefing contains these sections, in order:

| # | Section | Content |
|---|---|---|
| 1 | Executive summary | Written by the LLM when one is configured, using only the selected items. Unsupported claims are removed. Without an LLM a deterministic summary is used. |
| 2 | `top_ai` | Most important AI news |
| 3 | `model_releases` | New model releases |
| 4 | `new_tools` | New tools and frameworks |
| 5 | `research` | Research papers |
| 6 | `bugs` | Important bugs: only items with a documented severity or an importance of at least 50 |
| 7 | `vulnerabilities` | Critical or high CVEs, or CVEs in CISA KEV. Each item carries its CVE id, CVSS, KEV status and the basis for its severity. |
| 8 | `incidents` | Cloud and infrastructure incidents that started or were resolved in the period, plus every unresolved one. Each has a state (current, historical or unverified) and its last verification time. |
| – | `devops` | DevOps and cloud updates |
| 9 | `changes` | What changed since the previous briefing (see below) |
| 10 | `learning` | Curated resources and AI-suggested topics. AI suggestions are labelled. |

The ranking combines the importance score with a personal boost based on the user's interests and on the technologies, repositories and providers they follow. `meta` records the interests, frequency, timezone and the date of the previous briefing.

The `changes` section is computed, never generated. It lists:

- new items per section;
- incidents that were active in the previous briefing and are now resolved;
- CVEs from the previous briefing that have since been added to CISA KEV;
- items that mention something the user follows.

**Period.** A briefing covers the time since the end of the previous one, capped at 7 days. When there is no previous briefing, it covers 24 hours, or 7 days for weekly users.

Items count as new if they were published in the period. Items collected late are included only if they were published in the last 7 days, so an old item backfilled today never appears as "new".

## Scheduling

| Piece | Behaviour |
|---|---|
| `aipulse.generate_due_briefings` (Beat, every `BRIEFING_DISPATCH_SECONDS`) | Calls `due_briefings()` and enqueues one `generate_briefing(user_id, local_date)` per result. |
| `is_due(pref, now)` | Due once the local time reaches `briefing_hour`, subject to the frequency: `daily`, `weekdays` (Monday–Friday), `weekly` (on `briefing_weekday`, 0 = Monday) or `off`. A missed hour is caught up later the same local day. An invalid timezone falls back to UTC. |
| `aipulse.generate_briefing` | Automatic retries with exponential backoff and jitter (`BRIEFING_MAX_RETRIES`). Uses acks-late, so a task lost by a crashed worker is redelivered. |
| Idempotency | A transaction-level advisory lock on (user, date) serialises concurrent runs. Scheduled runs keep a briefing that already exists. `UNIQUE (user_id, briefing_date)` applies. |
| On-demand generation | `POST /briefings/generate` (re)builds today's briefing for the user's local date. A briefing generated in the last 10 minutes is returned as is. |

## Notifications

Notifications are delivered in the app. Each one has a kind, a severity, a title, a body and a link: the official source, or an in-app link for briefings.

`UNIQUE (user_id, dedup_key)` guarantees each event is notified at most once. A deleted notification is kept as a hidden row (`dismissed_at`), so the same event is never delivered again.

| Kind | Rule (`alert_settings`) | Dedup key |
|---|---|---|
| `critical_alert` | `exploited`: a CVE added to CISA KEV in the last 2 days | `cve:<id>:kev` |
| `vulnerability` | `critical_cves` (CVSS ≥ `min_cvss`, default 9.5; `null` = any critical), or `watched_tech` (at or above `min_notification_severity`) | `cve:<id>:new` |
| `bug` | `critical_bugs`: critical with a documented basis, limited to `bug_projects` or the followed repositories | `bug:<id>` |
| `incident` | `outages`: currently active, impact at or above `outage_min_impact`, optionally limited to `outage_providers` | `incident:<id>` |
| `model_release` | `model_releases`: released in the last 7 days. Limited to `model_providers`; when that list is empty, to the followed providers; when both are empty, any tracked provider. | `model:<release id>` |
| `briefing` | `briefing_ready`: a scheduled briefing was generated | `briefing:<date>` |
| `watchlist` | `watchlist`: a new release (model, tool or GitHub release collected in the last 48 h) of something the user follows: a whole-word mention of a followed technology or provider, or a release of a followed repository. Skipped when another rule already announced the same item. | `watch:<article id>` |
| `briefing` | `weekly_report`: the Monday weekly report (PDF) is ready; `weekly_report_email` also emails it as an attachment (SMTP needed, off by default) | `weekly:<week start>` |

## Weekly intelligence report (PDF)

`app/reports/weekly.py`, Celery `aipulse.generate_due_weekly_reports` (hourly).

- **When.** On Monday in the user's timezone, after their `briefing_hour`, for the week that just ended
  (Monday to Sunday).
- **What.** That week's briefings for the user, using the general one on days without a personal briefing.
  The sections are merged and de-duplicated, ranked by the best personal score each item had, and
  numbered with citations and links. The daily executive summaries come with them: AI-written ones stay
  labelled, and nothing new is generated.
- **Stored** in `weekly_reports`, one row per user and week. The PDF is rendered on download by a small
  built-in writer (`app/reports/pdf.py`, standard fonts, clickable links). Non-Latin characters show as
  "?", but every item links to its original source.
- **Where.**
  - On the Briefing page: *Weekly reports*, with *Download PDF* and *Build last week's report*.
  - From the API: `GET /briefings/weekly`, `POST /briefings/weekly/generate[?week_start=]` and
    `GET /briefings/weekly/{week_start}/pdf`.
  - By email, as an attachment, when `weekly_report_email` is on and SMTP is configured. A retried task
    never emails twice (`emailed_at`).

## API

| Endpoint | Purpose |
|---|---|
| `GET /notifications` | List notifications. Filters: `kind[]`, `severity[]`, `unread_only`; paginated. |
| `GET /notifications/unread-count` | Returns `{unread, by_kind}` |
| `POST /notifications/{id}/read` | Mark one notification as read |
| `POST /notifications/{id}/unread` | Mark one notification as unread |
| `DELETE /notifications/{id}` | Delete one notification |
| `POST /notifications/read-all?kind=` | Mark everything as read, optionally only for some kinds |
| `GET /preferences` and `PUT /preferences` | Interests, followed technologies, repositories and providers, severity threshold, `briefing_frequency`, `briefing_hour`, `briefing_weekday`, `timezone`, `alert_settings` |
| `POST /preferences/follow` and `POST /preferences/unfollow` | Body `{type: technology\|repository\|provider, value}`. Idempotent, case-insensitive, and the row is locked during the update. |
| `GET /briefings`, `/briefings/latest`, `/briefings/{date}` | Read briefings |
| `POST /briefings/generate` | Generate today's briefing now |

## UI

| Page | What it offers |
|---|---|
| `/notifications` | Tabs (all, critical, model releases, bugs & vulnerabilities, incidents, briefings) with unread counts. Unread-only filter. Mark read or unread, delete, mark the current tab as read. |
| `/briefing` | All sections, incident state and CVE badges, AI labels, and a briefing history you can navigate (`?date=`). |
| `/settings` | Briefing schedule, with a plain-language summary. In-app notification rules, thresholds and provider filters. |
| Follow buttons | GitHub repositories, model providers and trending technologies. |
