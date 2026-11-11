# Security

## Reporting a vulnerability

Please **do not open a public issue**. Use GitHub's private vulnerability reporting (repository →
*Security* → *Report a vulnerability*). Include what is affected, how to reproduce it, and the impact
you observed. We acknowledge reports within 3 business days and aim to ship fixes for high and critical
issues within 14 days. We credit reporters who wish to be credited.

## Threat model (summary)

| Asset | Threats considered | Main controls |
|---|---|---|
| User accounts | credential stuffing, brute force, session theft, token replay | Argon2id, auth rate limits per IP, short-lived JWT in memory, rotating httpOnly refresh cookie with reuse detection, revocation on password change |
| Admin functions | privilege escalation, unaudited changes | server-side RBAC on every route, last-admin and self-lockout protection, audit log with actor and IP |
| Secrets (DB, JWT, API keys) | leakage through code, images, logs, CI | Docker secret files (`/run/secrets`), never in images, env files or git; CI secrets scoped to GitHub environments; Trivy secret scanning; logs never include tokens |
| Data integrity | invented facts, tampering, SQL injection | provenance on every item, facts and AI output stored separately, ORM with bound parameters, strict Pydantic validation |
| Availability | abusive clients, expensive AI calls, queue floods | global, auth, search and AI rate limits; daily token budget; bounded page sizes; resource limits per container; Redis `noeviction` alerts |
| Infrastructure | container escape, lateral movement, exposed databases | non-root, read-only root filesystems, `cap_drop: ALL`, `no-new-privileges`, internal data network (no internet, never published), least-privilege DB roles |
| Supply chain | vulnerable or compromised dependencies, base images | pinned versions, pip-audit and npm audit, Trivy gate, CodeQL, Dependabot, SBOM and signed build provenance |

## Controls in detail

### Authentication and sessions
- Passwords: Argon2id (parameters upgraded transparently on login), at least 12 characters and 3 character classes.
- Unknown e-mail addresses take the same time as wrong passwords (dummy hash). Password-reset requests
  get the same response whether or not the account exists; the email is sent after the response
  (background task), so neither latency nor an SMTP failure reveals the account.
- Reset tokens: random, single-use, stored as a SHA-256 hash, valid 30 minutes; emailed over SMTP
  (`SMTP_*` settings). Without SMTP nothing is sent and the console backend never logs the token.
- Access token: HS256 JWT, 15 minutes, sent as `Authorization: Bearer`, kept in memory by the web app (never in `localStorage`).
- Refresh token:
  - 384-bit random value, stored only as a SHA-256 hash;
  - delivered as a `HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth` cookie;
  - rotated on every use. Replaying a rotated token revokes the whole token family.
- Password change and reset revoke every session. Deactivating a user revokes their sessions.

### Authorization
Roles are `admin`, `analyst` and `user`, checked by FastAPI dependencies on the server. The UI hides
what a role cannot do, but the API enforces it.

- Analysts can operate: ingestion status, job retries, AI status, usage, system health.
- Only admins manage users, roles, sources and read the audit log.

### Input validation and output
- Every body and query string is a Pydantic model. Unknown query parameters are rejected (422) on every
  route by a router-level check against the OpenAPI schema, sizes are bounded, URLs are validated, and
  sort fields are whitelisted.
- Outbound requests from collectors (source URLs are admin-configured, and what they fetch is
  published) refuse internal destinations on every request and redirect: cloud metadata,
  loopback, private and link-local ranges, `localhost`/`*.internal`/single-label names such as
  `postgres`, and - without an outbound proxy - names that resolve to such addresses
  (`app/ingestion/netguard.py`). The admin API rejects such URLs up front.
  `INGESTION_ALLOW_PRIVATE_HOSTS=true` lifts this for intranet-only deployments.
- SQL goes through SQLAlchemy with bound parameters. The few raw statements use bind parameters only.
- Errors use one envelope and never leak stack traces (unhandled errors are logged server-side with
  the request path).
- The frontend renders text, never HTML from sources. Links go through `safeUrl` (http and https only).

### Rate limiting (`app/core/ratelimit.py`)
Fixed-window counters in Redis, shared by all API replicas. All of them are configurable (`RATE_LIMIT_*`):

| Scope | Key | Default |
|---|---|---|
| global | client IP, every `/api/v1` request | 600 / minute |
| auth | client IP: login, register, password change/reset | 10 / minute |
| search | user (or IP) | 60 / minute |
| ai | user (or IP): Ask AI Pulse, on-demand briefings | 10 / minute |

Rejections return `429` with `Retry-After` and are counted in `aipulse_rate_limited_total`.

The client IP comes from `X-Forwarded-For` **only** when the request arrives from the edge proxy's
fixed address (`EDGE_IP`). A client cannot spoof its IP to escape the limits. If Redis is unreachable
the limiter fails open (logged, `aipulse_dependency_up{name="redis"}` drops, and an alert fires), so
that a cache outage does not take the whole service down.

### Transport and browser security
- Caddy terminates TLS (automatic certificates) and adds HSTS.
- The API sets the following headers:
  - `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`;
  - `Referrer-Policy`, `Permissions-Policy`, `Cross-Origin-Opener-Policy`;
  - `Cache-Control: no-store` on API responses;
  - HSTS in production.
- The web app sends a Content-Security-Policy on every page: `default-src 'self'`, no third-party
  scripts, `object-src 'none'`, `base-uri 'self'`, `form-action 'self'`, `frame-ancestors 'none'`.
  `script-src` allows `'unsafe-inline'` because Next.js bootstraps pages with inline scripts (no
  per-request nonces); `img-src` allows any HTTPS host (avatars, source images).
- CORS is an explicit allow-list (the web app calls the API same-origin anyway). Production refuses
  `*` and plain-http origins.
- `/metrics` requires a bearer token and the edge never routes it. Grafana and Prometheus listen on `127.0.0.1` only.

### Secrets management
- `scripts/generate-secrets.sh` creates random secrets in `./secrets`. The directory is mode 700 and
  ignored by git and by Docker build contexts.
- Compose mounts the files at `/run/secrets/<name>`. The settings loader reads them, and environment
  variables take precedence. Empty values mean "not configured", so a blank `OPENAI_API_KEY=` never
  hides a secret file.
- In production the application refuses to start with:
  - a JWT secret shorter than 32 characters or the development default;
  - `COOKIE_SECURE=false`;
  - `DEBUG=true`, `EXPOSE_RESET_TOKEN=true`;
  - wildcard or plain-http CORS origins.
- AI provider keys are environment configuration only. The admin console shows whether a key is set, never its value.
- CI secrets live in GitHub *environments* (`staging`, `production`) with required reviewers. Workflows
  default to `contents: read`, and jobs request extra permissions explicitly. The deploy job uses a
  deploy-only SSH key, a pinned host key and a short-lived registry token.

#### Rotating secrets
| Secret | Procedure |
|---|---|
| JWT secret, metrics token, Redis password | `./scripts/generate-secrets.sh --force` then `docker compose ... up -d --force-recreate --wait`. A JWT rotation signs every user out. |
| Application / metrics / superuser DB password | `./scripts/rotate-db-password.sh app\|metrics\|postgres`: runs `ALTER ROLE` first, then updates the secret files and recreates the services that use them |
| Grafana admin | `docker compose exec grafana grafana cli admin reset-admin-password '<new>'`, then update `secrets/grafana_admin_password` |
| LLM / GitHub / NVD keys | revoke at the provider, write the new key to its file, recreate `api` and `worker` |

### Containers and hosts
- Images run as fixed non-root UIDs, contain no package manager at runtime (no pip or npm in the app
  images, no gosu in PostgreSQL), and receive OS updates at build time.
- Compose runs every service with a read-only root filesystem (tmpfs where needed), `cap_drop: [ALL]`,
  `no-new-privileges`, `init`, memory and CPU limits, and log rotation.
- Networks: PostgreSQL and Redis sit on an *internal* network, with no internet access and no published
  port. Only the edge (80/443) and, on `127.0.0.1`, web, Prometheus and Grafana are published.
- PostgreSQL:
  - `scram-sha-256` and data checksums;
  - the application uses a non-superuser role that owns only its database;
  - postgres-exporter uses a `pg_monitor`-only role;
  - the superuser is used only for initialisation, backups and restores.
- Redis: password-protected, `noeviction`; `FLUSHALL`, `FLUSHDB`, `DEBUG` and `KEYS` are disabled.

### Dependency and container scanning
| Check | Where | Gate |
|---|---|---|
| `pip-audit` (backend, incl. dev) | CI `dependencies` | any known vulnerability fails |
| `npm audit` (all frontend dependencies) | CI `dependencies` | moderate and above fail |
| Trivy (all 7 images: OS + language packages + secrets) | CI `containers`, release `publish` | fixable HIGH/CRITICAL fail; SARIF uploaded to code scanning |
| CodeQL (Python, TypeScript, workflow files) | `codeql.yml` | findings in code scanning |
| Ruff `S` rules (Bandit), shellcheck, actionlint | CI | any finding fails |
| Dependabot | weekly | pip, npm, Docker base images, compose images, GitHub Actions |
| Pinned GitHub Actions | every workflow | each `uses:` is pinned to a full commit SHA (version in a comment, kept current by Dependabot), so a moved or hijacked tag cannot change what runs |

Base-image CVEs keep arriving after a release, so CI also rebuilds and re-scans every week. When a
finding has no fix yet, Trivy's `--ignore-unfixed` keeps the gate actionable. Review the full report in
code scanning, and do not add blanket ignores.

### Backups
Scheduled and pre-deployment `pg_dump` with checksums. Restores always go to a new database and are
swapped in only after they succeed (see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md#5-backups-and-restore)).
Dumps contain personal data: store them encrypted, off-site, with restricted access.

### Data protection
Personal data is limited to: e-mail, optional name, password hash, preferences, bookmarks, read
state, notifications and briefings. Deleting a user cascades to all of it (preferences, tokens,
bookmarks, read state, notifications, briefings); audit-log entries are kept with the actor set to NULL,
and AI usage rows keep only an unlinked user UUID for cost accounting. AI providers receive only
public source content and the user's question for Ask AI Pulse, never account data.
