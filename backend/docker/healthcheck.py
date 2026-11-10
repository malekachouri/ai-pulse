"""Container health checks (no curl/wget in the image). Usage: healthcheck.py api|worker|beat"""

import os
import socket
import sys
import time
import urllib.request


def api() -> bool:
    with urllib.request.urlopen("http://127.0.0.1:8000/health/live", timeout=3) as r:  # noqa: S310 - fixed local URL
        return r.status == 200


def worker() -> bool:
    from app.workers.celery_app import celery_app

    replies = celery_app.control.ping(destination=[f"celery@{socket.gethostname()}"], timeout=10)
    return bool(replies)


def beat() -> bool:
    """Healthy when the Beat scheduler loop wrote its heartbeat recently (see HeartbeatScheduler)."""
    from redis import Redis

    from app.core.config import get_settings
    from app.core.metrics import BEAT_HEARTBEAT_KEY

    last = Redis.from_url(get_settings().redis_url, socket_timeout=3).get(BEAT_HEARTBEAT_KEY)
    max_age = int(os.environ.get("BEAT_MAX_AGE_SECONDS", "120"))
    return last is not None and time.time() - float(last) < max_age


if __name__ == "__main__":
    try:
        ok = {"api": api, "worker": worker, "beat": beat}[sys.argv[1]]()
    except Exception as exc:  # noqa: BLE001 - any failure means unhealthy
        print(f"unhealthy: {type(exc).__name__}: {exc}", file=sys.stderr)
        ok = False
    sys.exit(0 if ok else 1)
