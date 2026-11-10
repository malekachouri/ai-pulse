"""Celery task telemetry, recorded in Redis so the API can expose it to Prometheus.

Each worker process records execution time, failures and retries into one Redis hash
(`aipulse:metrics:tasks`, fields `<task>|<stat>`), using atomic HINCRBY/HINCRBYFLOAT. A Redis outage
never breaks a task: telemetry errors are logged and ignored.
"""

import time
from typing import Any

from celery import signals
from celery.beat import PersistentScheduler

from app.core.logging import get_logger
from app.core.metrics import BEAT_HEARTBEAT_KEY, SCHEDULER_KEY, TASK_BUCKETS, TASK_STATS_KEY

log = get_logger(__name__)
_started: dict[str, float] = {}
_redis: Any = None


def _client() -> Any:
    global _redis
    if _redis is None:
        from redis import Redis

        from app.core.config import get_settings

        _redis = Redis.from_url(get_settings().redis_url, socket_timeout=2, socket_connect_timeout=2)
    return _redis


def record(task: str, seconds: float | None, *, failed: bool = False, retried: bool = False) -> None:
    try:
        pipe = _client().pipeline(transaction=False)
        if retried:
            pipe.hincrby(TASK_STATS_KEY, f"{task}|retries", 1)
        if failed:
            pipe.hincrby(TASK_STATS_KEY, f"{task}|failures", 1)
        if seconds is not None:
            pipe.hincrby(TASK_STATS_KEY, f"{task}|count", 1)
            pipe.hincrbyfloat(TASK_STATS_KEY, f"{task}|sum", seconds)
            for b in TASK_BUCKETS:
                if seconds <= b:
                    pipe.hincrby(TASK_STATS_KEY, f"{task}|le_{b}", 1)
            if not failed:
                pipe.hset(TASK_STATS_KEY, f"{task}|last_success", time.time())
        pipe.execute()
    except Exception as exc:  # noqa: BLE001 - telemetry must never fail a task
        log.warning("task_telemetry_failed", task=task, error=type(exc).__name__)


def mark_scheduler_dispatch() -> None:
    try:
        _client().set(SCHEDULER_KEY, time.time())
    except Exception as exc:  # noqa: BLE001
        log.warning("scheduler_telemetry_failed", error=type(exc).__name__)


@signals.task_prerun.connect
def _prerun(task_id: str | None = None, **_: Any) -> None:
    if task_id:
        _started[task_id] = time.perf_counter()


@signals.task_postrun.connect
def _postrun(task_id: str | None = None, task: Any = None, state: str | None = None, **_: Any) -> None:
    start = _started.pop(task_id or "", None)
    if task is None or start is None or state == "RETRY":
        return
    record(task.name, time.perf_counter() - start, failed=state == "FAILURE")


@signals.task_retry.connect
def _retry(sender: Any = None, **_: Any) -> None:
    if sender is not None:
        record(sender.name, None, retried=True)


class HeartbeatScheduler(PersistentScheduler):
    """Celery Beat's default scheduler plus a heartbeat in Redis (container health check, Prometheus).

    Beat ticks at least every `beat_max_loop_interval` seconds; the heartbeat is written at most every 15 s.
    """

    _last_beat = 0.0

    def tick(self, *args: Any, **kwargs: Any) -> float:
        delay = super().tick(*args, **kwargs)
        now = time.time()
        if now - self._last_beat >= 15:
            self._last_beat = now
            try:
                _client().set(BEAT_HEARTBEAT_KEY, now)
            except Exception as exc:  # noqa: BLE001
                log.warning("beat_heartbeat_failed", error=type(exc).__name__)
        return min(delay, 30.0)  # wake up at least every 30 s so the heartbeat stays fresh
