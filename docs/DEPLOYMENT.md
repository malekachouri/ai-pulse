# Deployment

AI Pulse ships as seven container images and runs with Docker Compose on a single host. The same
images run unchanged on an orchestrator if you outgrow one host. This guide covers a production
deployment end to end.

| Image | Built from | Runs as | Notes |
|---|---|---|---|
| `api` | `backend/Dockerfile --target api` | uid 10001 | uvicorn, 1 process per container, scaled with replicas |
| `worker` | `--target worker` | uid 10001 | Celery worker (ingestion, AI, alerts, briefings) |
| `beat` | `--target beat` | uid 10001 | Celery Beat, **exactly one** replica |
| `migrate` | `--target migrate` | uid 10001 | `alembic upgrade head`, one-shot |
| `web` | `frontend/Dockerfile` | uid 10001 | Next.js standalone server |
| `postgres` | `infra/postgres` | postgres (999) | PostgreSQL 16 + pgvector, tuned config, init script |
| `redis` | `infra/redis` | redis (999) | broker, rate limits, telemetry; AOF persistence |

Optional profiles: `edge` (Caddy, automatic HTTPS), `monitoring` (Prometheus, Alertmanager, Grafana,
postgres-exporter, redis-exporter), `backup` (scheduled `pg_dump`).

## 1. Server prerequisites

- Linux host with Docker Engine 25+ and the Compose plugin v2.24+ (`!reset` overrides).
- 4 vCPU and 8 GB RAM for the full stack with monitoring. Sum of the default limits: about 6 GB.
- DNS `A`/`AAAA` record for your domain pointing to the host. Ports 80 and 443 open (edge profile).
  Nothing else needs to be reachable from outside.
- A deploy user that belongs to the `docker` group, used only by CI over SSH (key authentication).
- Outbound HTTPS to the data sources (see [INGESTION.md](INGESTION.md)), to your LLM provider and to
  `ghcr.io`.

## 2. First deployment

```bash
sudo mkdir -p /opt/ai-pulse && sudo chown deploy:deploy /opt/ai-pulse && cd /opt/ai-pulse
```

```bash
git clone https://github.com/malekachouri/ai-pulse.git .
```

The deploy workflow refreshes the compose files and configs on every release; a clone is only needed
for the first start.

```bash
./scripts/generate-secrets.sh
```

This creates `./secrets/*` (directory mode 700): database, Redis, JWT, metrics token and Grafana
passwords, plus the derived connection strings. Optional keys are empty files. Put your values in
them, without a trailing newline:

```bash
printf '%s' 'sk-...' > secrets/openai_api_key
```

| Secret file | Purpose |
|---|---|
| `postgres_password` | PostgreSQL superuser (init, backups, restores only) |
| `app_db_password`, `database_url` | least-privilege application role and its connection string |
| `metrics_db_password` | read-only `metrics` role for postgres-exporter |
| `redis_password`, `redis_url`, `redis_exporter_passwords.json` | Redis authentication |
| `jwt_secret` | access-token signing key (64 random characters) |
| `metrics_token` | bearer token Prometheus uses for `/metrics` |
| `grafana_admin_password` | Grafana `admin` user |
| `alert_webhook_url` | Slack/Teams/Discord-compatible or generic webhook for alerts |
| `openai_api_key`, `anthropic_api_key` | LLM providers (optional) |
| `github_token`, `nvd_api_key` | higher source rate limits (optional) |
| `smtp_password` | SMTP password for password-reset emails (optional; empty = no auth) |

```bash
cp .env.example .env
```

Then edit `.env`:

- `ENVIRONMENT=production`
- `DOMAIN=pulse.example.com`
- `CORS_ORIGINS=["https://pulse.example.com"]`
- `IMAGE_PREFIX=ghcr.io/<owner>/ai-pulse`
- `IMAGE_TAG=<release tag or sha>`
- `LLM_PROVIDER` and `LLM_MODEL` (and the embedding settings) if you use AI features
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY`, `SMTP_USERNAME`, `SMTP_FROM` and `PUBLIC_URL` so that
  password-reset emails are delivered (with a link to `PUBLIC_URL/reset-password`). Without
  `SMTP_HOST` no email is sent; the API logs `email_not_configured` at startup.

Start everything:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile edge --profile monitoring --profile backup up -d --wait
```

```bash
./scripts/smoke-test.sh https://pulse.example.com
```

Create the first administrator:

```bash
docker compose exec api python -m app.cli create-admin --email you@example.com
```

`generate-secrets.sh` never overwrites existing secrets (see §8 for rotation).

### Without building on the server (recommended) vs. building locally

`docker-compose.prod.yml` resets every `build:` section, so the server only pulls the images CI built,
scanned and signed. For a quick local "production-like" run, use the base file alone. It builds locally:

```bash
docker compose up -d --build --wait
```

### Behind an existing reverse proxy or load balancer

Skip the `edge` profile, bind the web container where your proxy can reach it (`WEB_BIND`, `WEB_PORT`),
route `/api/*` to the API container and the rest to web. Set `EDGE_IP` to your proxy's address on the
`frontend` network, and make sure it overwrites `X-Forwarded-For` with the client IP. Otherwise the
per-IP rate limits apply to the proxy as a whole.

## 3. CI/CD

`.github/workflows/ci.yml` runs on pull requests, on pushes to `main`, weekly, and on demand:

1. Frontend: ESLint, TypeScript, Vitest, production build.
2. Backend:
   - Ruff (including Bandit-style `S` rules) and formatting;
   - migrations upgrade → `alembic check` → downgrade to base → upgrade;
   - pytest against real PostgreSQL + pgvector and Redis.
3. Dependency audit: `pip-audit` and `npm audit`.
4. Configuration:
   - `docker compose config` for the base, dev and prod files with every profile;
   - promtool config check and alert unit tests, amtool;
   - shellcheck and actionlint;
   - Grafana dashboards regenerated and compared.
5. Containers:
   - every image built with BuildKit cache;
   - **Trivy gate**: no fixable HIGH/CRITICAL vulnerability or embedded secret, results uploaded to code scanning;
   - full stack started with production settings;
   - end-to-end smoke test, monitoring scrape check;
   - backup → restore drill → smoke test again.

`.github/workflows/deploy.yml` runs on a `v*` tag (production) or manually (staging or production):

1. **publish** (`packages: write`, `id-token: write`): builds each image, runs the Trivy gate, pushes
   to `ghcr.io/<owner>/ai-pulse/<image>:<sha>` (and `:<tag>`) with an SBOM and max-mode provenance,
   then records a signed build-provenance attestation. You can check it with:

   ```bash
   gh attestation verify oci://ghcr.io/<owner>/ai-pulse/api:<sha> --owner <owner>
   ```

2. **deploy** (GitHub *environment* `staging`/`production`: add required reviewers there): copies
   the bundle (compose files, `infra/`, `scripts/`; never secrets) over SSH with a pinned host key,
   then runs `scripts/deploy.sh` on the server, which does the following:
   - pulls the images;
   - takes a pre-deployment backup;
   - runs the migrations;
   - rolls out with `--wait` and runs the smoke test;
   - **rolls back automatically** to the previous tag on any failure.

   The registry token is the job's short-lived `GITHUB_TOKEN`, and the server logs out of the registry afterwards.

Repository settings to configure once:

| Where | Name | Value |
|---|---|---|
| Environment secrets | `DEPLOY_HOST`, `DEPLOY_USER` | server address, deploy user |
| | `DEPLOY_SSH_KEY` | private key of a deploy-only key pair (no passphrase) |
| | `DEPLOY_KNOWN_HOSTS` | output of `ssh-keyscan -t ed25519 <host>` (verify the fingerprint) |
| Environment variables | `DEPLOY_PATH`, `PUBLIC_URL` | `/opt/ai-pulse`, `https://pulse.example.com` |
| Environments | `production` | required reviewers, deployment branch/tag rule `v*` |
| Branch protection | `main` | require the CI and CodeQL checks |

Workflows default to `permissions: contents: read`; jobs only elevate what they need.

## 4. Monitoring and alerting

Grafana and Prometheus bind to `127.0.0.1` only. Reach them through an SSH tunnel:

```bash
ssh -L 3001:127.0.0.1:3001 -L 9090:127.0.0.1:9090 deploy@pulse.example.com
```

Then open <http://localhost:3001>. The user is `admin` and the password is in `secrets/grafana_admin_password`.

| Dashboard | Panels |
|---|---|
| **AI Pulse — Service health** | API up, Postgres/Redis reachability, requests/s, 5xx ratio, p50/p95/p99 latency, slowest routes, requests by route, rate-limited requests, DB connections by state, connection pool, transactions, DB size, Redis memory |
| **AI Pulse — Pipeline, ingestion & AI** | queue length, Beat heartbeat and last dispatch age, sources down, task duration p95, runs, failures and retries per task, ingestion jobs per status, longest job per connector, source availability table, AI error ratio, tokens, estimated cost, analysis backlog, calls/errors by provider and purpose |

Dashboards are generated from `scripts/build-dashboards.py` (dashboards as code; CI fails if the
JSON is stale). Alert rules live in `infra/prometheus/alerts.yml`, with unit tests in `alerts_test.yml`:

| Severity | Alerts |
|---|---|
| critical | APIDown, DependencyDown, BeatNotRunning, SchedulerDispatchStalled |
| warning | HighErrorRate (> 5 % 5xx), HighLatencyP95 (> 1 s), DatabaseConnectionsHigh (> 80 %), CeleryQueueBacklog (> 200 for 15 min), IngestionJobsFailing, DataSourceDown (3+ failures), CeleryTaskFailures, SlowBackgroundJobs (p95 > 10 min), AIProviderErrors (> 20 %), PostgresExporterDown, RedisMemoryHigh |
| info | AITokenSpendSpike (2× the same hour yesterday), AIAnalysisBacklog |

Alertmanager sends every alert, and its resolution, to the URL in `secrets/alert_webhook_url`.

Logs are JSON on stdout, rotated by Docker (5 × 20 MB per container):

```bash
docker compose logs -f api worker
```

`/metrics` requires `Authorization: Bearer <metrics_token>` and is never routed by the edge.

## 5. Backups and restore

- **Scheduled.** The `backup` service writes `pg_dump --format=custom` every
  `BACKUP_INTERVAL_SECONDS` (default 24 h) to the `pgbackups` volume (or `BACKUP_DIR`, a host
  directory owned by UID 999), with a `.sha256` and a readability check, and keeps
  `BACKUP_RETENTION_DAYS` days. Its health check turns unhealthy when the newest dump is older than
  the interval plus one hour.
- **On demand / before each deployment.** `./scripts/backup.sh [dir]` writes to `./backups`.
- **Off-site.** Copy the dumps to object storage (for example a cron job running `rclone copy` or
  `aws s3 sync`, using a bucket with versioning and object lock). Dumps contain personal data
  (emails, preferences): encrypt them at rest.
- **Restore.** `./scripts/restore.sh backups/<file>.dump` works in four steps:
  1. it verifies the checksum;
  2. it restores into a *new* database as the application role;
  3. only if that succeeds, it stops the writers and swaps the databases;
  4. it runs the migrations and restarts.

  The previous database is kept as `<db>_pre_restore_<ts>` for rollback. A failed or corrupt
  restore leaves production untouched. CI rehearses this drill on every run.

Recovery objectives with the defaults: RPO ≤ 24 h (lower it with `BACKUP_INTERVAL_SECONDS`, or add
WAL archiving: `wal_level=replica` is already set), RTO ≈ restore time (minutes for this dataset size).

## 6. Upgrades and rollback

- Push a tag `v1.2.3` and approve the `production` environment.
- Rollbacks are automatic when the rollout or the smoke test fails.
- For a manual rollback, run `IMAGE_TAG=<previous> scripts/deploy.sh` on the host. The previous tag is
  in `.deployed_tag` before each deployment.
- Migrations are forward-only in production. Write them backward compatible with the previous
  release (expand → migrate → contract over two releases), so that an image rollback never needs a
  schema rollback.

## 7. Scaling

- **API.** Stateless. Set `API_REPLICAS`; Prometheus discovers every replica through DNS, and rate
  limits are shared through Redis.
- **Workers.** Set `WORKER_REPLICAS` or raise `--concurrency`. Ingestion uses per-source advisory
  locks and per-host rate limits in Redis, so replicas never duplicate work.
- **Beat.** Must stay at one replica.
- **PostgreSQL.** Tune `infra/postgres/postgresql.conf` (`shared_buffers` ≈ 25 % of the container
  memory). Keep the sum of pool sizes (API replicas × 20 + workers) below `max_connections`; the
  `DatabaseConnectionsHigh` alert warns at 80 %.

## 8. Operations checklist

| Task | How |
|---|---|
| Rotate secrets | `./scripts/generate-secrets.sh --force` rotates the JWT secret (signs everyone out), the metrics token and the Redis password; then `docker compose ... up -d --force-recreate --wait` (Compose does not notice secret *content* changes). Database and Grafana passwords: procedure in SECURITY.md. |
| Add an LLM key | write it to `secrets/<provider>_api_key`, set `LLM_PROVIDER` / `LLM_MODEL` in `.env`, then `up -d api worker` |
| Disable a noisy source | Admin → Sources (audited) |
| Retry failed ingestion | Admin → Jobs & failures → *Retry all failed sources* |
| Check system health | Admin → Overview (database, migrations, Redis/queues, scheduler, workers, ingestion, AI provider) |
| Patch base images | merge Dependabot PRs; the weekly CI run rebuilds and re-scans every image |
