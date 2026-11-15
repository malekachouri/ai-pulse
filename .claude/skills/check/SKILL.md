---
name: check
description: Run the AI Pulse checks (backend lint, migrations and tests, frontend lint, types, tests and build, smoke test of the running stack) with Docker only, and report what failed and why. Use after changing code, before a commit or pull request, or when the user asks whether the app still works.
argument-hint: "[backend] [frontend] [smoke] [pytest args]"
allowed-tools: Bash(./scripts/check.sh:*), Bash(docker compose ps:*), Bash(docker compose logs:*), Bash(git status:*), Bash(git diff:*)
---

# /check: run the project's checks

Run the checks with the project script. It needs only Docker: the backend and frontend run on a copy of the
code in throwaway containers (a separate test database), so the user's running stack and data are not
touched.

1. Choose what to run from `$ARGUMENTS`:
   - empty: everything, `./scripts/check.sh` (backend, frontend, smoke);
   - one or more of `backend`, `frontend`, `smoke`: only those, e.g. `./scripts/check.sh backend`;
   - `backend` followed by pytest arguments runs part of the tests, e.g. `./scripts/check.sh backend -k cli`.

   If the user did not say and the change touches only one side (`backend/` or `frontend/`, see `git status`),
   run that side only and say so.
2. Run it with a long timeout (the backend takes about 2 minutes, 5 on a slow PC; the first run downloads
   packages). The last lines are a summary: `ok   <part>` or `FAIL <part>`.
3. Report in plain, short sentences:
   - each part, passed or failed, with the test count (`280 passed`);
   - for a failure: the failing test or lint rule, the file and line, and the error message, then the likely
     cause. Read the failing test and the code it covers before explaining. Never call a failure flaky
     without evidence.
4. Do not edit code during `/check` unless the user asks to fix what failed. Never skip, delete or weaken a
   test to make it pass.

Notes:

- `smoke` needs the stack running (`docker compose up -d --wait`). If the stack still runs with the browser
  test settings (after `./scripts/e2e.sh`), the script restarts it normally first: those settings relax the
  login rate limit on purpose and would make the smoke test fail.
- Browser end-to-end tests (Playwright) are not part of `/check`: they need Node and a browser on the
  computer and take about 6 minutes. CI runs them on every pull request. Locally: `./scripts/e2e.sh --build`
  (see `e2e/README.md`).
