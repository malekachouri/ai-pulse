# AI Pulse build prompts

These are the prompts that built this repository, one file per phase, ready to reuse: to rebuild AI Pulse
from scratch, to build a similar product, or to re-run a phase (for example the final audit) on a later
version. Each file says when to send it, what it produced here, and what to check before moving on.
The prompt itself is in a box you can copy as one message.

| # | Prompt | Result in this repository |
|---|---|---|
| – | [Project specification](00-project-specification.md) | vision and stack (context, not a prompt) |
| 01 | [Project foundation](01-project-foundation.md) | architecture, schema, auth, core API, Docker |
| 02 | [Complete user interface](02-frontend.md) | app shell, every page, dashboard, filters |
| 03 | [FastAPI backend and database](03-backend-api.md) | typed API modules, search, admin endpoints |
| 04 | [Automated ingestion engine](04-data-ingestion.md) | 14 connectors, 28 official sources, Celery |
| 05 | [AI-powered analysis](05-ai-engine.md) | providers, grounded analysis, scoring, RAG |
| 06 | [Bugs & Failures Radar](06-bugs-failures-radar.md) | bugs, incidents, advisories, alerts |
| 07 | [Daily briefing and notifications](07-briefings-notifications.md) | personalised briefings, notification center |
| 08 | [Production readiness](08-production-readiness.md) | images, CI/CD, monitoring, security, backups |
| 09 | [Senior engineering review](09-final-audit.md) | verified audit, fixes, docs/AUDIT_REPORT.md |
| 10 | [Additional features](10-additional-features.md) | all built: watchlist, change detection, Bug Intelligence, model comparison, Learning Assistant, weekly PDF, recommendations, offsite backups |

## How to use them

1. Open Claude Code in your project directory.
2. Send prompt 01 first.
3. Wait for the implementation and inspect the files.
4. Send each following prompt separately, never all nine in one message.
5. Ask Claude to run the tests after every major module.
6. Never let it replace working code unnecessarily.

These prompts make Claude implement the actual project, not just write an architecture document.
Between two prompts, run the application, look at it, and fix errors before moving on. In this
repository each phase ended as a pull request, merged once CI was green.

## Start a new project with them

```bash
mkdir ai-pulse && cd ai-pulse && git init
```

```bash
claude
```

Then paste prompt 01. After the architecture is approved, let Claude create the files and implement it.
Review and save each phase:

```bash
git status
```

```bash
git diff
```

```bash
git add . && git commit -m "feat: implement AI Pulse architecture"
```

Keep API keys in `secrets/` or `.env` files, never in Git.

## Short prompts that helped between phases

| When | Prompt |
|---|---|
| after any phase | `verify the repo` (Claude re-runs the checks and reports what is missing) |
| a CI log fails | paste the log: Claude reproduces the failure locally and fixes the cause |
| Dependabot opens pull requests | `check the Dependabot PRs one by one` |
| a dependency needs more than a version bump | `do a complete migration like the Node one` (e.g. Python 3.15 in PR #20) |
