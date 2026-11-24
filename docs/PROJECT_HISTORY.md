# Project history and traceability

Every step that built AI Pulse, why it was done, the concepts it applied and where to find it. Use it to
trace any feature, fix or decision back to the pull request (PR) that introduced it, and to explain the
project in an interview.

**Sources of truth.** The git history of `main` (116 commits, 9–18 November 2026) and the merged pull
requests on GitHub. Every PR below links to its description, which lists what was changed and how it was
tested. The build prompts of each phase are in [docs/prompts/](prompts/README.md); the audit evidence is in
[AUDIT_REPORT.md](AUDIT_REPORT.md).

PR numbers missing from the timeline (#11, #14, #15, #18, #24, #41, #42, #43) are Dependabot updates that
were closed or replaced by another PR (for example #20 replaced #18, #25 replaced #24).

Contents:
1. [Timeline](#1-timeline)
2. [Steps in detail](#2-steps-in-detail)
3. [Incidents: problem, root cause, fix](#3-incidents-problem-root-cause-fix)
4. [Concept index](#4-concept-index)
5. [Decisions and their reasons](#5-decisions-and-their-reasons)
6. [Work outside this repository](#6-work-outside-this-repository)
7. [Open items](#7-open-items)

---

## 1. Timeline

| Date | PR | What was delivered | Main concepts |
|---|---|---|---|
| 2026-11-09 | (first commit) | Phase 1: architecture, database schema, authentication, core API | layered FastAPI, SQLAlchemy async, Alembic, Argon2id, JWT + rotating refresh cookie, RBAC |
| 2026-11-09 | [#1](https://github.com/malekachouri/ai-pulse/pull/1) | Phase 2: Next.js web interface | App Router, TanStack Query, URL-synced filters, demo mode |
| 2026-11-09 | [#2](https://github.com/malekachouri/ai-pulse/pull/2) | Phases 3 and 4: typed REST API, ingestion engine | typed API modules, connectors, Celery + Beat, checkpoints, retries, rate limits, dedup |
| 2026-11-09 | [#3](https://github.com/malekachouri/ai-pulse/pull/3) | Phases 5 and 6: AI engine, Bugs & Failures Radar | LLM providers, grounding, explainable scoring, hybrid search (pgvector), RAG, alerts |
| 2026-11-09 | [#4](https://github.com/malekachouri/ai-pulse/pull/4) | Phase 7: personalised briefings and notifications | per-user scheduling, notification center |
| 2026-11-10 | [#5](https://github.com/malekachouri/ai-pulse/pull/5) | Phase 8: production readiness | hardened images, CI/CD, Trivy, CodeQL, SHA-pinned actions, signed provenance, Prometheus/Grafana, backups |
| 2026-11-10 | #6–#10, #12, #13, [#16](https://github.com/malekachouri/ai-pulse/pull/16), [#19](https://github.com/malekachouri/ai-pulse/pull/19) | Dependabot updates (Caddy, Prometheus, Alertmanager, Grafana, Redis, exporters, actions, npm) | supply-chain maintenance |
| 2026-11-10 | [#17](https://github.com/malekachouri/ai-pulse/pull/17) | Node 26 LTS everywhere, ESLint 10 | toolchain alignment |
| 2026-11-10 | [#20](https://github.com/malekachouri/ai-pulse/pull/20) | Backend on Python 3.15 | runtime upgrade with full test run |
| 2026-11-11 | [#21](https://github.com/malekachouri/ai-pulse/pull/21) | Phase 9: full audit, 22 bugs fixed, final report | live verification, SSRF fix, WCAG 2.1 AA |
| 2026-11-11 | [#22](https://github.com/malekachouri/ai-pulse/pull/22) | Browser e2e tests in CI, CVSS 9.5 alert default, build prompts, branch protection guide | Playwright, axe-core, branch protection |
| 2026-11-11 | [#23](https://github.com/malekachouri/ai-pulse/pull/23) | Dependabot: postgres-exporter | supply chain |
| 2026-11-11 | [#25](https://github.com/malekachouri/ai-pulse/pull/25) | Playwright 1.65 + axe-core 4.14, label-in-name fixes | accessibility (WCAG 2.5.3) |
| 2026-11-11 | [#26](https://github.com/malekachouri/ai-pulse/pull/26) | Fix polynomial ReDoS in the tokenizer (CodeQL alert) | ReDoS, linear-time regex |
| 2026-11-11 | [#27](https://github.com/malekachouri/ai-pulse/pull/27) | Learn: recommendations, Learning Assistant, release change detection | explainable recommendations, extraction without AI |
| 2026-11-11 | [#28](https://github.com/malekachouri/ai-pulse/pull/28) | Watchlist, Bug Intelligence, model comparison, weekly PDF report, encrypted offsite backups | cited facts, grounding, GPG + S3 SigV4, restore drill |
| 2026-11-11 | [#29](https://github.com/malekachouri/ai-pulse/pull/29) | One AI analysis run at a time | PostgreSQL advisory lock (deadlock fix) |
| 2026-11-12 | [#30](https://github.com/malekachouri/ai-pulse/pull/30) | AI requests no longer cut after 30 s by the web proxy | proxy timeouts |
| 2026-11-12 | [#31](https://github.com/malekachouri/ai-pulse/pull/31) | Bug Intelligence quotes versions and fixes stated in official records | stated facts extraction |
| 2026-11-15 | [#32](https://github.com/malekachouri/ai-pulse/pull/32) | Fix random sign-outs; consistent stated fixes | refresh-token grace period, Web Locks API |
| 2026-11-15 | [#33](https://github.com/malekachouri/ai-pulse/pull/33) | Slow local models no longer lose the database connection | `SET LOCAL idle_in_transaction_session_timeout` |
| 2026-11-15 | [#34](https://github.com/malekachouri/ai-pulse/pull/34) | Re-analysing chosen items analyses those items | scoped pipeline runs |
| 2026-11-15 | [#35](https://github.com/malekachouri/ai-pulse/pull/35) | Roadmap of suggestions for later | backlog in [ROADMAP.md](ROADMAP.md) |
| 2026-11-15 | [#36](https://github.com/malekachouri/ai-pulse/pull/36) | Docker-only checks, update script, Claude Code skills | developer experience, `CLAUDE.md`, `/check` `/update` `/reanalyse` |
| 2026-11-15 | [#37](https://github.com/malekachouri/ai-pulse/pull/37) | Smoke test reads the web port; fast Beat health check; TLS 1.2+ | health checks under load, explicit TLS minimum |
| 2026-11-15 | [#38](https://github.com/malekachouri/ai-pulse/pull/38) | Smoke test asks Docker which port is published | robust local tooling |
| 2026-11-16 | [#39](https://github.com/malekachouri/ai-pulse/pull/39) | Skills Radar (MCP servers, Claude Code plugins, Agent Skills) | resumable cursor pagination, baseline vs new, facts-only install commands |
| 2026-11-16 | [#40](https://github.com/malekachouri/ai-pulse/pull/40) | Dependabot: Grafana 13.3.1 | supply chain |
| 2026-11-16 | [#44](https://github.com/malekachouri/ai-pulse/pull/44) | "What is it good for?" AI explanation; sign-out on network errors fixed | grounded explanations, keep-alive race, refresh retries |
| 2026-11-16 | [#45](https://github.com/malekachouri/ai-pulse/pull/45) | Proprietary license | intellectual property |
| 2026-11-16 | [#46](https://github.com/malekachouri/ai-pulse/pull/46) | Small embedding batches for local models; daily cleanup; e2e lock fix | batching with partial progress, data retention |
| 2026-11-18 | [#47](https://github.com/malekachouri/ai-pulse/pull/47) | Explanations from small models; expiring npm audit allowlist | schema-constrained output, citation matching, risk acceptance with expiry |

---

## 2. Steps in detail

Each step: **goal**, **what was done**, **concepts applied**, **how it was verified**, **where to look**.

### Phase 1: Foundation (first commit, 2026-11-09)
- **Goal:** a secure, layered base every later module builds on.
- **Done:** architecture, full database schema and first migration, user accounts, core API, Docker.
- **Concepts:** layered architecture (API → services → repositories → models); async SQLAlchemy;
  Alembic migrations with working downgrades; Argon2id password hashing; short-lived JWT access token in
  memory and a rotating `HttpOnly` refresh cookie with reuse detection; role-based access control
  (`admin`, `analyst`, `user`).
- **Verified:** backend tests against a real PostgreSQL.
- **Where:** [ARCHITECTURE.md](ARCHITECTURE.md), [DATABASE.md](DATABASE.md), [SECURITY.md](../SECURITY.md),
  `backend/app/services/auth.py`.

### Phase 2: Web interface ([#1](https://github.com/malekachouri/ai-pulse/pull/1))
- **Goal:** a usable product, not only an API.
- **Done:** Next.js app shell, 13 pages, dashboard, article cards, filters synced with the URL, bookmarks,
  notifications, preferences, and a demo mode with clearly fictional `[DEMO]` data.
- **Concepts:** App Router, TanStack Query caching, URL as state, dark/light themes, keyboard access.
- **Where:** `frontend/src/app`, `frontend/src/lib/demo.ts`.

### Phase 3: REST API ([#2](https://github.com/malekachouri/ai-pulse/pull/2))
- **Goal:** typed endpoints for each intelligence module.
- **Done:** models, tools, research, GitHub, bugs, security, incidents; keyword search; admin endpoints for
  users, roles, jobs and the audit log.
- **Concepts:** Pydantic schemas on every input, whitelisted sorting, unknown query parameters rejected,
  one error envelope, pagination.
- **Where:** [API.md](API.md), `backend/app/api/v1`.

### Phase 4: Ingestion engine ([#2](https://github.com/malekachouri/ai-pulse/pull/2))
- **Goal:** collect from official sources only, automatically and reliably.
- **Done:** 14 connectors, 27 official sources at the time (NVD, CISA KEV, GitHub, arXiv, Hugging Face,
  vendor blogs, status pages), Celery workers and Beat scheduling.
- **Concepts:** checkpoints and conditional requests (ETag), retries with exponential backoff and jitter,
  per-host rate limits, honouring `Retry-After` and GitHub quota resets, cross-source deduplication by
  canonical key, per-source health, recorded real responses as test fixtures.
- **Where:** [INGESTION.md](INGESTION.md), `backend/app/ingestion`.

### Phase 5: AI engine ([#3](https://github.com/malekachouri/ai-pulse/pull/3))
- **Goal:** useful AI analysis that stays faithful to the sources.
- **Done:** OpenAI, Anthropic and Ollama providers; a 10-step analysis pipeline; explainable importance
  score (not CVSS); keyword, semantic and hybrid search; "Ask AI Pulse" (RAG) with citations.
- **Concepts:** structured JSON output validated against a schema; **grounding**: sentences containing
  numbers, versions, CVE/CWE ids, percentages or dates that the sources lack are removed
  (`app/ai/claims.py`); RAG with a sufficiency gate before calling the model and citations checked against
  the provided sources; pgvector HNSW index; token budget and cost tracking.
- **Where:** [AI.md](AI.md), `backend/app/ai`.

### Phase 6: Bugs & Failures Radar ([#3](https://github.com/malekachouri/ai-pulse/pull/3))
- **Goal:** bugs, incidents and vulnerabilities with trustworthy states.
- **Done:** bugs with fix tracking, incident states, GitHub Security Advisories connector, configurable alerts.
- **Concepts:** severity only with a documented basis; an incident is "active" only when the provider's own
  status page was re-verified in the last 2 hours; remediation only from official sources, never generated.
- **Where:** [RADAR.md](RADAR.md).

### Phase 7: Briefings and notifications ([#4](https://github.com/malekachouri/ai-pulse/pull/4))
- **Done:** 10-section personalised daily briefings, per-user schedule and time zone, notification center
  and preferences.
- **Where:** [NOTIFICATIONS.md](NOTIFICATIONS.md).

### Phase 8: Production readiness ([#5](https://github.com/malekachouri/ai-pulse/pull/5))
- **Goal:** something that can run in production safely.
- **Done:** 7 images (non-root, read-only root filesystem), Docker Compose for dev and prod, Caddy with TLS,
  CI/CD, Prometheus/Grafana/Alertmanager with alert rules and unit tests, Redis-backed rate limiting,
  secrets as files, admin console, backups and a safe restore script, an end-to-end smoke test.
- **Concepts:** defence in depth for containers; supply-chain security (Trivy gate, CodeQL, `pip-audit`,
  `npm audit`, Dependabot, SBOM and signed build provenance, every GitHub Action pinned to a commit SHA);
  observability (metrics, dashboards, alerts, Beat heartbeat).
- **Where:** [DEPLOYMENT.md](DEPLOYMENT.md), `.github/workflows`, `infra/`.

### Toolchain upgrades ([#17](https://github.com/malekachouri/ai-pulse/pull/17), [#20](https://github.com/malekachouri/ai-pulse/pull/20), Dependabot PRs)
- Node 26 LTS and ESLint 10 across the stack; backend moved to Python 3.15; base images and actions kept
  current by Dependabot, each update merged only with green CI.

### Phase 9: Audit ([#21](https://github.com/malekachouri/ai-pulse/pull/21))
- **Goal:** verify everything for real and fix what was wrong.
- **Done:** live runs of every source, API, browser and full-stack checks; **22 bugs fixed**, including SSRF
  through admin-configured source URLs, undelivered password-reset emails, ingestion failure accounting,
  RAG retrieval and WCAG 2.1 AA contrast and structure.
- **Concepts:** SSRF guard on every request and redirect (`app/ingestion/netguard.py`); verification over
  assumption.
- **Where:** [AUDIT_REPORT.md](AUDIT_REPORT.md).

### Quality gates ([#22](https://github.com/malekachouri/ai-pulse/pull/22), [#25](https://github.com/malekachouri/ai-pulse/pull/25), [#26](https://github.com/malekachouri/ai-pulse/pull/26))
- Playwright browser tests in CI: every page, three roles, both themes, mobile, with axe-core accessibility
  checks; label-in-name fixes (WCAG 2.5.3); branch protection guide in [CONTRIBUTING.md](../CONTRIBUTING.md).
- A polynomial ReDoS found by CodeQL in the tokenizer was rewritten as linear-time matching.
- The default critical-CVE alert threshold became CVSS 9.5.
- Build prompts for every phase saved in [docs/prompts](prompts/README.md).

### Additional features ([#27](https://github.com/malekachouri/ai-pulse/pull/27), [#28](https://github.com/malekachouri/ai-pulse/pull/28), [#31](https://github.com/malekachouri/ai-pulse/pull/31))
- **Learn:** "what to learn next" recommendations, each with its reason; a Learning Assistant with short
  daily lessons, labelled AI-generated and linked to curated official documentation.
- **Release change detection:** what changed between two releases (version, license, benchmarks,
  changelog), **extracted from the release notes, no AI**; anything a source does not state is "not documented".
- **Bug Intelligence:** why a bug or CVE occurs, impact, affected versions and fixes, as facts copied from
  structured fields plus optional AI text with numbered citations; "insufficient information" otherwise.
  [#31](https://github.com/malekachouri/ai-pulse/pull/31) added versions and fixes quoted from the official record.
- **Watchlist**, **model comparison** (only cited benchmark numbers), **weekly PDF report**.
- **Encrypted offsite backups:** OpenPGP AES-256 before upload, S3-compatible storage with SigV4 signing,
  retention, and a restore drill in CI.

### Running on a local model: stability fixes ([#29](https://github.com/malekachouri/ai-pulse/pull/29)–[#34](https://github.com/malekachouri/ai-pulse/pull/34))
Found while running AI Pulse on Windows 11 / WSL2 with Ollama (`qwen2.5:3b`) on a CPU. Each one is in
[section 3](#3-incidents-problem-root-cause-fix) with its root cause.

### Developer experience ([#35](https://github.com/malekachouri/ai-pulse/pull/35)–[#38](https://github.com/malekachouri/ai-pulse/pull/38))
- [ROADMAP.md](ROADMAP.md): ideas recorded for later instead of half-built.
- `scripts/check.sh` runs every check with Docker only; `scripts/update.sh` updates a local stack;
  `python -m app.cli reanalyse` analyses one item again.
- `CLAUDE.md` and Claude Code skills `/check`, `/update`, `/reanalyse` in `.claude/skills/`.
- Smoke test finds the published web port itself; Beat health check made cheap; TLS 1.2 minimum explicit.

### Skills Radar ([#39](https://github.com/malekachouri/ai-pulse/pull/39), [#44](https://github.com/malekachouri/ai-pulse/pull/44), [#46](https://github.com/malekachouri/ai-pulse/pull/46), [#47](https://github.com/malekachouri/ai-pulse/pull/47))
- **Goal:** follow new MCP servers, Claude Code plugins and Agent Skills, for any project.
- **Done:** connectors for the official MCP Registry and Claude Code plugin marketplaces, stored in their own
  table (thousands of entries a day must not flood the news feed or the AI queue); install commands built
  from each listing's own fields; technology tags; an on-demand, general AI explanation ("What is it good
  for?") grounded in the listing and README; daily cleanup of inactive entries.
- **Concepts:** resumable cursor pagination with a page budget; marketplace "baseline" (already listed, not
  new); path-traversal rejection; schema-constrained output with required fields; citation matching for
  small models; data retention.
- **Where:** [SKILLS.md](SKILLS.md), `backend/app/skills`, `backend/app/ingestion/connectors/skills.py`.

### Security and licensing ([#37](https://github.com/malekachouri/ai-pulse/pull/37), [#44](https://github.com/malekachouri/ai-pulse/pull/44), [#45](https://github.com/malekachouri/ai-pulse/pull/45), [#47](https://github.com/malekachouri/ai-pulse/pull/47))
- Repository checked for committed secrets (full history: none) and for unauthenticated write or admin
  endpoints (none).
- Proprietary license ("all rights reserved") for a public repository.
- Dependency audit: production dependencies strict; development tools strict except advisories listed with
  a reason and an **expiry date** (see [SECURITY.md](../SECURITY.md#accepted-advisories-githubnpm-audit-allowlist)).

---

## 3. Incidents: problem, root cause, fix

| # | Symptom | Root cause | Fix | PR |
|---|---|---|---|---|
| 1 | AI analysis runs failed with a database deadlock | two pipeline runs (Beat tick and post-ingestion) updated the same rows in a different order | one run at a time with a transaction-scoped PostgreSQL advisory lock | [#29](https://github.com/malekachouri/ai-pulse/pull/29) |
| 2 | Long AI requests failed after 30 s | the Next.js proxy (Node 26) cut proxied requests at 30 s | `experimental.proxyTimeout` of 10 minutes | [#30](https://github.com/malekachouri/ai-pulse/pull/30) |
| 3 | Bug Intelligence said "no official remediation" although the record says "fixed in 0.31.8"; truncated headline quoted twice | fixes stated in the free text were not read; cut-off fragments were quoted | `stated_fix()` from the record; fragments ending in "…" skipped, duplicates dropped | [#31](https://github.com/malekachouri/ai-pulse/pull/31), [#32](https://github.com/malekachouri/ai-pulse/pull/32) |
| 4 | Random sign-outs | two tabs refreshed with the same rotating token at once, which looked like token theft | 30 s reuse grace period on the server; Web Locks so tabs take turns | [#32](https://github.com/malekachouri/ai-pulse/pull/32) |
| 5 | "connection is closed" during AI work | PostgreSQL closes connections idle in a transaction after 5 min; a CPU model takes longer | `SET LOCAL idle_in_transaction_session_timeout = '30min'` only for AI work | [#33](https://github.com/malekachouri/ai-pulse/pull/33) |
| 6 | Re-analysing a CVE analysed another item | the LLM stage took the most important pending item, not the chosen one | `pending_llm()` honours `article_ids` | [#34](https://github.com/malekachouri/ai-pulse/pull/34) |
| 7 | Smoke test "login is not rate limited" | it ran on the e2e stack, whose rate limits are relaxed on purpose | the smoke test detects the e2e stack and says so; `check.sh smoke` restarts it normally | [#36](https://github.com/malekachouri/ai-pulse/pull/36) |
| 8 | Smoke test "API through the web rewrite" | it tested port 3000; the app ran on 3005 (`WEB_PORT`) and another program used 3000 | read `WEB_PORT`, then ask Docker which port is published | [#37](https://github.com/malekachouri/ai-pulse/pull/37), [#38](https://github.com/malekachouri/ai-pulse/pull/38) |
| 9 | Beat "unhealthy" while working | the health check imported the app (≈4 s) and timed out at 10 s with Ollama using every core | standard-library Redis check (≈0.5 s under load), 30 s timeout | [#37](https://github.com/malekachouri/ai-pulse/pull/37) |
| 10 | CodeQL "insecure TLS version" | `ssl.create_default_context()` without an explicit minimum | `minimum_version = TLSv1_2` (also for SMTP) | [#37](https://github.com/malekachouri/ai-pulse/pull/37) |
| 11 | CodeQL polynomial ReDoS | a regular expression with nested repetition in the tokenizer | linear-time rewrite | [#26](https://github.com/malekachouri/ai-pulse/pull/26) |
| 12 | CI: user signed out during a browser test | uvicorn closed an idle keep-alive connection as the proxy reused it (ECONNRESET), and the client treated the 500 as a refused refresh | only a 4xx ends the session, network errors and 5xx are retried; uvicorn keep-alive 75 s | [#44](https://github.com/malekachouri/ai-pulse/pull/44) |
| 13 | Ollama timeouts while embedding | batches of 64 texts are too slow on a CPU; one failure lost the whole run | 8 per request and 40 per run for Ollama; every successful batch kept | [#46](https://github.com/malekachouri/ai-pulse/pull/46) |
| 14 | CI: "what changed since v1.0" missing in a browser test | the worker held the analysis lock (the seed's analysis did nothing and exited 0) and analyses newest items first | the seed analyses exactly its items and waits for the lock; `ai-analyze` exits 3 when busy | [#46](https://github.com/malekachouri/ai-pulse/pull/46) |
| 15 | Skill explanations empty with `qwen2.5:3b` | optional fields in the reply schema, and small models leave citations empty | required fields and an example reply; uncited text matched to the source holding its words; a reason per empty section | [#47](https://github.com/malekachouri/ai-pulse/pull/47) |
| 16 | CI dependency audit red on every PR | GHSA-fc5q-39xc-vjpf (picomatch ReDoS): every version affected, no fix; only in dev tools | production audited strictly; dev advisory accepted until 2026-12-31 with its reason, then it blocks again | [#47](https://github.com/malekachouri/ai-pulse/pull/47) |

---

## 4. Concept index

| Concept | What it means here | Where in the code | Since |
|---|---|---|---|
| Layered architecture | API → services → repositories → models | `backend/app/{api,services,repositories,models}` | Phase 1 |
| Migrations with downgrade | every schema change reversible; CI runs upgrade → check → downgrade → upgrade | `backend/alembic/versions` (0001–0010) | Phase 1 |
| Password hashing | Argon2id | `app/core/security.py` | Phase 1 |
| Refresh-token rotation and reuse detection | a reused rotated token revokes the family; 30 s grace for concurrent tabs | `app/services/auth.py` | Phase 1, [#32](https://github.com/malekachouri/ai-pulse/pull/32) |
| Cross-tab coordination | Web Locks API around token refresh | `frontend/src/lib/api.ts` | [#32](https://github.com/malekachouri/ai-pulse/pull/32) |
| RBAC | roles checked by FastAPI dependencies | `app/api/deps.py` | Phase 1 |
| Input validation | Pydantic on every body and query; unknown parameters rejected | `app/schemas`, `reject_unknown_query_params` | Phase 3 |
| Retries, backoff, rate limits | exponential backoff with jitter, per-host limits, `Retry-After`, quota resets | `app/ingestion/http.py` | Phase 4 |
| Checkpoints and conditional requests | incremental collection, ETag / If-Modified-Since | connectors | Phase 4 |
| Deduplication | canonical keys, title similarity, embedding similarity | `app/ingestion/writer.py`, `app/ai/pipeline.py` | Phases 4–5 |
| SSRF protection | internal destinations refused on every request and redirect | `app/ingestion/netguard.py` | [#21](https://github.com/malekachouri/ai-pulse/pull/21) |
| Structured LLM output | JSON validated against a schema, retried with feedback | `app/ai/providers/base.py` | Phase 5 |
| Grounding (hallucination control) | sentences with numbers, versions, ids or dates missing from the sources are removed | `app/ai/claims.py` | Phase 5 |
| RAG | sufficiency gate, numbered sources, citations validated, "insufficient information" | `app/ai/rag.py` | Phase 5 |
| Hybrid search | BM25-style keyword + pgvector HNSW semantic search | `app/ai/search.py` | Phase 5 |
| Explainable scoring | importance score with its reasons, separate from CVSS | `app/ai/scoring.py` | Phase 5 |
| Extraction without AI | release changes from the notes only; "not documented" otherwise | `app/ai/changes.py` | [#27](https://github.com/malekachouri/ai-pulse/pull/27) |
| Cited facts + optional AI | Bug Intelligence: structured facts with source numbers, AI text grounded | `app/ai/bugintel.py` | [#28](https://github.com/malekachouri/ai-pulse/pull/28) |
| Advisory lock | one analysis run at a time, released at commit | `app/ai/pipeline.py` | [#29](https://github.com/malekachouri/ai-pulse/pull/29) |
| Per-transaction timeout | longer idle limit only while waiting on a model | `app/db/session.py` | [#33](https://github.com/malekachouri/ai-pulse/pull/33) |
| Batching with partial progress | small embedding batches; each success kept | `app/ai/pipeline.py`, `app/ai/providers` | [#46](https://github.com/malekachouri/ai-pulse/pull/46) |
| Data retention | daily cleanup of inactive radar entries and old job logs | `app/services/retention.py` | [#46](https://github.com/malekachouri/ai-pulse/pull/46) |
| Resumable pagination | cursor kept in the checkpoint when a run's page budget is spent | `app/ingestion/connectors/skills.py` | [#39](https://github.com/malekachouri/ai-pulse/pull/39) |
| Schema-constrained output for small models | required fields, example reply, citation matching | `app/skills/explain.py` | [#47](https://github.com/malekachouri/ai-pulse/pull/47) |
| Container hardening | non-root, read-only root filesystem, minimal images | `backend/Dockerfile`, `frontend/Dockerfile` | Phase 8 |
| Health checks | per service; cheap checks that survive CPU load | `backend/docker/healthcheck.py` | Phase 8, [#37](https://github.com/malekachouri/ai-pulse/pull/37) |
| Observability | Prometheus metrics, Grafana dashboards, alert rules with unit tests | `infra/prometheus`, `infra/grafana` | Phase 8 |
| Supply-chain security | SHA-pinned actions, Trivy, CodeQL, pip-audit, npm audit, Dependabot, signed provenance | `.github/workflows` | Phase 8 |
| Risk acceptance with expiry | dev-only advisory accepted until a date, then blocks again | `scripts/npm-audit.sh`, `.github/npm-audit-allowlist` | [#47](https://github.com/malekachouri/ai-pulse/pull/47) |
| Encrypted offsite backups | GPG AES-256 before upload, S3 SigV4, retention, restore drill | `infra/backup` | [#28](https://github.com/malekachouri/ai-pulse/pull/28) |
| Accessibility | WCAG 2.1 AA; axe-core on every page in CI | `e2e/tests` | [#21](https://github.com/malekachouri/ai-pulse/pull/21), [#22](https://github.com/malekachouri/ai-pulse/pull/22) |
| Testing strategy | real PostgreSQL, mocked external HTTP with recorded responses, mutation checks of new tests | `backend/tests`, `frontend/src/**/*.test.tsx`, `e2e/` | all phases |
| Branch protection | merges only with green required checks | [CONTRIBUTING.md](../CONTRIBUTING.md) | [#22](https://github.com/malekachouri/ai-pulse/pull/22) |
| AI-assisted development | build prompts per phase, `CLAUDE.md`, project skills | `docs/prompts`, `CLAUDE.md`, `.claude/skills` | [#22](https://github.com/malekachouri/ai-pulse/pull/22), [#36](https://github.com/malekachouri/ai-pulse/pull/36) |

---

## 5. Decisions and their reasons

| Decision | Reason | PR |
|---|---|---|
| Official sources only; no scraping | trust and terms of use; pages without RSS/API (Anthropic, Mistral, Meta news) are covered through their official GitHub and Hugging Face accounts instead | Phase 4 |
| AI text stored and shown separately from facts, labelled AI-generated | a reader must always know what is a fact from a source and what the model wrote | Phase 5 |
| Grounding checks numbers, versions, ids and dates | these are the details that can be checked automatically and that cause harm when wrong (a wrong "fixed in" version); free-form ideas cannot be verified automatically, so the claims stay modest | Phase 5 |
| Release change detection without AI | comparing two releases is extraction, so it should not be generated | [#27](https://github.com/malekachouri/ai-pulse/pull/27) |
| Skills Radar entries in their own table | more than a thousand registry changes a day would flood the news feed and the AI queue | [#39](https://github.com/malekachouri/ai-pulse/pull/39) |
| Explanation general, not tied to AI Pulse | the owner uses the radar for many projects | [#44](https://github.com/malekachouri/ai-pulse/pull/44) |
| Ideas recorded in ROADMAP.md instead of built at once | finish and verify what is in progress first | [#35](https://github.com/malekachouri/ai-pulse/pull/35) |
| Repository stays public, with a proprietary license and GitHub security settings | private repositories would lose free code scanning and branch rules on a free plan; the license protects reuse legally | [#45](https://github.com/malekachouri/ai-pulse/pull/45) |
| Dev-only advisory accepted with an expiry, approved by the owner | no fix exists; production stays strict; the exception expires by itself | [#47](https://github.com/malekachouri/ai-pulse/pull/47) |

---

## 6. Work outside this repository

Steps that are not in the code but are part of running and presenting the project.

**Local environment (owner's PC).** Windows 11 with WSL2 and Docker Engine (no Docker Desktop, no Python or
Node on the host); Ollama with `qwen2.5:3b`. Settings learned along the way:
- `WEB_PORT=3005` in `.env`, because another program uses port 3000.
- `.env`: `LLM_TIMEOUT_SECONDS=900`, `AI_BATCH_SIZE=2`, and `EMBEDDING_PROVIDER=none` while large embedding
  batches timed out; after [#46](https://github.com/malekachouri/ai-pulse/pull/46) embeddings can be turned
  back on with `EMBEDDING_PROVIDER=ollama` and `EMBEDDING_MODEL=nomic-embed-text`.
- Ollama service: `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_KEEP_ALIVE=2m` (memory
  use about 4.3 GB → about 2.5 GB).
- Memory exhaustion (swap full, disk at 100 %) traced to Ollama plus four kind clusters and other
  projects running at once; those were stopped and their auto-restart disabled.

**GitHub settings (owner, recommended 2026-11-16).** Only the owner can see or change them: two-factor
authentication, secret scanning and push protection, Dependabot alerts and security updates, private
vulnerability reporting, approval for outside contributors' workflows, read-only workflow permissions, and the
branch ruleset on `main`. The Dependabot dependency graph is confirmed active (its runs appear in Actions).

**Portfolio and CV.** AI Pulse added to the portfolio as a featured project with screenshots
(malekachouri/Portfolio-Malek-Achouri#18, #19), its claims corrected to match the code (#20), and entries
for the French and English CVs written in the same style as the other projects.

---

## 7. Open items

| Item | When | Where |
|---|---|---|
| Try "Regenerate with AI" on a radar entry with the real local model after [#47](https://github.com/malekachouri/ai-pulse/pull/47) | next update on the owner's PC | Skills Radar |
| Remove the picomatch allowlist entry once a fixed version exists | before 2026-12-31 (it blocks CI again after that date) | `.github/npm-audit-allowlist`, [SECURITY.md](../SECURITY.md) |
| Remaining suggestions (interactive priority, shorter sources for small models, alerts on offsite backup failures, PITR, admin 2FA, more marketplaces…) | when needed | [ROADMAP.md](ROADMAP.md) |

When a new pull request is merged, add a line to the [timeline](#1-timeline) and, if it fixes a problem or
introduces a concept, to [section 3](#3-incidents-problem-root-cause-fix) or [section 4](#4-concept-index).
