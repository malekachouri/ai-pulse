# Contributing

Thank you for helping improve AI Pulse. This guide covers how changes flow from an idea to production.

## Ground rules

1. **Never invent data.** Every item must come from a source, with its original URL and both its
   publication and collection dates. Severity needs a documented basis. AI-generated text is stored
   and displayed separately from facts and is labelled.
2. **No secrets in code, tests, fixtures, images or logs.** Configuration comes from environment
   variables and secret files. Test fixtures use clearly synthetic data (`example.test`, `[DEMO]`).
3. **No placeholders.** No `TODO`s or stub implementations in merged code. Open an issue instead.
4. **Fix problems; don't silence them.** Do not skip tests, add blanket `noqa`/`eslint-disable`, or
   ignore scanner findings to get a green build. A justified, narrow suppression with a comment is
   acceptable when the tool is wrong.

## Workflow

1. Open an issue (bug, feature, or security hardening; report vulnerabilities privately, see
   [SECURITY.md](SECURITY.md)).
2. Branch from `main`: `feat/…`, `fix/…`, `docs/…`, `ops/…`.
3. Develop with the Docker dev stack or natively ([docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)).
4. Run the checks locally (below), then open a pull request. CI must be green: lint, types, tests,
   migrations, dependency audit, Compose/Prometheus validation, image build, Trivy, end-to-end smoke
   test, backup/restore drill, CodeQL.
5. At least one review. Changes to `infra/`, `.github/`, auth, or the database schema need a review
   from a maintainer who owns that area.
6. Squash-merge with a [Conventional Commit](https://www.conventionalcommits.org/) title
   (`feat(radar): …`, `fix(auth): …`, `ops(ci): …`). Releases are tags `vX.Y.Z` (semantic versioning).

## Checks before pushing

Backend:

```bash
cd backend && ruff check --config pyproject.toml app tests alembic docker ../scripts && ruff format --check --config pyproject.toml app tests alembic docker ../scripts && pytest -q
```

Frontend:

```bash
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
```

Generated files: the dashboards, and the API reference when routes change.

```bash
python3 scripts/build-dashboards.py && (cd backend && python ../scripts/build-api-docs.py)
```

## What a good pull request contains

- **Tests** for the behaviour you add or fix. Backend tests run against real PostgreSQL. Mock only
  external HTTP, using recorded or realistic responses.
- **A migration** for every model change, reviewed by hand, with a working `downgrade()` and backward
  compatibility with the previous release (see [docs/DATABASE.md](docs/DATABASE.md#migrations)).
- **Docs** updated in the same PR: the module guide in `docs/`, `.env.example` for new settings,
  [SECURITY.md](SECURITY.md) for security-relevant changes.
- **Observability** for new background work: metrics, a dashboard panel and, where it matters, an
  alert with a promtool unit test.
- **Accessibility** for UI changes: keyboard reachable, labelled controls, a data-table view for every
  chart, both themes checked.

## Adding a data source

Prefer official APIs and feeds; respect their terms and rate limits. Implement the connector contract
in `backend/app/ingestion/connectors/` (fetch, normalize, validate), add it to the catalog, and test it
with a recorded real response. See [docs/INGESTION.md](docs/INGESTION.md).
