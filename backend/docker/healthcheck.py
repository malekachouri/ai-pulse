"""Container health checks (no curl/wget in the image). Usage: healthcheck.py api|worker|beat"""

import os
import socket
import sys
import time

BEAT_HEARTBEAT_KEY = "aipulse:metrics:beat_heartbeat"  # app.core.metrics.BEAT_HEARTBEAT_KEY


def api() -> bool:
    import urllib.request  # here, not at the top: it takes ~0.5 s to import and only this check needs it

    with urllib.request.urlopen("http://127.0.0.1:8000/health/live", timeout=3) as r:  # noqa: S310 - fixed local URL
        return r.status == 200


def worker() -> bool:
    from app.workers.celery_app import celery_app

    replies = celery_app.control.ping(destination=[f"celery@{socket.gethostname()}"], timeout=10)
    return bool(replies)


def _redis_url() -> str:
    """The setting `redis_url` as the app reads it: environment first, then the Docker secret file."""
    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        path = os.path.join(os.environ.get("SECRETS_DIR", "/run/secrets"), "redis_url")
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                url = f.read().strip()
    return url or "redis://localhost:6379/0"


def _redis_get(url: str, key: str, timeout: float = 5.0) -> bytes | None:
    """GET one key with a minimal RESP client: the standard library only, so the check starts in a fraction of
    a second even when the CPU is busy (importing the app's settings and the redis package takes seconds)."""
    import ssl
    from urllib.parse import unquote, urlsplit

    u = urlsplit(url)
    if u.scheme not in ("redis", "rediss"):
        raise ValueError(f"unsupported Redis URL scheme {u.scheme!r}")
    sock = socket.create_connection((u.hostname or "localhost", u.port or 6379), timeout=timeout)
    if u.scheme == "rediss":
        ctx = ssl.create_default_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2  # never TLS 1.0 / 1.1
        sock = ctx.wrap_socket(sock, server_hostname=u.hostname)
    with sock, sock.makefile("rb") as f:

        def call(*args: str) -> bytes | None:
            parts = [f"*{len(args)}\r\n".encode()]
            for a in args:
                b = a.encode()
                parts.append(b"$%d\r\n%s\r\n" % (len(b), b))
            sock.sendall(b"".join(parts))
            line = f.readline()
            if line.startswith(b"-"):
                raise RuntimeError(line[1:].strip().decode(errors="replace"))
            if line.startswith(b"$"):
                n = int(line[1:])
                return None if n < 0 else f.read(n + 2)[:-2]
            return line[1:].strip()

        if u.password is not None:
            auth = [unquote(u.username), unquote(u.password)] if u.username else [unquote(u.password)]
            call("AUTH", *auth)
        db = u.path.lstrip("/")
        if db and db != "0":
            call("SELECT", db)
        return call("GET", key)


def beat() -> bool:
    """Healthy when the Beat scheduler loop wrote its heartbeat recently (see HeartbeatScheduler).

    Imports nothing from the app: the key name is pinned by test_beat_healthcheck_reads_the_heartbeat."""
    last = _redis_get(_redis_url(), BEAT_HEARTBEAT_KEY)
    max_age = int(os.environ.get("BEAT_MAX_AGE_SECONDS", "120"))
    return last is not None and time.time() - float(last) < max_age


if __name__ == "__main__":
    try:
        ok = {"api": api, "worker": worker, "beat": beat}[sys.argv[1]]()
    except Exception as exc:  # noqa: BLE001 - any failure means unhealthy
        print(f"unhealthy: {type(exc).__name__}: {exc}", file=sys.stderr)
        ok = False
    sys.exit(0 if ok else 1)
