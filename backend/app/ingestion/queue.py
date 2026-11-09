"""How the API asks workers to run a source. Swappable so tests don't need Redis."""

from typing import Protocol

from app.core.errors import AppError


class QueueUnavailableError(AppError):
    status_code = 503
    code = "queue_unavailable"


class TaskQueue(Protocol):
    def enqueue_ingest(self, source_id: str, trigger: str) -> str: ...

    def enqueue(self, task: str, kwargs: dict) -> str: ...


class CeleryTaskQueue:
    def enqueue_ingest(self, source_id: str, trigger: str) -> str:
        from app.workers.celery_app import celery_app

        try:
            result = celery_app.send_task(
                "aipulse.ingest_source", args=[source_id], kwargs={"trigger": trigger}, retry=False
            )
        except Exception as exc:  # kombu raises OperationalError subclasses when Redis is down
            raise QueueUnavailableError(
                "The ingestion queue (Redis) is unavailable; try again shortly"
            ) from exc
        return str(result.id)

    def enqueue(self, task: str, kwargs: dict) -> str:
        from app.workers.celery_app import celery_app

        try:
            return str(celery_app.send_task(task, kwargs=kwargs, retry=False).id)
        except Exception as exc:
            raise QueueUnavailableError("The task queue (Redis) is unavailable; try again shortly") from exc
