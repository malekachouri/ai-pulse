# syntax=docker/dockerfile:1.7
# PostgreSQL 16 + pgvector, with a tuned configuration and first-boot initialisation
# (extensions + a least-privilege application role). Runs as the image's unprivileged "postgres" user.
FROM pgvector/pgvector:0.8.7-pg16
# OS security updates on top of the base image (Trivy gate: no fixable HIGH/CRITICAL), and remove gosu:
# the container always starts as the unprivileged postgres user, so the entrypoint never needs to drop
# privileges, and the binary only adds attack surface (its Go runtime has its own CVE stream).
# OS_UPGRADE=false only for air-gapped builds without a Debian mirror; CI and releases keep the default.
ARG OS_UPGRADE=true
# Optional build secret "build_ca" (TLS-inspecting corporate proxy): apt then uses HTTPS mirrors with that CA
# for the duration of this step only; the image keeps the standard Debian configuration.
RUN --mount=type=secret,id=build_ca,required=false set -eu; \
    if [ "$OS_UPGRADE" = true ]; then \
    if [ -s /run/secrets/build_ca ]; then \
      echo 'Acquire::https::CAInfo "/run/secrets/build_ca";' > /etc/apt/apt.conf.d/99build-ca; \
      sed -i 's|http://|https://|g' /etc/apt/sources.list.d/debian.sources /etc/apt/sources.list.d/pgdg.list; \
    fi; \
    apt-get update --error-on=any; \
    DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends upgrade; \
    rm -rf /var/lib/apt/lists/* /etc/apt/apt.conf.d/99build-ca; \
    sed -i 's|https://|http://|g' /etc/apt/sources.list.d/debian.sources /etc/apt/sources.list.d/pgdg.list; \
    fi; \
    rm -f /usr/local/bin/gosu
LABEL org.opencontainers.image.title="ai-pulse-postgres"
COPY --chown=postgres:postgres postgresql.conf /etc/postgresql/postgresql.conf
COPY --chown=postgres:postgres initdb/ /docker-entrypoint-initdb.d/
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=10 \
  CMD pg_isready -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-postgres}" -h 127.0.0.1 || exit 1
# Target directory of the optional backup service (named volume inherits this ownership).
RUN mkdir -p /backups && chown postgres:postgres /backups && chmod 700 /backups
USER postgres
CMD ["postgres", "-c", "config_file=/etc/postgresql/postgresql.conf"]
