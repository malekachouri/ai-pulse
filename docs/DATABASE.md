# Database

PostgreSQL 16 with **pgvector** (embeddings), built-in full-text search, and **pg_trgm** (title
similarity for cross-source duplicate detection). The schema is managed only by Alembic migrations.
In the deployed schema that is 27 tables, 92 indexes, 25 unique constraints and 25 check constraints.

## Conventions

- UUID primary keys (integer for small lookup tables such as `roles`, `categories`); `created_at` and
  `updated_at` on mutable rows; every timestamp is `timestamptz` (UTC).
- Enumerations are stored as `VARCHAR` with a `CHECK` constraint, so adding a value is a cheap migration.
- **Provenance**:
  - every `articles` row keeps the original `url`, its `source_id`, the source's `published_at` and
    our `collected_at`, a `content_hash` and a `verification_status`;
  - unique `(source_id, external_id)` makes ingestion idempotent;
  - `canonical_key` and `duplicate_of_id` link the same story across sources.
- **Facts vs. AI**:
  - source content lives in `articles` and the typed tables;
  - everything an LLM produced lives in `ai_analyses` (`kind`, `prompt_version`, provider, model,
    tokens, cost, `valid`), never in the fact columns.
- **No invented severity**: `severity` is always paired with `severity_basis`. The 0–100
  `importance_score` is a separate ranking and is never shown as CVSS.
- **Idempotency keys**:
  - `notifications (user_id, dedup_key)`;
  - `daily_briefings (user_id, briefing_date)`;
  - `bookmarks (user_id, article_id)`;
  - `ai_analyses (article_id, kind, prompt_version)`;
  - `incidents (provider, external_id)`;
  - `security_vulnerabilities.cve_id`.

## Tables by domain

The ER diagram and the column-level list are in [ARCHITECTURE.md §4](ARCHITECTURE.md#4-database-schema).

| Domain | Tables |
|---|---|
| Identity | `roles` (admin, analyst, user), `users`, `user_preferences` (interests, follows, notification rules in `alert_settings` JSONB, briefing schedule), `refresh_tokens` (SHA-256 hashes, rotation family), `password_reset_tokens` |
| Content | `sources` (connector, config, checkpoint, health), `categories`, `articles` (canonical item, `embedding vector(768)`, generated `search_vector`), `article_categories` |
| Intelligence | `ai_models`, `ai_model_releases`, `ai_tools`, `research_papers`, `github_repositories` (star history), `github_issues`, `software_bugs`, `security_vulnerabilities`, `incidents` |
| AI | `ai_analyses` (summary, entities, importance, release `changes`), `ai_usage` (one row per LLM/embedding call: tokens, cost, errors), `learning_lessons` (per-user daily AI lessons, labelled) |
| User data | `bookmarks`, `article_reads`, `notifications` (soft-deleted with `dismissed_at`, so the dedup key survives), `daily_briefings` |
| Operations | `collection_jobs` (every ingestion run), `audit_logs` (admin actions) |

### Notable indexes

| Index | Purpose |
|---|---|
| `ix_articles_embedding_hnsw` (HNSW, cosine) | semantic search / RAG retrieval |
| `ix_articles_search_vector` (GIN) | keyword search with weighted title/description/content |
| `ix_articles_title_trgm` (GIN, `gin_trgm_ops`) | near-duplicate titles across sources |
| filter indexes on `item_type`, `published_at`, `severity`, `importance_score`, … | feed filters (migration 0002) |
| `ix_incidents_status_verified`, `ix_incidents_started_at` | "currently active" incidents, radar history |
| `ix_notifications_user_unread`, `ix_notifications_user_kind_created` | unread badge, notification center tabs |
| `ix_collection_jobs_source_started`, `ix_collection_jobs_status` | job history, failure dashboards |
| `ix_ai_usage_created` | daily token budget, usage statistics |

## Migrations

| Revision | Content |
|---|---|
| 0001 | full initial schema, extensions, roles and categories |
| 0002 | filter and sort indexes |
| 0003 | `canonical_key`, 27 official sources |
| 0004 | `pg_trgm`, `ai_usage`, analysis indexes |
| 0005 | bug resolution and fix fields, verification timestamps, `alert_settings`, GitHub advisories source |
| 0006 | `briefing_weekday`, notification `dismissed_at`, check constraints on the briefing schedule, notification index |
| 0007 | analysis kind `changes` (release comparison), `learning_lessons` |

Workflow:

1. Change the models in `backend/app/models`.
2. Generate the migration:

   ```bash
   cd backend && alembic revision --autogenerate -m "describe the change" --rev-id 0008
   ```

3. Read and edit the generated file. Autogenerate misses check constraints, data migrations and
   extension changes. Keep `downgrade()` working.
4. Verify:

   ```bash
   alembic upgrade head && alembic check && alembic downgrade base && alembic upgrade head
   ```

   CI runs the same sequence, and the test suite builds its schema with the real migrations,
   including a downgrade/upgrade round trip.

In production, migrations run in the one-shot `migrate` service before the API, workers and Beat
start, and `scripts/deploy.sh` runs them before each rollout. Migrations must stay
**backward compatible with the previous release** (expand → migrate → contract), because a rollback
redeploys the old image on the new schema.

## Roles and access

| Role | Privileges | Used by |
|---|---|---|
| `postgres` (superuser) | everything | first-boot init, `backup` service, `scripts/backup.sh`, `scripts/restore.sh` |
| `aipulse` (`APP_DB_USER`) | **not** superuser, cannot create roles or databases; owns the application database and the `public` schema | API, workers, Beat, migrations |
| `metrics` | `pg_monitor` only (statistics views, no table data) | postgres-exporter |

Extensions (`vector`, `pg_trgm`, `pg_stat_statements`) are created once by the superuser in
`infra/postgres/initdb/10-init.sh`, so the application role never needs elevated rights. Rotate
passwords with `scripts/rotate-db-password.sh app|metrics|postgres`.

## Backups, restore, retention

See [DEPLOYMENT.md §5](DEPLOYMENT.md#5-backups-and-restore).
- Backups are `pg_dump --format=custom`, scheduled and taken before each deployment, with checksums and a readability check.
- A restore goes into a staging database and is swapped in only after it succeeds.
- `wal_level=replica` is set, so point-in-time recovery (WAL archiving, pgBackRest, wal-g) can be added later without schema changes.

Data growth is dominated by `articles` (with `raw` JSONB and embeddings) and `collection_jobs`.
Indicative sizes:
- an `articles` row is about 10 KB with its embedding;
- `collection_jobs` grows by one row per source per run, about 30 000 rows a month with the default schedules.

Plan a retention job for `collection_jobs` older than 90 days if the history is not needed.

## Configuration

`infra/postgres/postgresql.conf` is sized for a 2 GB container. Main settings:
- `shared_buffers` 512 MB, `effective_cache_size` 1.5 GB, `work_mem` 16 MB;
- `maintenance_work_mem` 128 MB (also used by HNSW builds);
- SSD-friendly `random_page_cost`;
- logs for slow queries over 500 ms, lock waits and autovacuum;
- `pg_stat_statements` enabled;
- `idle_in_transaction_session_timeout` of 5 minutes;
- `scram-sha-256` authentication and data checksums (initdb).
