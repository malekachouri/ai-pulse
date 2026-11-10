# syntax=docker/dockerfile:1.7
# PostgreSQL 16 + pgvector, with a tuned configuration and first-boot initialisation
# (extensions + a least-privilege application role). Runs as the image's unprivileged "postgres" user.
ARG PG_IMAGE=pgvector/pgvector:0.8.1-pg16
FROM ${PG_IMAGE}
LABEL org.opencontainers.image.title="ai-pulse-postgres"
COPY --chown=postgres:postgres postgresql.conf /etc/postgresql/postgresql.conf
COPY --chown=postgres:postgres initdb/ /docker-entrypoint-initdb.d/
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=10 \
  CMD pg_isready -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-postgres}" -h 127.0.0.1 || exit 1
# Target directory of the optional backup service (named volume inherits this ownership).
RUN mkdir -p /backups && chown postgres:postgres /backups && chmod 700 /backups
USER postgres
CMD ["postgres", "-c", "config_file=/etc/postgresql/postgresql.conf"]
