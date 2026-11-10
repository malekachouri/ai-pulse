# syntax=docker/dockerfile:1.7
# One Dockerfile, four images sharing the same dependency layers:
#   --target api     FastAPI (uvicorn, 1 process per container; scale with replicas)
#   --target worker  Celery worker
#   --target beat    Celery Beat (exactly one replica)
#   --target migrate Alembic migrations (one-shot)
FROM python:3.12-slim-bookworm AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY requirements.txt .
# Optional build secret "build_ca": CA bundle of a TLS-inspecting corporate proxy (never stored in the image).
RUN --mount=type=cache,target=/root/.cache/pip --mount=type=secret,id=build_ca,required=false \
    if [ -s /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca; fi; \
    python -m venv /opt/venv && /opt/venv/bin/pip install --upgrade pip && /opt/venv/bin/pip install -r requirements.txt \
    && /opt/venv/bin/pip uninstall -y pip  # no package manager in the runtime image

FROM python:3.12-slim-bookworm AS runtime
LABEL org.opencontainers.image.title="ai-pulse-backend" \
      org.opencontainers.image.description="AI Pulse API, workers and scheduler"
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONPATH=/app \
    LOG_JSON=true
# Unprivileged user with a fixed UID. OS patches come from rebuilding on the current base image
# (Dependabot + scheduled CI builds), and Trivy blocks images with fixable HIGH/CRITICAL CVEs.
# The base image's own pip (and what it vendors) is never used at runtime: remove it.
RUN python -m pip uninstall -y pip \
    && groupadd --system --gid 10001 app && useradd --system --uid 10001 --gid app --home /app --shell /usr/sbin/nologin app
COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY --chown=root:root alembic.ini ./
COPY --chown=root:root alembic ./alembic
COPY --chown=root:root app ./app
COPY --chown=root:root docker/healthcheck.py /usr/local/bin/healthcheck.py
# Code is owned by root and read-only for the app user; containers also run with a read-only root filesystem.
USER 10001:10001

FROM runtime AS api
EXPOSE 8000
# Only trust X-Forwarded-For from these proxies (the web container network in docker-compose).
ENV FORWARDED_ALLOW_IPS=127.0.0.1
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 CMD ["python", "/usr/local/bin/healthcheck.py", "api"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--no-server-header", "--timeout-graceful-shutdown", "20"]

FROM runtime AS worker
HEALTHCHECK --interval=60s --timeout=30s --start-period=60s --retries=3 CMD ["python", "/usr/local/bin/healthcheck.py", "worker"]
CMD ["celery", "-A", "app.workers.celery_app", "worker", "-Q", "ingestion", "--concurrency", "4", "--loglevel", "INFO", "--without-mingle", "--max-tasks-per-child", "200"]

FROM runtime AS beat
HEALTHCHECK --interval=60s --timeout=10s --start-period=120s --retries=3 CMD ["python", "/usr/local/bin/healthcheck.py", "beat"]
CMD ["celery", "-A", "app.workers.celery_app", "beat", "--loglevel", "INFO", "--schedule", "/tmp/celerybeat-schedule"]

FROM runtime AS migrate
CMD ["alembic", "upgrade", "head"]
