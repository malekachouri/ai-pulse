#!/usr/bin/env bash
# Browser end-to-end tests (Playwright + axe-core) against the production build of the full stack.
#   ./scripts/e2e.sh [--build] [playwright arguments...]
# Needs ./secrets and .env (scripts/generate-secrets.sh, cp .env.example .env), Node 26 and the Playwright
# browser (cd e2e && npm ci && npx playwright install chromium). Starts the stack with the test-only
# additions in e2e/docker-compose.e2e.yml, seeds labelled [E2E] items, creates a one-off admin, runs the
# tests and leaves the stack running for inspection (HTML report: cd e2e && npx playwright show-report).
set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE=(docker compose -f docker-compose.yml -f e2e/docker-compose.e2e.yml)
BUILD=(--no-build)
if [[ "${1:-}" == "--build" ]]; then BUILD=(--build); shift; fi

echo "==> starting the stack (with mailpit and test rate limits)"
"${COMPOSE[@]}" up -d "${BUILD[@]}" --wait --wait-timeout 300 mailpit api worker beat web

echo "==> seeding labelled test data"
"${COMPOSE[@]}" exec -T api python - < e2e/seed.py
"${COMPOSE[@]}" exec -T api python -m app.cli ai-analyze --limit 100 > /dev/null

# A new admin per run: its password only exists in this process.
E2E_ADMIN_EMAIL="e2e-admin-$(date +%s)@example.com"
E2E_ADMIN_PASSWORD="$(openssl rand -hex 16)-Aa1"
export E2E_ADMIN_EMAIL E2E_ADMIN_PASSWORD
"${COMPOSE[@]}" exec -T -e ADMIN_PASSWORD="$E2E_ADMIN_PASSWORD" api \
  python -m app.cli create-admin --email "$E2E_ADMIN_EMAIL" --full-name "E2E Admin" > /dev/null

# The reader account exists before alerts are evaluated, so notifications and unread counters are always
# on screen (otherwise they depend on when Beat's 5-minute alert run happens to fire). Twelve labelled
# notifications per test user make the counters two digits: axe-core skips one-character text, so a
# low-contrast "3" badge would pass unnoticed.
"${COMPOSE[@]}" exec -T api python - <<'PY'
import asyncio
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.alerts.engine import AlertEngine
from app.core.config import get_settings
from app.db.session import create_engine, create_session_factory
from app.models import Notification, User, UserPreference
from app.models.enums import NotificationKind, Severity
from app.services.auth import AuthService
from app.services.email import ConsoleEmailSender


async def main() -> None:
    settings = get_settings()
    engine = create_engine(settings)
    async with create_session_factory(engine)() as s:
        auth = AuthService(s, settings, ConsoleEmailSender())
        if await auth.users.get_by_email("e2e-reader@example.com") is None:
            await auth.register("e2e-reader@example.com", "E2e-Reader-Pass-2026", "E2E Reader")
        reader = await auth.users.get_by_email("e2e-reader@example.com")
        pref = await s.scalar(select(UserPreference).where(UserPreference.user_id == reader.id))
        if pref is None:
            pref = UserPreference(user_id=reader.id)
            s.add(pref)
        pref.followed_technologies = ["Kubernetes"]  # so "what to learn next" has a reason to show
        await s.commit()
        stats = await AlertEngine(s).run()
        users = (await s.scalars(select(User.id).where(User.email.like("e2e-%@example.com")))).all()
        now = datetime.now(UTC)
        for uid in users:
            for n in range(12):
                await s.execute(insert(Notification).values(
                    id=uuid.uuid4(), user_id=uid, kind=NotificationKind.VULNERABILITY, severity=Severity.HIGH,
                    title=f"[E2E] Test notification {n + 1}", body="[E2E] Test data.",
                    link="https://example.com/e2e", dedup_key=f"e2e:{n}", created_at=now,
                ).on_conflict_do_nothing())
        await s.commit()
        print(f"alerts created: {stats.created}; test notifications for {len(users)} user(s)")
    await engine.dispose()


asyncio.run(main())
PY

echo "==> running the browser tests"
cd e2e
[[ -d node_modules ]] || npm ci --no-audit --no-fund
export E2E_BASE_URL="${E2E_BASE_URL:-http://localhost:${WEB_PORT:-3000}}"
export MAILPIT_URL="${MAILPIT_URL:-http://127.0.0.1:${MAILPIT_PORT:-8025}}"
npx playwright test "$@"
