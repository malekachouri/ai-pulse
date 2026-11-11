# Browser end-to-end tests

Playwright + axe-core against the **production build** of the full stack. CI runs them on every pull
request (job *Images · build, scan, end-to-end*). They cover:

| Spec | What it checks |
|---|---|
| `tests/pages.spec.ts` | Every page (26) as anonymous, user and admin, on desktop in the dark and light themes and on a phone (Pixel 7). Each page must render an h1, have no JavaScript/CSP error, no unexpected API failure and no horizontal scrolling, and pass axe-core (WCAG 2.0/2.1 A and AA, plus best practices). |
| `tests/flows.spec.ts` | User journeys: registration (validation, duplicates), session after reload, bookmark and read, feed search, search and Ask AI Pulse, settings persistence, notification tabs, keyboard skip link, sign out, wrong password, password reset **through the real email** (Mailpit), an admin changing a role, mobile navigation. |

## Run locally

You need Docker, Node 26 and `./secrets` + `.env` (see the README quick start).

```bash
cd e2e && npm ci && npx playwright install chromium && cd ..
```

Build the images and run everything (later runs can drop `--build`):

```bash
./scripts/e2e.sh --build
```

Pass Playwright options after it, e.g. only the flows, with a visible browser:

```bash
./scripts/e2e.sh tests/flows.spec.ts --headed
```

Open the HTML report of the last run:

```bash
cd e2e && npx playwright show-report
```

`scripts/e2e.sh` starts the stack with `e2e/docker-compose.e2e.yml` (test only: a Mailpit inbox on
<http://127.0.0.1:8025>, and relaxed rate limits because one browser crawls everything from one IP). It then:
- seeds ten clearly labelled `[E2E]` items through the real ingestion writer (`e2e/seed.py`; links go to
  example.com, and the source is disabled so it is never fetched);
- creates a one-off admin;
- runs the tests.

The stack keeps running afterwards. Stop it with:

```bash
docker compose -f docker-compose.yml -f e2e/docker-compose.e2e.yml down
```

Never run the test override in production.
