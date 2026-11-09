"""Celery application: Redis broker, one `ingestion` queue, Beat drives the DB-backed scheduler."""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "aipulse", broker=settings.redis_url, backend=settings.redis_url, include=["app.workers.tasks"]
)
celery_app.conf.update(
    task_default_queue="ingestion",
    task_acks_late=True,  # a crashed worker's task is redelivered (runs are idempotent)
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_time_limit=60 * 30,
    task_soft_time_limit=60 * 25,
    result_expires=60 * 60 * 24,
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "dispatch-due-sources": {
            "task": "aipulse.dispatch_due_sources",
            "schedule": float(settings.ingestion_dispatch_seconds),
        },
        "recover-stale-jobs": {"task": "aipulse.recover_stale_jobs", "schedule": 600.0},
        "ai-analyze": {"task": "aipulse.ai_analyze", "schedule": 120.0},
        "ai-rescore": {"task": "aipulse.ai_rescore", "schedule": 3600.0},
        "briefings": {
            "task": "aipulse.generate_due_briefings",
            "schedule": float(settings.briefing_dispatch_seconds),
        },
        "alerts": {"task": "aipulse.evaluate_alerts", "schedule": float(settings.alerts_interval_seconds)},
    },
)
