# AI Pulse: final audit report (phase 9)

Date: 2026-11-10 · Audited revision: `main` at `1b82df4` (after PR #20) · Fixes on branch
`claude/busy-wozniak-1y66q2`.

**Method.** Nothing in this report is taken from the code or the docs alone; every statement was
verified by running something:
- **Data:** all 28 sources were collected live from their real APIs, about 6,200 items, into a separate
  database.
- **API:** every API operation was called as an anonymous visitor, a user and an admin.
- **Browser:** every page of the production build was opened with Playwright and checked with axe-core,
  on desktop and mobile, in both themes.
- **Full stack:** the 7 images were rebuilt, scanned and run together, with every Compose profile, the
  HTTPS edge included.

Where something could not be verified here, section 5 says so, along with the reason.

---

## 1. Implemented features

Verified in this audit, by the method shown in brackets:

| Area | Feature | Verified by |
|---|---|---|
| Collection | 14 connectors, 28 official sources: NVD, CISA KEV, Kubernetes CVE feed, GitHub (releases, issues, advisories, rising repositories), arXiv, Hugging Face (models, daily papers, blog), vendor blogs (OpenAI, Google DeepMind, AWS, GCP, CNCF, Docker, Kubernetes), status pages (GitHub, OpenAI, Anthropic, Docker, AWS, Azure, GCP) | live runs (19 sources) + recorded fixtures (all 14 connectors) |
| Collection | per-host rate limits shared through Redis, retries with backoff and `Retry-After`, checkpoints and ETags, in-batch and cross-source dedup, failed-job retries, source health | live runs, 72 ingestion and destination-guard tests |
| Feeds | news, models, tools, research, GitHub, bugs, security, DevOps/cloud. Each has URL-synced filters (type, category, source, severity, importance, date) and its own search | browser crawl + UI flows |
| Search | keyword (PostgreSQL FTS + BM25 re-ranking), semantic and hybrid (pgvector + RRF) when embeddings exist | live queries; semantic/hybrid with deterministic test embeddings |
| AI | rule-based stage for every item: cleaning, language, categories, keywords, entities, duplicate detection, explainable importance score | run on 6,234 live items (14 duplicates found, all genuine) |
| AI | LLM stage: summary, impact, actions and learning topics, checked against the source text; token budget and cost tracking | provider wire-format tests + scripted LLM tests (no live LLM, see §5) |
| AI | "Ask AI Pulse": retrieval, a sufficiency gate *before* generation, citations validated, unsupported claims removed; lists sources only when no LLM is set | live questions on real data + tests |
| Radar | bugs with fix tracking, incident states re-verified on status pages, severity only with a documented basis | live status pages + tests |
| Briefings | personalised 10-section briefing (user timezone, frequency, "what changed") | generated from live data for a user following Kubernetes (25 cited items) |
| Notifications | critical CVE, KEV, bug, outage, model-release and briefing alerts; per-kind preferences; each event notified once | alert engine run on live data (second run created 0) |
| Accounts | register, login, rotating refresh cookie, sign out, change password, password reset by email, roles (admin, analyst, user) | 20 browser flows + API probes |
| Admin | system health, usage, users and roles, sources (create/edit/disable/run), connector health, jobs and retries, AI configuration and usage, audit log | browser crawl as admin + API probe |
| Operations | 7 hardened images (non-root, read-only root filesystem), Compose dev/prod, Caddy HTTPS edge, Prometheus with 17 alert rules, Alertmanager, Grafana dashboards, daily backups with a restore drill, CI/CD with security gates | full-stack run (§3) |

## 2. Fixed bugs

Every bug below was reproduced first, then fixed and covered by a test or a re-run.

### Data collection
| # | Bug (how it was reproduced) | Fix |
|---|---|---|
| 1 | Counts were wrong for records saved without an article (e.g. old KEV entries). The first KEV run on an empty database reported `created=40 updated=1739` | new rows now count as `created`, unchanged ones as `skipped` |
| 2 | Job totals didn't add up. NVD: `fetched=5000 created=4732`, and the 268 rejected CVEs and in-batch duplicates appeared nowhere | those are now counted as `skipped` |
| 3 | When *every* request of a multi-repo source failed (GitHub 403 on all repos), the job was `partial`, `last_success_at` was updated and the failure counter reset. A dead source never triggered the alert | the job is now `failed`, counts as a consecutive failure, and is retried and alerted on |
| 4 | After a provider said the quota was spent (`x-ratelimit-remaining: 0`), the client kept calling it. GitHub bans clients that ignore its limits | requests to that host stop until `x-ratelimit-reset`. GitHub's secondary limits (403 + `Retry-After`) are retried after the delay |
| 5 | 4xx responses lost their body, so a failure read only "HTTP 400 from api.openai.com" | the error now keeps the provider's explanation (truncated). Keys are never echoed |

### API
| # | Bug | Fix |
|---|---|---|
| 6 | Unknown query parameters were ignored on `/news`, `/briefings`, `/bookmarks` and 19 other routes, so `?severty=critical` returned unfiltered data. SECURITY.md claimed the opposite | router-level check against the OpenAPI schema: 422 on every route |
| 7 | **SSRF through source URLs.** An admin-created source could point at the cloud metadata service (`169.254.169.254`), `localhost`, private ranges or Docker service names (`postgres`). The worker would fetch it and publish the response as items. Reproduced: all 6 internal URLs were accepted | collectors refuse internal destinations on every request and redirect (literal IPs, internal names, and resolved addresses when no proxy is in use); the admin API rejects them up front (400). Opt-in `INGESTION_ALLOW_PRIVATE_HOSTS` for intranet feeds |
| 8 | **Password reset never reached anyone in production.** The only email backend logged "not sent" | SMTP sender (STARTTLS/SSL, auth, password as a Docker secret) and a reset *link* when `PUBLIC_URL` is set. Delivery happens after the response, so neither timing nor an SMTP error reveals whether an account exists |

### AI
| # | Bug | Fix |
|---|---|---|
| 9 | OpenAI reasoning models (o-series, gpt-5) reject a non-default `temperature`. With `LLM_TEMPERATURE=0.2`, every call would fail | one retry without `temperature`, remembered for that model |
| 10 | KEV items were scored with a type baseline, even though the linked CVE record has the official CVSS | the score uses the linked CVSS, citing the CVE as its basis |
| 11 | "What critical Kubernetes vulnerabilities…" returned a Microsoft CVE first. Common words filled the 150-candidate pool, so the decisive term never reached BM25 | candidates matching more distinct question terms come first. "critical" / "high-severity" became a filter on the official severity. Type words and event verbs are no longer search terms |
| 12 | "Which AI models were released recently?" wasn't recognised as a model-release question (the regex required adjacent words), and returned arXiv papers | broader pattern. Results are now model releases and news |
| 13 | "What is the capital of France?" passed the sufficiency gate because one item mentioned "capital" | questions with one or two informative terms need every term covered. Now `insufficient` |

### Frontend (accessibility and security)
| # | Bug (axe-core, WCAG 2.1 AA) | Fix |
|---|---|---|
| 14 | No Content-Security-Policy anywhere (web or edge) | CSP on every page (details in §4) |
| 15 | Primary buttons: white on `#3b82f6`, 3.7:1. Critical-severity and status text 3.6:1 on navy and 4.1:1 on tinted badges. Amber text 3.2:1. Muted text at 80% opacity 3.8:1 | dedicated token for solid fills, contrast-checked severity and status colours in both themes |
| 16 | Heading levels skipped (h1 → h3) on most pages | card and feed-item titles are h2 |
| 17 | Auth pages had no `<main>` landmark. `/admin/ingestion` had no h1 while loading, signed out or forbidden | landmark added; heading rendered in every state |
| 18 | `aria-label` on unlabelled spans (unread dots, 20 per feed page). Notification tabs pointed `aria-controls` at elements that don't exist. "Actions" columns had empty headers. In-text links were distinguishable by colour only | labelled images, tab panel rendered, screen-reader header labels, underlined in-text links |

**Result:** 0 axe violations on all 26 pages, in both themes, as anonymous visitor, user and admin
(previously 9 kinds of violation, including "serious" and "critical" ones).

### DevOps
| # | Bug | Fix |
|---|---|---|
| 19 | Caddy, Prometheus, Alertmanager and Grafana had no health check, so `up --wait` treated "started" as healthy | health checks added; all report healthy in the full-stack run |
| 20 | The deploy workflow expanded the registry token into the remote SSH command line, so it was visible in the server's process list during deploys | the token goes to `docker login` over stdin |
| 21 | CI validated the Prometheus/Alertmanager configs with v3.5.0/v0.28.1 while v3.16.0/v0.34.2 are deployed. Dependabot only updates `docker-compose.yml` | CI now reads the tags from `docker-compose.yml` |
| 22 | Operator settings (DB pool, LLM timeout/tokens/temperature, cookie SameSite, reset TTL, SMTP) were missing from `.env.example` | documented |

## 3. Test results

| Check | Result |
|---|---|
| Backend tests (pytest, real PostgreSQL 16 + pgvector, Python 3.15) | **240 passed** (199 before the audit + 41 new) |
| Ruff lint and format (incl. security rules) | clean |
| Alembic: upgrade, `alembic check`, downgrade to base, upgrade | clean (head `0006`) |
| `docs/API.md` regenerated from the code | unchanged |
| Frontend: ESLint, TypeScript, Vitest | clean, clean, **27 passed** |
| Frontend production build (Next.js 16, Node 26) | success, 28 routes |
| Browser crawl: 26 pages × 3 roles × desktop/mobile = 156 page loads | 0 JavaScript errors, 0 failed API calls except the expected ones (signed-out refresh 401, "no briefing yet" 404), 0 horizontal overflow on mobile |
| axe-core (WCAG 2.0/2.1 A and AA + best practices), every page, every role, dark and light themes, desktop | **0 violations** |
| UI flows: register (mismatch, weak password, duplicate, success), session after reload, bookmark, mark read, feed search, global search, Ask, settings persist, notification tabs, keyboard skip link, sign out, wrong password, forgot → reset → login, mobile navigation | **20/20 passed**, no 5xx |
| API probe: 80 operations × anonymous/user/admin | 0 server errors; every admin route returns 403 for users; slowest call 320 ms (queueing a source run), dashboard ~100 ms on 6,200 items |
| Security probe (32 checks): SSRF via source URLs (6, after the fix), IDOR on bookmarks and briefings, tampered and `alg=none` JWTs, role mass-assignment, deactivated user's token, self-demotion, duplicate email, enumeration-safe login and reset, CORS, headers, SQL-like and oversized input | all behave correctly |
| Live connectors (28 sources) | 19 succeeded against the real APIs (NVD 5,000 CVEs, KEV 1,779, arXiv 200, Hugging Face, status pages, blogs); 9 blocked by this environment or the site (§5) |
| Rule-based AI stage on live data | 6,234 items processed, 14 duplicates, all genuine (same CVE from NVD and KEV, same paper from arXiv and HF, same repo in two lists) |
| Dependency audits | pip-audit: no known vulnerabilities; npm audit: 0 vulnerabilities |
| Static configuration checks (the CI "compose" job) | Compose config valid for base/dev/prod with all profiles; promtool config + **17 alert-rule unit tests**; amtool; shellcheck; actionlint; dashboards up to date |
| Image scan (Trivy, fixable HIGH/CRITICAL, vulnerabilities + secrets) | api, worker, beat, migrate, web, redis: **clean**. postgres: 2 HIGH (`apt`) in *this sandbox's* build only (§5) |
| Full stack, all profiles (13 containers incl. Caddy, monitoring, backup) | every service with a health check is healthy; smoke test passed on `http://localhost:3000` and **through Caddy over HTTPS**; HTTP→HTTPS 308; `/metrics` 404 at the edge; Prometheus scrapes API, Postgres and Redis |
| Backup → restore → restart → smoke test | passed (27 tables restored; previous database kept for rollback) |

## 4. Security findings

**Fixed in this audit:**
- SSRF through admin-configured source URLs (#7);
- no Content-Security-Policy (#14);
- the registry token was visible on the deploy server (#20);
- unknown query parameters were silently accepted (#6);
- password-reset delivery could have revealed accounts: timing, SMTP errors (#8);
- clients kept calling a provider after its quota was spent, which risks a ban (#4).

**Verified as correct (no change needed):**
- Argon2id passwords, with identical answers and timing for unknown accounts and wrong passwords;
- 15-minute JWTs kept in memory;
- rotating refresh token in an `HttpOnly; Secure; SameSite=Strict` cookie, with reuse detection;
- password change, password reset and deactivation all revoke sessions immediately;
- admins can't remove their own role;
- tampered and `alg=none` tokens are rejected;
- no IDOR on per-user data;
- the CORS allow-list rejects foreign origins;
- the security headers and HSTS are present at the edge, and `/metrics` is not exposed;
- containers run non-root with a read-only root filesystem and no capabilities;
- secrets are Docker secret files that are never committed;
- dependency audits and Trivy are clean (§3).

**Accepted trade-offs (documented in SECURITY.md):**
- **CSP:** `script-src 'unsafe-inline'`, because Next.js bootstraps pages with inline scripts. Removing it
  needs per-request nonces, which means dynamic rendering of every page.
- **CSP:** `img-src https:`, for source images and avatars.
- **Console noise:** when signed out, the web app's silent session refresh returns 401. It's expected,
  and appears as one console line per page load.

## 5. Remaining limitations

These were not verified here, or were found but deliberately not changed:

- **Live LLM providers (OpenAI, Anthropic, Ollama).**
  - What wasn't tested: no API keys exist in this environment, and model downloads (Hugging Face CDN) are
    blocked, so no real model ran.
  - What was tested: each provider's request and response format (structured output, usage, errors,
    retries) against recorded exchanges; the full pipeline, RAG and briefings with a scripted model;
    "sources only" mode live.
  - What to do: run `python -m app.cli ai-analyze --limit 20` once with your key before relying on
    summaries.
- **Semantic and hybrid search on real embeddings.** Tested with deterministic test vectors only. They
  need `EMBEDDING_MODEL` with 768 dimensions.
- **9 of the 28 sources could not be collected live here:**
  - api.github.com: 5 sources (releases ×3, issues, advisories);
  - status.claude.com and docs.cloud.google.com: 2 sources;
  - www.cncf.io and www.docker.com answered HTTP 403 to the collector. The cause was not determined
    from here.

  The GitHub and blocked-host connectors pass their fixture tests. Check the cncf.io and docker.com
  feeds from the production host: Admin → Ingestion shows each source's last error.
- **Deploy workflow.** Not run: it needs a server, GHCR and SSH secrets. Its script (`scripts/deploy.sh`)
  and the Compose files it uses were exercised locally.
- **postgres image.** The sandbox can't reach Debian mirrors, so it was built with `OS_UPGRADE=false`,
  and Trivy flags `apt` 2.6.1. CI builds with the upgrade, and the Trivy gate passed on PR #20. Releases
  are unaffected.
- **Notification volume.** On live data, the default "critical CVE" rule produced 84 notifications per
  user in a 48-hour window, plus 10 KEV alerts. *Follow-up (after the audit):* the default minimum CVSS
  is now 9.5, which gives 56 for the same window. That is still about 28 a day, because NVD publishes
  many critical CVEs. Users can pick a stricter value or "any critical" in *Settings → Notifications*,
  and followed technologies keep their own rule.
- **Accessibility.** Automated checks don't replace a manual screen-reader pass. *Follow-up:* axe-core
  now runs in CI on every page for every role, in both themes and on a phone layout (`e2e/`). Its
  first run found and fixed horizontally scrolling tables that keyboards couldn't reach, an admin card
  that widened the page on phones, and a badge that inherited low-contrast text.
- **Email.** SMTP delivery was tested against an in-process SMTP server, not a real provider.
- **GitHub CI on the audit commits.** Every CI step was reproduced locally (§3); the hosted workflow runs
  when these commits are proposed as a pull request.

## 6. External API credentials

All are optional: the application runs without them. Put each value in the named file under `secrets/`.

| Credential | Secret file | Needed for | Without it |
|---|---|---|---|
| OpenAI API key | `openai_api_key` | `LLM_PROVIDER=openai`, OpenAI embeddings | rule-based analysis and keyword search only |
| Anthropic API key | `anthropic_api_key` | `LLM_PROVIDER=anthropic` (no embeddings: pair with OpenAI or Ollama) | as above |
| *(none)* Ollama URL | `OLLAMA_BASE_URL` in `.env` | local models | as above |
| GitHub token (fine-grained, public-repository read only) | `github_token` | 5,000 requests/h instead of 60/h, for the 5 GitHub sources | GitHub sources may hit the 60/h limit; the client now stops until the reset |
| NVD API key | `nvd_api_key` | 50 requests/30 s instead of 5/30 s | slower NVD collection (a full 5,000-CVE run takes about 1 minute) |
| SMTP account | `smtp_password` + `SMTP_*` in `.env` | password-reset emails | reset emails are not sent (warning logged at startup) |
| Alert webhook URL | `alert_webhook_url` | Alertmanager → Slack/Teams/webhook | alerts visible in Alertmanager only |

The other 23 sources (NVD, CISA KEV, arXiv, Hugging Face, status pages, blogs) need no credentials.

## 7. Commands to run the application

Local (Docker, production settings). Generate random secrets in `./secrets`:

```bash
./scripts/generate-secrets.sh
```

Copy the settings, then edit `.env` (for local use the defaults work):

```bash
cp .env.example .env
```

Build and start, waiting until every service is healthy:

```bash
docker compose up -d --build --wait
```

Create your administrator account (it prompts for the password):

```bash
docker compose exec api python -m app.cli create-admin --email you@example.com
```

Check that everything works:

```bash
./scripts/smoke-test.sh http://localhost:3000
```

Collect one source now instead of waiting for the schedule:

```bash
docker compose exec api python -m app.cli ingest nvd-cve
```

Monitoring (Grafana on http://localhost:3001, user `admin`, password in `secrets/grafana_admin_password`):

```bash
docker compose --profile monitoring up -d --wait
```

Development with hot reload:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Tests (backend; needs PostgreSQL with pgvector):

```bash
cd backend && TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/aipulse_test pytest -q
```

Tests (frontend):

```bash
cd frontend && npm ci && npm run lint && npm run typecheck && npm test && npm run build
```

The web app is on http://localhost:3000 and the API reference on http://localhost:8000/docs (dev stack).

## 8. Deployment instructions

Full guide: [DEPLOYMENT.md](DEPLOYMENT.md). In short:

1. **Server:**
   - Linux with Docker Engine and Compose v2.24+;
   - ports 80 and 443 open;
   - a DNS name pointing at the server;
   - a deploy user in the `docker` group;
   - the deployment directory, e.g. `/opt/ai-pulse`.
2. **Secrets and settings, once, on the server.** Copy the repository's `docker-compose*.yml`, `infra/`,
   `scripts/` and `.env.example` to the deployment directory, then run:

   ```bash
   ./scripts/generate-secrets.sh
   ```

   ```bash
   cp .env.example .env
   ```

   Then set these in `.env`:
   - `ENVIRONMENT=production`, `DOMAIN=pulse.example.com`, `CORS_ORIGINS=["https://pulse.example.com"]`;
   - `IMAGE_PREFIX=ghcr.io/<owner>/ai-pulse`;
   - the `SMTP_*` settings and `PUBLIC_URL`;
   - optional: `LLM_PROVIDER` and `LLM_MODEL`.

   Optional keys go in `secrets/` (§6).
3. **GitHub:**
   - create the `production` (and optionally `staging`) environment, with required reviewers;
   - secrets: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY` (a deploy-only key) and
     `DEPLOY_KNOWN_HOSTS` (`ssh-keyscan -t ed25519 <host>`, check the fingerprint);
   - variables: `DEPLOY_PATH` and `PUBLIC_URL`.
4. **Release.** Push a tag such as `v1.0.0`. The *Deploy* workflow then:
   - builds the 7 images, scans them (Trivy gate) and pushes them with an SBOM and provenance;
   - waits for approval;
   - over SSH: pulls, backs up, migrates, rolls out, waits for health and runs the smoke test;
   - rolls back automatically on failure.

   A manual run (*Actions → Deploy → Run workflow*) can target staging.
5. **First start without CI** (or to check the server):

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile edge --profile monitoring --profile backup up -d --wait
   ```

   ```bash
   ./scripts/smoke-test.sh https://pulse.example.com
   ```

   ```bash
   docker compose exec api python -m app.cli create-admin --email you@example.com
   ```

6. **Afterwards:**
   - backups run daily (`backup` profile); test a restore with `scripts/restore.sh` (DEPLOYMENT.md §5);
   - rotate secrets as described in DEPLOYMENT.md §8;
   - watch *Admin → Ingestion* and Grafana for source health.
