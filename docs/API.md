# API

REST API under `/api/v1` (FastAPI).

- Interactive documentation: `GET /docs` (Swagger UI).
- Machine-readable schema: `GET /api/v1/openapi.json`.
- In a deployment, the web origin serves the API at `https://<domain>/api/v1/...`; the edge routes `/api/*` straight to FastAPI.

## Conventions

**Content.** JSON request and response bodies; UTF-8; timestamps are ISO 8601 in UTC. Every item
keeps its original `url` and both `published_at` (source) and `collected_at` (AI Pulse). AI-generated
fields are always separate from source content and labelled (`summary_is_ai`, `generated_by`, …).

**Authentication.**

1. `POST /auth/login` returns an access token and sets an `HttpOnly` refresh cookie.
2. Send `Authorization: Bearer <access_token>` with each request. The access token lasts 15 minutes.
3. `POST /auth/refresh` exchanges the refresh cookie for a new access token and rotates the cookie.
   Reusing an old refresh token revokes the whole session family.
4. `POST /auth/logout` revokes the session.

Some read endpoints are public and become personalised when a token is sent. Roles: `user`,
`analyst`, `admin`; staff routes are under `/admin`.

```bash
curl -s -c jar -H 'content-type: application/json' \
  -d '{"email":"me@example.com","password":"…"}' https://pulse.example.com/api/v1/auth/login
```

```bash
curl -s -H "Authorization: Bearer $TOKEN" "https://pulse.example.com/api/v1/news?category=rag&sort=importance"
```

**Errors.** Always one envelope, with the HTTP status matching the code:

```json
{"error": {"code": "validation_error", "message": "Request validation failed", "details": [{"loc": ["query", "page_size"], "msg": "...", "type": "..."}]}}
```

| Status | `code` | When |
|---|---|---|
| 400 | `bad_request` | invalid sort field, invalid connector config, … |
| 401 | `unauthorized` | missing/expired token (header `WWW-Authenticate: Bearer`) |
| 403 | `forbidden` | role not allowed |
| 404 | `not_found` | unknown id, or a resource that belongs to someone else |
| 409 | `conflict` | duplicate e-mail/slug, retrying a job that did not fail, last-admin protection |
| 422 | `validation_error` | body/query validation; **unknown query parameters are rejected** |
| 429 | `rate_limited` | rate limit exceeded; `Retry-After` header and `details.retry_after_seconds` |
| 501 | `not_implemented` | semantic search without an embedding provider |
| 503 | `queue_unavailable` | Redis/Celery unreachable when queueing a task |

**Lists.**
- Lists return `{"items": [...], "total", "page", "page_size", "pages"}`, with `page ≥ 1` and `page_size` between 1 and 100.
- Sorting is `sort=field` (ascending) or `sort=-field` (descending), against a whitelist per endpoint.
  Descending sorts put NULLs last, and severity sorts by rank (critical → info).
- Text filters are literal substring matches (`%` and `_` are escaped). Repeated parameters
  (`?severity=critical&severity=high`) mean "any of".

**Rate limits.** The defaults below are configurable. Responses carry `X-RateLimit-Limit` and
`X-RateLimit-Remaining` on limited routes.

| Scope | Applies to | Default |
|---|---|---|
| global | every `/api/v1` request, per client IP | 600/min |
| auth | register, login, change-password, password reset, per IP | 10/min |
| search | `GET /search`, per user (IP when anonymous) | 60/min |
| ai | `POST /search/ask`, `POST /briefings/generate`, per user | 10/min |

**Idempotency.** Several write endpoints are safe to repeat:
- `PUT`/`DELETE` on bookmarks and read state;
- `POST /preferences/follow|unfollow`;
- `POST /briefings/generate`, which returns the briefing generated in the last 10 minutes if there is one;
- mark-read endpoints.

Notifications are never delivered twice for the same event.

**Health and metrics** (outside `/api/v1`):
- `GET /health/live` and `GET /health/ready` (database and pgvector);
- `GET /metrics` (Prometheus; requires `Authorization: Bearer <METRICS_TOKEN>` when configured, and is never exposed by the edge).

## Endpoint reference

Module guides with field-level detail:
- [INGESTION.md](INGESTION.md): sources, connectors and jobs;
- [AI.md](AI.md): analysis, search, Ask AI Pulse and briefings;
- [RADAR.md](RADAR.md): bugs, incidents, vulnerabilities and alerts;
- [NOTIFICATIONS.md](NOTIFICATIONS.md): briefings, notifications and preferences.

The table below is regenerated from the code with `cd backend && python ../scripts/build-api-docs.py`.

<!-- BEGIN GENERATED ENDPOINTS -->

80 operations, generated from the OpenAPI schema.

### health

| Method | Path | Summary | Access |
|---|---|---|---|
| `GET` | `/health/live` | Liveness probe | public |
| `GET` | `/health/ready` | Readiness probe (checks database and pgvector) | public |

### auth

| Method | Path | Summary | Access |
|---|---|---|---|
| `POST` | `/api/v1/auth/change-password` | Change Password | signed in |
| `POST` | `/api/v1/auth/login` | Login; sets an httpOnly refresh cookie | public |
| `POST` | `/api/v1/auth/logout` | Logout | public |
| `GET` | `/api/v1/auth/me` | Me | signed in |
| `PATCH` | `/api/v1/auth/me` | Update Me | signed in |
| `POST` | `/api/v1/auth/password-reset/confirm` | Confirm Reset | public |
| `POST` | `/api/v1/auth/password-reset/request` | Request Reset | public |
| `POST` | `/api/v1/auth/refresh` | Rotate the refresh cookie, get a new access token | public |
| `POST` | `/api/v1/auth/register` | Register | public |

### dashboard

| Method | Path | Summary | Access |
|---|---|---|---|
| `GET` | `/api/v1/dashboard/summary` | Overview KPIs computed from collected data | public (personalised when signed in) |

### news

| Method | Path | Summary | Access |
|---|---|---|---|
| `GET` | `/api/v1/news` | Search and filter collected items | public (personalised when signed in) |
| `GET` | `/api/v1/news/{article_id}` | Get News | public (personalised when signed in) |
| `GET` | `/api/v1/news/{article_id}/analysis` | AI analysis (labelled AI-generated) and the explainable importance breakdown | public (personalised when signed in) |
| `DELETE` | `/api/v1/news/{article_id}/read` | Mark Unread | signed in |
| `PUT` | `/api/v1/news/{article_id}/read` | Mark Read | signed in |

### search

| Method | Path | Summary | Access |
|---|---|---|---|
| `GET` | `/api/v1/search` | Search all collected items | public (personalised when signed in) |
| `POST` | `/api/v1/search/ask` | Ask a question; answered only from collected items, with citations | public (personalised when signed in) |
| `GET` | `/api/v1/search/capabilities` | Capabilities | public |

### models

| Method | Path | Summary | Access |
|---|---|---|---|
| `GET` | `/api/v1/models` | AI models with their latest release | public |
| `GET` | `/api/v1/models/releases` | Model releases, newest first by default | public |
| `GET` | `/api/v1/models/{model_id}` | Get Model | public |

### tools

| Method | Path | Summary | Access |
|---|---|---|---|
| `GET` | `/api/v1/tools` | List Tools | public |
| `GET` | `/api/v1/tools/{tool_id}` | Get Tool | public |

### research

| Method | Path | Summary | Access |
|---|---|---|---|
| `GET` | `/api/v1/research` | List Papers | public |
| `GET` | `/api/v1/research/{paper_id}` | Get Paper | public |

### github

| Method | Path | Summary | Access |
|---|---|---|---|
| `GET` | `/api/v1/github/issues` | List Issues | public |
| `GET` | `/api/v1/github/repositories` | List Repositories | public |
| `GET` | `/api/v1/github/repositories/by-name/{owner}/{name}` | Get Repository By Name | public |
| `GET` | `/api/v1/github/repositories/{repo_id}` | Get Repository | public |

### bugs

| Method | Path | Summary | Access |
|---|---|---|---|
| `GET` | `/api/v1/bugs` | Public bug reports; severity always has a basis | public |
| `GET` | `/api/v1/bugs/{bug_id}` | Get Bug | public |

### security

| Method | Path | Summary | Access |
|---|---|---|---|
| `GET` | `/api/v1/security/stats` | Stats | public |
| `GET` | `/api/v1/security/vulnerabilities` | List Vulnerabilities | public |
| `GET` | `/api/v1/security/vulnerabilities/{cve_id}` | Get Vulnerability | public |

### incidents

| Method | Path | Summary | Access |
|---|---|---|---|
| `GET` | `/api/v1/incidents` | Provider incidents | public |
| `GET` | `/api/v1/incidents/{incident_id}` | Get Incident | public |

### radar

| Method | Path | Summary | Access |
|---|---|---|---|
| `GET` | `/api/v1/radar/summary` | Critical bugs, new/exploited CVEs, current vs resolved incidents, trends | public |

### briefings

| Method | Path | Summary | Access |
|---|---|---|---|
| `GET` | `/api/v1/briefings` | List Briefings | public (personalised when signed in) |
| `POST` | `/api/v1/briefings/generate` | Generate (or refresh) today's personalised briefing now | signed in |
| `GET` | `/api/v1/briefings/latest` | Latest | public (personalised when signed in) |
| `GET` | `/api/v1/briefings/{briefing_date}` | By Date | public (personalised when signed in) |

### notifications

| Method | Path | Summary | Access |
|---|---|---|---|
| `GET` | `/api/v1/notifications` | List Notifications | signed in |
| `POST` | `/api/v1/notifications/read-all` | Mark All Read | signed in |
| `GET` | `/api/v1/notifications/unread-count` | Unread Count | signed in |
| `DELETE` | `/api/v1/notifications/{notification_id}` | Delete Notification | signed in |
| `POST` | `/api/v1/notifications/{notification_id}/read` | Mark Read | signed in |
| `POST` | `/api/v1/notifications/{notification_id}/unread` | Mark Unread | signed in |

### preferences

| Method | Path | Summary | Access |
|---|---|---|---|
| `GET` | `/api/v1/preferences` | Get Preferences | signed in |
| `PUT` | `/api/v1/preferences` | Update Preferences | signed in |
| `POST` | `/api/v1/preferences/follow` | Follow a technology, GitHub repository (owner/name) or AI provider | signed in |
| `GET` | `/api/v1/preferences/options` | Allowed interest values | public |
| `POST` | `/api/v1/preferences/unfollow` | Stop following an entry (idempotent) | signed in |

### bookmarks

| Method | Path | Summary | Access |
|---|---|---|---|
| `GET` | `/api/v1/bookmarks` | List Bookmarks | signed in |
| `DELETE` | `/api/v1/bookmarks/{article_id}` | Remove Bookmark | signed in |
| `PUT` | `/api/v1/bookmarks/{article_id}` | Add Bookmark | signed in |

### catalog

| Method | Path | Summary | Access |
|---|---|---|---|
| `GET` | `/api/v1/categories` | List Categories | public |
| `GET` | `/api/v1/sources` | Enabled data sources | public |

### admin

| Method | Path | Summary | Access |
|---|---|---|---|
| `GET` | `/api/v1/admin/ai/config` | Effective AI provider configuration (no secrets) | admin / analyst |
| `POST` | `/api/v1/admin/ai/run` | Ai Run | admin / analyst |
| `GET` | `/api/v1/admin/ai/status` | Provider configuration (no secrets), coverage and usage | admin / analyst |
| `POST` | `/api/v1/admin/alerts/run` | Evaluate alert rules now | admin / analyst |
| `GET` | `/api/v1/admin/audit-logs` | List Audit Logs | admin |
| `GET` | `/api/v1/admin/connectors` | Available connectors and their options | admin / analyst |
| `GET` | `/api/v1/admin/ingestion/status` | Source health and recent failures | admin / analyst |
| `GET` | `/api/v1/admin/jobs` | Ingestion job history (admin, analyst) | admin / analyst |
| `POST` | `/api/v1/admin/jobs/retry-failed` | Retry every source whose latest job failed in the window (audited) | admin / analyst |
| `POST` | `/api/v1/admin/jobs/{job_id}/retry` | Retry Job | admin / analyst |
| `GET` | `/api/v1/admin/roles` | List Roles | admin |
| `GET` | `/api/v1/admin/sources` | List Sources | admin |
| `POST` | `/api/v1/admin/sources` | Create Source | admin |
| `DELETE` | `/api/v1/admin/sources/{source_id}` | Delete Source | admin |
| `PATCH` | `/api/v1/admin/sources/{source_id}` | Update Source | admin |
| `POST` | `/api/v1/admin/sources/{source_id}/run` | Queue an immediate run (works for disabled sources too) | admin / analyst |
| `GET` | `/api/v1/admin/system/health` | Detailed health of every component (admin, analyst) | admin / analyst |
| `GET` | `/api/v1/admin/usage` | Usage statistics over a window (admin, analyst) | admin / analyst |
| `GET` | `/api/v1/admin/users` | List Users | admin |
| `GET` | `/api/v1/admin/users/{user_id}` | Get User | admin |
| `PATCH` | `/api/v1/admin/users/{user_id}` | Change a user's role or active status (audited) | admin |

<!-- END GENERATED ENDPOINTS -->
