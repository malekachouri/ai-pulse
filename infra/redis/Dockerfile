# syntax=docker/dockerfile:1.7
# Redis 7 as Celery broker / result backend, rate-limit and telemetry store.
# Password comes from REDIS_PASSWORD_FILE (Docker secret); runs as the unprivileged "redis" user.
FROM redis:7.4-alpine
LABEL org.opencontainers.image.title="ai-pulse-redis"
COPY --chown=redis:redis redis.conf /usr/local/etc/redis/redis.conf
COPY --chmod=0755 entrypoint.sh /usr/local/bin/ai-pulse-redis
USER redis
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=10 \
  CMD REDISCLI_AUTH="$(cat "${REDIS_PASSWORD_FILE:-/dev/null}" 2>/dev/null || printf '%s' "${REDIS_PASSWORD:-}")" redis-cli ping | grep -q PONG
ENTRYPOINT ["/usr/local/bin/ai-pulse-redis"]
